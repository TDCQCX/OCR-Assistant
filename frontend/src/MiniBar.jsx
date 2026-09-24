import React, { useEffect, useRef } from 'react'
import { call } from './bridge'
import { useApp } from './main'
import Guide, { useGuide } from './Guide'
import { EngineSwitch, Icon, IconBtn, IconSeg, QBox, ResizeHandles, Tip, useWindowDrag } from './ui'

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
  const preview = result?.error ? `失败:${result.error}` : result?.answer || status.text
  const guide = useGuide('mini')

  // 高度锁定:把内容自然高度上报后端,由后端锁定窗口高度。
  // 否则字号/主题变大后第二行会被裁掉,或窗口高度被拉伸后无法还原。
  const rootRef = useRef(null)
  useEffect(() => {
    const el = rootRef.current
    if (!el) return
    const report = () => {
      const need = Math.round(el.scrollHeight + 2)   // +2 = 上下边框
      if (need > 0 && need !== cfg.window?.miniHeight) call('set_mini_height', need)
    }
    report()
    const t = setTimeout(report, 120)                // 字体/图标异步加载后再校正一次
    return () => clearTimeout(t)
  }, [cfg.ui?.fontSize, cfg.ui?.radius, cfg.window?.miniHeight, preview])

  const toggleOcr = async (cloud) => {
    await call('set_config_value', 'ocr.mode', cloud ? 'cloud' : 'local')
    await app.reload()
  }

  return (
    <div
      ref={rootRef}
      className="h-full w-full flex flex-col rounded-card border border-line overflow-hidden relative"
      style={{ background: 'var(--c-panel)', boxShadow: 'var(--c-shadow)' }}
    >
      {/* 拖动左右边缘可加宽:超过阈值自动切回悬浮窗模式 */}
      {/* 迷你条高度固定:只允许左右拉伸(超过阈值会自动切回悬浮窗) */}
      <ResizeHandles which="mini" edges={['w', 'e']} />
      {/* 第一行:图标工具栏 */}
      <div className="shrink-0 flex items-center gap-2 px-2 h-[38px] drag-handle" data-guide="mini-drag" {...drag}>
        <span className="logo-o w-[22px] h-[22px] text-[11px] no-drag" title="OCR 助手">O</span>
        <span className="w-1.5 h-1.5 rounded-full shrink-0 no-drag" style={{ background: tone }} />
        <span className="truncate text-[12px] text-muted flex-1 min-w-0 no-drag">{preview}</span>
        <span data-guide="mini-mode" className="flex items-center no-drag">
          <IconSeg size="sm" value="mini" options={MODES} onChange={(m) => app.setMode(m)} />
        </span>
        <EngineSwitch cloud={(cfg.ocr?.mode || 'cloud') === 'cloud'} onChange={toggleOcr} tips={['云端', '本地']} />
        <span data-guide="mini-run" className="no-drag">
          <IconBtn icon="scan" tip={busy ? '处理中…' : '框选识别(Ctrl+Shift+A)'} primary disabled={busy}
                   onClick={() => call('run_mini_capture', question.trim())} />
        </span>
        <IconBtn icon="info" tip="新手教程" onClick={() => call('guide_start', 'mini')} />
        <IconBtn icon="snip" tip="框选新区域" onClick={() => app.startSnip()} />
        <IconBtn icon="settings" tip="设置" onClick={() => call('open_settings')} />
        <IconBtn icon="power" tip="退出(Ctrl+Q)" danger onClick={() => app.quit()} />
      </div>

      {/* 第二行:提问预输入 */}
      <div className="shrink-0 flex items-center gap-2 px-2 pb-2 pt-0.5" data-guide="mini-qbox">
        <Tip text="提问/指令(自输入会自动记住)">
          <span className="text-muted"><Icon name="edit" size={14} /></span>
        </Tip>
        <QBox value={question} onChange={setQuestion} rows={1} className="flex-1 no-drag"
              presets={cfg.behavior?.question_presets} history={cfg.behavior?.question_history}
              placeholder={`提问/指令:留空则默认「${cfg.behavior?.default_question || '请回答识别到的内容'}」`} />
      </div>
      <Guide mode="mini" open={guide.open} onClose={guide.stop} />
    </div>
  )
}
