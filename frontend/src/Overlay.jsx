import React, { useEffect, useRef, useState } from 'react'
import { call } from './bridge'
import { useApp } from './main'
import QuitDialog from './QuitDialog'
import Guide, { useGuide } from './Guide'
import { Btn, EngineSwitch, Icon, IconBtn, IconSeg, Logo, Pill, QBox, ResizeHandles, Tip, useDownloader, useSmallWindow, useToast, useWindowDrag } from './ui'

/** 端侧识别档位的显示名(与 app/local_models.py 的 OCR_TIERS 一致) */
const LOCAL_TIER_NAMES = { light: '端侧·轻量', balanced: '端侧·均衡', full: '端侧·全量' }

const MODES = [
  { value: 'overlay', label: '悬浮窗', icon: 'overlay' },
  { value: 'translate', label: '翻译', icon: 'translate' },
  { value: 'snip', label: '框选', icon: 'snip' },
  { value: 'mini', label: '迷你条', icon: 'mini' },
]

export default function Overlay() {
  const app = useApp()
  const { cfg, status, result, busy, setStatus } = app
  const toast = useToast()
  const dl = useDownloader()
  const holeRef = useRef(null)
  const dragHeader = useWindowDrag('overlay')
  const dragFooter = useWindowDrag('overlay')
  const { question, setQuestion } = app  // 全局共享:各模式输入框内容保持同步
  const [borderHidden, setBorderHidden] = useState(false)
  const [topmost, setTopmost] = useState(cfg.window?.always_on_top !== false)
  const small = useSmallWindow()
  const guide = useGuide('overlay')

  useEffect(() => {
    call('last_result').then((r) => { if (r && (r.answer || r.ocr_text)) app.setResult(r) })
  }, [])

  // 顶部只显示当前模型与状态:直接由 cfg 派生,设置窗口改动后会随 config 事件立即刷新。
  // 问题12:云端/本地开关切换时,这里显示的内容必须跟着变 ——
  //   云端 → 当前平台填的模型 ID;本地 → 端侧识别模型(与云端无关)。
  const curProv = (cfg.providers || []).find((p) => p.id === cfg.active_provider) || {}
  const ocrCloudNow = (cfg.ocr?.mode || 'cloud') === 'cloud'
  const cloudModelName = curProv.model || curProv.name || '未选择模型'
  const localModelName = cfg.local?.ocr_tier_name || LOCAL_TIER_NAMES[cfg.local?.ocr_tier] || '端侧识别'
  const modelName = ocrCloudNow ? cloudModelName : localModelName
  // 本地模式不需要 API Key,只要有模型档位就算就绪
  const modelReady = ocrCloudNow ? !!(curProv.api_key || '').trim() : true

  // 把洞口(OCR 区域)几何上报后端,用于把该区域从窗口"输入/绘制区域"中挖掉 → 鼠标可穿透
  const reportRef = useRef(() => {})
  const chromeRef = useRef(cfg.window?.chromeHeight || 240)
  const wantHoleRef = useRef(null)   // 目标洞口尺寸(收敛式调整,抵消面板高度变化)
  const triesRef = useRef(0)
  useEffect(() => {
    const el = holeRef.current
    if (!el) return
    const report = () => {
      // 用 offset*(布局尺寸)而不是 getBoundingClientRect,避免切换动画的 transform 影响测量
      const r = { x: el.offsetLeft, y: el.offsetTop, width: el.offsetWidth, height: el.offsetHeight }
      const cs = getComputedStyle(el)
      const bw = parseFloat(cs.borderTopWidth) || 0
      const dpr = window.devicePixelRatio || 1
      const chrome = Math.max(0, window.innerHeight - r.height)
      if (chrome > 20) chromeRef.current = chrome
      call('set_hole_region', {
        x: (r.x + bw) * dpr,
        y: (r.y + bw) * dpr,
        w: Math.max(0, r.width - 2 * bw) * dpr,
        h: Math.max(0, r.height - 2 * bw) * dpr,
        innerH: window.innerHeight * dpr,
        innerW: window.innerWidth * dpr,
        // chromeCss 用 CSS 像素上报:后端拿它换算"洞口尺寸 -> 窗口尺寸",
        // 若按物理像素上报会因缩放比而算高(125% 下多出 25%)。保持单位单一来源。
        // 用布局尺寸(offsetHeight,含边框)算:实机核对 header+footer+洞口 = innerHeight
        chromeCss: Math.max(0, window.innerHeight - r.height),
      })
      // 洞口尺寸收敛:仅用于"设为悬浮窗区域"时按目标洞口大小换算窗口尺寸
      const want = wantHoleRef.current
      if (want) {
        const off = Math.abs(r.width - want.w) > 3 || Math.abs(r.height - want.h) > 3
        if (off && triesRef.current < 5) {
          triesRef.current += 1
          const need = Math.max(120, want.h + (window.innerHeight - r.height))
          setTimeout(() => call('resize_main', want.w, need), 50)
        } else {
          wantHoleRef.current = null
          triesRef.current = 0
        }
      }
    }
    reportRef.current = report
    report()
    const ro = new ResizeObserver(report)
    ro.observe(el)
    window.addEventListener('resize', report)
    return () => { ro.disconnect(); window.removeEventListener('resize', report) }
  }, [])

  // 后端事件:截图时隐藏洞口边框 / 快捷键触发识别 / 模式切换后重新上报洞口 /
  // "设为悬浮窗区域"按洞口尺寸换算窗口尺寸
  useEffect(() => {
    const onEvent = (e) => {
      const ev = e.detail
      if (ev.type === 'hideBorder') { setBorderHidden(!!ev.value); setTimeout(() => reportRef.current(), 60) }
      if (ev.type === 'config') {
        setTimeout(() => reportRef.current(), 80)
        const holeW = ev.config?.window?.holeWidth
        const holeH = ev.config?.window?.holeHeight
        if (ev.applyHole && holeW && holeH) {
          // holeWidth/holeHeight 存物理像素;resize_main 用 CSS 像素,这里换算后收敛
          const k = window.devicePixelRatio || 1
          wantHoleRef.current = { w: Math.round(holeW / k), h: Math.round(holeH / k) }
          triesRef.current = 0
          setTimeout(() => reportRef.current(), 60)
        }
      }
      if (ev.type === 'hotkeyCapture') run()
    }
    window.addEventListener('ocr-event', onEvent)
    return () => window.removeEventListener('ocr-event', onEvent)
  })

  const defaultQuestion = cfg.behavior?.default_question || '请回答识别到的内容'

  const run = () => {
    const q = question.trim()
    if (!q) toast(`未填写提问,将按默认指令执行:${defaultQuestion}`)
    // 用 offset*(布局尺寸)而不是 getBoundingClientRect:切换动画的 transform 会让
    // rect 带上偏移,截出来的区域就会整体位移几像素。
    const el = holeRef.current
    const r = {
      x: el.offsetLeft, y: el.offsetTop, w: el.offsetWidth, h: el.offsetHeight,
      dpr: window.devicePixelRatio,
    }
    call('run_pipeline_rect', r, q)
  }

  const toggleTop = async () => {
    const next = !topmost
    setTopmost(next)
    await call('set_topmost', next)
    toast(next ? '已置顶' : '已取消置顶')
  }

  const toggleOcr = async (cloud) => {
    if (!cloud) {
      const st = await call('local_models_status')
      const ocrReady = st?.tiers?.ocr?.find((t) => t.key === st?.current?.ocr)?.ready ?? st?.ocr?.ready
      if (!ocrReady) {
        dl.ask('ocr', {
          title: '端侧识别需要下载 OCR 模型',
          detail: 'RapidOCR 检测/识别/方向模型(PP-OCRv4)',
          size: '约 16 MB',
          onDone: async () => {
            await call('set_config_value', 'ocr.mode', 'local')
            await app.reload()
            toast('已切换为端侧识别(离线)')
          },
        })
        return
      }
    }
    await call('set_config_value', 'ocr.mode', cloud ? 'cloud' : 'local')
    await app.reload()
    toast(cloud ? '识别:云端' : '识别:端侧(离线)')
  }

  const copy = async () => {
    const text = result?.error ? '' : (result?.answer || '')
    const ok = await call('copy_text', text)
    toast(ok ? '已复制回答' : '复制失败', ok ? 'ok' : 'danger')
  }

  // Key 配置状态随 cfg 变化:在设置里填好 Key 并关闭后,主界面状态立即变为"已配置"
  useEffect(() => {
    if (status.tone === 'working' || status.tone === 'danger') return
    setStatus({
      text: modelReady ? '就绪 · Key 已配置' : '就绪 · Key 未配置',
      tone: modelReady ? 'idle' : 'warn',
    })
  }, [modelReady])

  const modeTone = { idle: 'ok', working: 'warn', ok: 'ok', danger: 'danger' }[status.tone] || 'muted'
  const ocrCloud = (cfg.ocr?.mode || 'cloud') === 'cloud'

  // 顶栏密度:宽窗口单行居中;窄窗口先收起模式文字、再折成两行,避免控件互相压住。
  // (这类问题只能靠实测宽度决定,写死一个值会在不同字号/主题下失效)
  const [density, setDensity] = useState('full')
  useEffect(() => {
    const on = () => {
      const w = window.innerWidth
      const k = Number(cfg.ui?.fontSize ?? 13) / 13          // 字号越大越早降级
      const wide = 900 * k
      const roomy = 640 * k        // 低于 640 才折行;640-900 靠"收起模式文字"省出空间
      setDensity(w >= wide ? 'full' : w >= roomy ? 'compact' : 'stacked')
    }
    on()
    window.addEventListener('resize', on)
    return () => window.removeEventListener('resize', on)
  }, [cfg.ui?.fontSize])

  return (
    <div className="window-shell view-overlay h-full flex flex-col overflow-hidden mode-enter relative"
         style={{ background: 'var(--c-bg)' }}>
      {/* 窗口可拖边缩放(问题1:之前误把缩放热区一起删了,只该删尺寸输入框)。
          拖边只改变窗口大小,洞口会随之自适应;缩放结果会写回配置。 */}
      <ResizeHandles which="overlay" onStart={() => { wantHoleRef.current = null }} />
      {/* ================= 顶部:单行工具栏(可拖动) =================
          布局:左=品牌与窗口动作;中=模式切换 + 引擎开关 + 模型名(整体居中);
          三者都不换行,窄窗口下由模型名先收缩,避免互相压住。 */}
      <header className="panel shrink-0 h-11 px-2.5 flex items-center gap-2 drag-handle"
              data-density={density} {...dragHeader}>
        {/* 左:品牌图标(放大),不参与挤压 */}
        <span className="toolbar-group shrink-0" title="OCR 助手"><Logo size={28} /></span>
        {/* 中:模式切换 + 云端/本地 + 模型名。
             有富余时在「logo 与右侧控件之间」居中;空间不足时靠左排布(向左移动),
             宁可贴着 logo 也不与右侧控件重叠。 */}
        <span className="topbar-center flex items-center justify-center gap-2 whitespace-nowrap min-w-0 flex-1">
          <span data-guide="mode" className="toolbar-group shrink-0">
            <IconSeg size="sm" value="overlay" options={MODES} onChange={(m) => app.setMode(m)} />
          </span>
          <span data-guide="engine" className="flex items-center shrink-0">
            <EngineSwitch cloud={(cfg.ocr?.mode || 'cloud') === 'cloud'} onChange={toggleOcr}
                          tips={['云端', '本地']} />
          </span>
          <Tip text="点击打开设置,切换模型/平台">
            <button type="button" className="model-chip no-drag" data-guide="model"
                    onClick={() => call('open_settings')}>
              <span className="w-1.5 h-1.5 rounded-full shrink-0"
                    style={{ background: modelReady ? 'var(--c-ok)' : 'var(--c-warn)' }} />
              <span className="truncate">{modelName}</span>
            </button>
          </Tip>
        </span>
        {/* 右:窗口动作贴最右,始终可点(按钮之间的空隙仍可拖动窗口) */}
        <span className="toolbar-group shrink-0">
          <IconBtn icon="info" tip="新手教程" onClick={() => call('guide_start', 'overlay')} />
          <IconBtn icon="pin" tip={topmost ? '取消置顶' : '窗口置顶'} active={topmost} onClick={toggleTop} />
          <IconBtn icon="settings" tip="设置" onClick={() => call('open_settings')} />
          <IconBtn icon="power" tip="退出(Ctrl+Q)" danger onClick={() => app.quit()} />
        </span>
      </header>

      {/* ================= 中部:透明洞口(鼠标可穿透,可透看后方) ================= */}
      <div className="flex-1 min-h-0">
        <div
          ref={holeRef}
          data-guide="hole"
          className="hole-frame w-full h-full"
          style={{
            border: borderHidden ? 'none' : `2px ${cfg.ui?.holeStyle || 'dashed'} ${cfg.ui?.holeColor || '#ff5252'}`,
            borderRadius: cfg.ui?.holeRadius ?? 4,
          }}
        />
      </div>

      {/* ================= 底部:操作 + 结果 ================= */}
      <footer className={`panel shrink-0 border-t px-2.5 space-y-2 ${small ? 'py-1.5' : 'py-2.5'}`}>
        <div className="flex items-start gap-2">
          <span data-guide="qbox" className="flex-1 min-w-0">
            <QBox value={question} onChange={setQuestion} className="no-drag"
                  onSubmit={run}
                  placeholder={`提问/指令(Enter 识别;留空则默认:${defaultQuestion})`} />
          </span>
          {/* 操作列:最小宽度保证"识别 ↔ 处理中"切换时宽度稳定,又不至于把文字挤换行 */}
          <div className="flex flex-col gap-1.5 w-[84px] shrink-0">
            <span data-guide="run">
              <Btn primary icon={busy ? undefined : 'scan'}
                   className="w-full whitespace-nowrap !px-2" disabled={busy} onClick={run}>
                {busy ? '处理中' : '识别'}
              </Btn>
            </span>
            {!small && (
              <Tip text="翻译模式(无洞口,结果区更大)">
                <Btn icon="translate" className="w-full" onClick={() => app.setMode('translate')}>翻译</Btn>
              </Tip>
            )}
          </div>
        </div>

        <div className="flex items-center gap-2 flex-wrap drag-handle" {...dragFooter}>
          {!small && (
            <>
              <IconBtn icon="snip" tip="重新框选区域(可设为悬浮窗区域)" onClick={() => app.startSnip()} />
              <IconBtn icon="copy" tip="复制回答" onClick={copy} />
              <IconBtn icon="trash" tip="清空结果" onClick={() => app.setResult(null)} />
            </>
          )}
        </div>

        {!small && (
          <div data-guide="result" className="result-split max-h-[30vh] overflow-auto pr-0.5">
            <section className="result-pane">
              <div className="result-pane-head">
                <Icon name="image" size={13} />
                <span>识别结果</span>
                <span className="flex-1" />
                <span className="hint">{(result?.ocr_text || '').length} 字</span>
              </div>
              <div className="result-body result-body-quiet text-[12px] max-h-40">
                {result?.ocr_text || '—'}
              </div>
            </section>
            <section className="result-pane">
              <div className="result-pane-head">
                <Icon name="wand" size={13} />
                <span>回答</span>
                <span className="flex-1" />
                {result?.answer_time > 0 && <span className="hint">{result.answer_time.toFixed(1)}s</span>}
              </div>
              {result?.error ? (
                <div className="result-body result-body-error flex items-start gap-2 text-[12.5px]">
                  <Icon name="alert" size={14} className="mt-0.5 shrink-0" />
                  <span className="break-anywhere">{result.error}</span>
                </div>
              ) : (
                <div className="result-body text-[13px] max-h-40 selectable">
                  {result?.answer || '—'}
                </div>
              )}
            </section>
          </div>
        )}
      </footer>

      {/* ================= 状态栏(问题7):置于窗口最底部,与翻译模式一致 ================= */}
      <div className="status-bar" data-guide="status">
        <Pill tone={modeTone}>{small ? status.text.slice(0, 6) : status.text}</Pill>
        {!small && (
          <>
            <span className="stat-chip">识别 <b>{ocrCloud ? '云端' : '端侧'}</b></span>
            <span className="stat-chip">模型 <b>{modelName}</b></span>
            {result && !result.error && (
              <>
                <span className="stat-chip">来源 <b>{result.source || '—'}</b></span>
                <span className="stat-chip">OCR <b>{result.ocr_time?.toFixed(1) || '0.0'}s</b></span>
                <span className="stat-chip">回答 <b>{result.answer_time?.toFixed(1) || '0.0'}s</b></span>
                {result.task === 'translate' && <span className="stat-chip">任务 <b>翻译</b></span>}
              </>
            )}
          </>
        )}
        <span className="flex-1" />
        {!small && <span className="hint">Ctrl+F1 识别 · Ctrl+4 翻译</span>}
      </div>
      <Guide mode="overlay" open={guide.open} onClose={guide.stop} />
      <QuitDialog mode="overlay" />
    </div>
  )
}
