import React, { useEffect, useRef, useState } from 'react'
import { call } from './bridge'
import { useApp } from './main'
import Guide, { useGuide } from './Guide'
import { EngineSwitch, Icon, IconBtn, IconSeg, Logo, QBox, ResizeHandles, Tip, useWindowDrag } from './ui'

const MODES = [
  { value: 'overlay', label: '悬浮窗', icon: 'overlay' },
  { value: 'translate', label: '翻译', icon: 'translate' },
  { value: 'snip', label: '框选', icon: 'snip' },
  { value: 'mini', label: '迷你条', icon: 'mini' },
]

/** 迷你条模式:图标行(选中项展开文字)+ 提问输入行,可自由拖动 */
export default function MiniBar() {
  const app = useApp()
  const { cfg, status, result, busy } = app
  const drag = useWindowDrag('mini')
  const { question, setQuestion } = app  // 全局共享:与悬浮窗/翻译模式同步
  const tone = { idle: 'var(--c-ok)', working: 'var(--c-warn)', ok: 'var(--c-ok)', danger: 'var(--c-danger)' }[status.tone] || 'var(--c-muted)'
  // 问题10:状态点旁边必须是「AI 运行状态」,不是翻译/识别结果。
  // 结果放到第二行(提问输入行的右侧预览)去展示。
  const statusText = status.text || '就绪'
  const preview = result?.error
    ? `失败:${result.error}`
    : (result?.answer || result?.ocr_text || '').replace(/\s+/g, ' ').trim()
  const guide = useGuide('mini')

  const [quitHint, setQuitHint] = useState(false)
  useEffect(() => {
    const onEvent = (e) => {
      const ev = e.detail
      if (ev?.type === 'quitHint') setQuitHint(ev.value !== false)
    }
    window.addEventListener('ocr-event', onEvent)
    return () => window.removeEventListener('ocr-event', onEvent)
  }, [])
  // 提示期间在迷你条上方预留一块固定空间(后端按 MINI_MODAL_EXTRA 向上扩展窗口),
  // 关闭即精确还原。这里不做"先测量再申请":测量时窗口还没长高,量到的是被挤压的高度。
  useEffect(() => {
    if (!quitHint) return undefined
    call('set_modal_room', true)
    return () => { call('set_modal_room', false) }
  }, [quitHint])

  // 提示打开期间用户可能用模式切换/快捷键离开迷你条 —— 此时必须主动收起提示,
  // 否则上面的清理不会执行,迷你条会被永久撑大。
  //
  // 注意:只能比较"自己观察到的模式变化",不能用 `cfg.mode !== 'mini'` 直接判断 ——
  // 配置广播到达本窗口有延迟,刚进迷你条时 cfg.mode 还可能是旧值,
  // 那样会在提示刚打开的瞬间把它自己关掉,并留下一次乱序的 加高/还原 调用。
  const prevModeRef = useRef(null)
  useEffect(() => {
    const prev = prevModeRef.current
    prevModeRef.current = cfg.mode
    if (prev === 'mini' && cfg.mode && cfg.mode !== 'mini' && quitHint) setQuitHint(false)
  }, [cfg.mode, quitHint])

  // 高度锁定:把迷你条本体的自然高度上报后端,由后端锁定窗口高度。
  // 注意只量"迷你条本体"(.mini-body),不把上方预留的提示区算进去 ——
  // 否则提示关闭后高度不会回退。
  const rootRef = useRef(null)
  useEffect(() => {
    const el = rootRef.current?.querySelector('.mini-body')
    if (!el) return undefined
    const report = () => {
      const need = Math.round(el.scrollHeight + 2)
      if (need > 0 && need !== cfg.window?.miniHeight) call('set_mini_height', need)
    }
    report()
    const t0 = setTimeout(report, 150)
    return () => clearTimeout(t0)
  }, [cfg.ui?.fontSize, cfg.ui?.radius, cfg.window?.miniHeight, preview, quitHint])

  // 迷你条只有约 80px 高,不适合放大弹窗。退出提示改成"迷你条上方的独立浮层":
  // 浮层本身绝对定位在窗口顶部之外,窗口只临时抬高一点点容纳它。

  const toggleOcr = async (cloud) => {
    await call('set_config_value', 'ocr.mode', cloud ? 'cloud' : 'local')
    await app.reload()
  }

  return (
    <div
      ref={rootRef}
      className="window-shell view-mini h-full w-full flex flex-col justify-end border border-line relative"
      style={{ background: 'var(--c-panel)', boxShadow: 'var(--c-shadow)' }}
    >
      {/* 拖动左右边缘可加宽:超过阈值自动切回悬浮窗模式 */}
      {/* 迷你条高度固定:只允许左右拉伸(超过阈值会自动切回悬浮窗) */}
      <ResizeHandles which="mini" edges={['w', 'e']} />
      {/* 退出提示:渲染在"迷你条上方的预留区"里(迷你条本体被 justify-end 顶到底部),
          因此不会再把它撑开,关闭后窗口精确还原到原位置与高度。 */}
      {quitHint && (
        <div className="mini-hint-spacer" data-mini-hint-spacer="1">
        <div className="mini-hint-layer" data-mini-quit-hint="1">
          <div className="mini-hint-card anim-pop">
            <span className="card-icon" style={{ width: 24, height: 24 }}>
              <Icon name="power" size={13} />
            </span>
            <span className="font-medium text-[12.5px] whitespace-nowrap">要退出吗?</span>
            <button type="button" className="btn btn-sm shrink-0"
                    onClick={() => { setQuitHint(false); call('minimize_app') }}>
              最小化到托盘
            </button>
            <button type="button" className="btn btn-sm shrink-0"
                    onClick={() => { setQuitHint(false); call('quit_app') }}>
              直接关闭
            </button>
            <button type="button" className="btn btn-primary btn-sm shrink-0"
                    title="到主界面处理(迷你条太小)"
                    onClick={() => { setQuitHint(false); call('open_quit_dialog_in_main') }}>
              去悬浮窗
            </button>
            <button type="button" className="icon-btn shrink-0" title="取消"
                    onClick={() => setQuitHint(false)}>
              <Icon name="close" size={14} />
            </button>
          </div>
        </div>
        </div>
      )}
      <div className="mini-body shrink-0 w-full flex flex-col">
      {/* 第一行:图标工具栏(左=状态与预览,右=动作,中间弹性留白) */}
      <div className="shrink-0 flex items-center gap-2 px-2 h-[38px] drag-handle" data-guide="mini-drag" {...drag}>
        <span className="no-drag toolbar-group" title="OCR 助手"><Logo size={22} /></span>
        {/* 状态点 + AI 状态(可收缩到 0;右侧控件优先占位,问题9) */}
        <span className="toolbar-group no-drag min-w-0 overflow-hidden" style={{ flex: '0 1 auto' }}>
          <span className="w-1.5 h-1.5 rounded-full shrink-0" style={{ background: tone }} />
          <span className="truncate text-[12px] text-muted min-w-0">{statusText}</span>
        </span>
        <span className="flex-1" />
        <span data-guide="mini-mode" className="flex items-center no-drag">
          <IconSeg size="sm" value="mini" options={MODES} onChange={(m) => app.setMode(m)} />
        </span>
        <EngineSwitch cloud={(cfg.ocr?.mode || 'cloud') === 'cloud'} onChange={toggleOcr} tips={['云端', '本地']} />
        {/* 蓝色主按钮 = 直接进入自由截图(全屏框选),不再"复用上次区域" */}
        <span data-guide="mini-run" className="no-drag">
          <IconBtn icon="snip" tip={busy ? '处理中…' : '框选识别(Ctrl+Shift+A)'} primary disabled={busy}
                   onClick={() => app.startSnip()} />
        </span>
        <span className="toolbar-sep no-drag" />
        <span className="toolbar-group no-drag">
          <IconBtn icon="info" tip="新手教程" onClick={() => call('guide_start', 'mini')} />
          <IconBtn icon="settings" tip="设置" onClick={() => call('open_settings')} />
          <IconBtn icon="power" tip="退出(Ctrl+Q)" danger onClick={() => app.quit()} />
        </span>
      </div>

      {/* 第二行:单行输入 + 结果预览(与上一行左对齐) */}
      <div className="shrink-0 flex items-center gap-2 px-2 pb-2 pt-0.5" data-guide="mini-qbox">
        <Tip text="提问/指令(自输入会自动记住)">
          <span className="text-muted grid place-items-center w-5 shrink-0"><Icon name="edit" size={14} /></span>
        </Tip>
        <QBox value={question} onChange={setQuestion} className="flex-1 min-w-0 no-drag"
              onSubmit={() => app.startSnip()}
              placeholder={`提问/指令:留空则默认「${cfg.behavior?.default_question || '请回答识别到的内容'}」`} />
      </div>
      {/* 第三行:上次结果的提示(不再直接甩一段裸文本 —— 那样看起来像不明字符串)。
           带「结果」标签 + 图标,并说明可点「框选」重新识别。 */}
      {preview && (
        <div className="shrink-0 flex items-center gap-1.5 px-2 pb-2 -mt-0.5 min-w-0"
             data-guide="mini-preview">
          <Icon name={result?.error ? 'alert' : 'wand'} size={12}
                className="shrink-0" style={{ color: result?.error ? 'var(--c-danger)' : 'var(--c-muted)' }} />
          <span className="shrink-0 text-[11px] text-muted">{result?.error ? '失败' : '结果'}</span>
          <span className="text-muted shrink-0">·</span>
          <span className="truncate text-[11.5px] text-muted min-w-0" title={preview}>{preview}</span>
        </div>
      )}
      </div>
      <Guide mode="mini" open={guide.open} onClose={guide.stop} />
    </div>
  )
}
