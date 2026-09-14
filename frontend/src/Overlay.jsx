import React, { useEffect, useRef, useState } from 'react'
import { call } from './bridge'
import { useApp } from './main'
import { Btn, Collapse, Icon, IconBtn, Pill, Segmented, useToast, useWindowDrag } from './ui'

const MODES = [
  { value: 'overlay', label: '悬浮窗', icon: 'overlay', tip: '悬浮窗模式(Ctrl+1)' },
  { value: 'snip', label: '自由截图', icon: 'snip', tip: '自由截图模式(Ctrl+Shift+A)' },
  { value: 'mini', label: '迷你条', icon: 'mini', tip: '迷你条模式(Ctrl+2)' },
]

export default function Overlay() {
  const app = useApp()
  const { cfg, status, result, busy } = app
  const toast = useToast()
  const holeRef = useRef(null)
  const dragHeader = useWindowDrag('overlay')
  const dragFooter = useWindowDrag('overlay')
  const [question, setQuestion] = useState(cfg.behavior?.default_question || '请给出该题目的答案')
  const [providers, setProviders] = useState([])
  const [active, setActive] = useState(cfg.active_provider)
  const [borderHidden, setBorderHidden] = useState(false)
  const [size, setSize] = useState({ w: cfg.window?.width || 640, h: cfg.window?.height || 680 })
  const [topmost, setTopmost] = useState(cfg.window?.always_on_top !== false)

  useEffect(() => { call('list_providers').then((p) => { setProviders(p.list || []); setActive(p.active) }) }, [])

  // 把洞口(OCR 区域)几何上报后端,用于把该区域从窗口"输入/绘制区域"中挖掉 → 鼠标可穿透
  const reportRef = useRef(() => {})
  useEffect(() => {
    const el = holeRef.current
    if (!el) return
    const report = () => {
      const r = el.getBoundingClientRect()
      const cs = getComputedStyle(el)
      const bw = parseFloat(cs.borderTopWidth) || 0
      const dpr = window.devicePixelRatio || 1
      call('set_hole_region', {
        x: (r.x + bw) * dpr,
        y: (r.y + bw) * dpr,
        w: Math.max(0, r.width - 2 * bw) * dpr,
        h: Math.max(0, r.height - 2 * bw) * dpr,
      })
    }
    reportRef.current = report
    report()
    const ro = new ResizeObserver(report)
    ro.observe(el)
    window.addEventListener('resize', report)
    return () => { ro.disconnect(); window.removeEventListener('resize', report) }
  }, [])

  // 后端事件:截图时隐藏洞口边框 / 快捷键触发识别 / 模式切换后重新上报洞口
  useEffect(() => {
    const onEvent = (e) => {
      const ev = e.detail
      if (ev.type === 'hideBorder') { setBorderHidden(!!ev.value); setTimeout(() => reportRef.current(), 60) }
      if (ev.type === 'config') setTimeout(() => reportRef.current(), 80)
      if (ev.type === 'hotkeyCapture') run()
    }
    window.addEventListener('ocr-event', onEvent)
    return () => window.removeEventListener('ocr-event', onEvent)
  })

  const run = () => {
    const r = holeRef.current.getBoundingClientRect()
    call('run_pipeline_rect', { x: r.x, y: r.y, w: r.width, h: r.height, dpr: window.devicePixelRatio }, question)
  }

  const resize = async (w, h) => {
    setSize({ w, h })
    await call('resize_main', w, h)
  }

  const switchProvider = async (id) => {
    setActive(id)
    await call('set_active_provider', id)
    const s = await call('get_state')
    app.setCfg(s.config)
    app.setStatus({ text: s.key_ready ? '就绪 · Key 已配置' : '就绪 · Key 未配置', tone: s.key_ready ? 'idle' : 'warn' })
  }

  const toggleTop = async () => {
    const next = !topmost
    setTopmost(next)
    await call('set_topmost', next)
    toast(next ? '已置顶' : '已取消置顶')
  }

  const copy = () => {
    navigator.clipboard.writeText(result?.error ? '' : (result?.answer || ''))
    toast('已复制回答')
  }

  const modeTone = { idle: 'ok', working: 'warn', ok: 'ok', danger: 'danger' }[status.tone] || 'muted'

  return (
    <div className="h-full flex flex-col overflow-hidden">
      {/* ================= 顶部:图标工具栏(可拖动) ================= */}
      <header className="panel shrink-0 h-10 px-2 flex items-center gap-2 drag-handle" {...dragHeader}>
        <span className="logo-o w-[22px] h-[22px] text-[11px] no-drag" title="OCR 助手">O</span>
        <Segmented size="sm" value="overlay" options={MODES.map((m) => ({ ...m, iconOnly: true }))}
                   onChange={(m) => app.setMode(m)} />
        <span className="flex-1" />
        <select className="ctl !w-[110px] !h-7 !text-[12px] no-drag" value={active} title="当前 AI 平台"
                onChange={(e) => switchProvider(e.target.value)}>
          {providers.map((p) => (
            <option key={p.id} value={p.id}>{p.name}{p.ready ? '' : '(未配置)'}</option>
          ))}
        </select>
        <IconBtn icon="pin" tip={topmost ? '取消置顶' : '窗口置顶'} active={topmost} onClick={toggleTop} />
        <IconBtn icon="settings" tip="设置" onClick={() => call('open_settings')} />
        <IconBtn icon="power" tip="退出(Ctrl+Q)" danger onClick={() => app.quit()} />
      </header>

      {/* ================= 中部:透明洞口(鼠标可穿透,可透看后方) ================= */}
      <div className="flex-1 min-h-0">
        <div
          ref={holeRef}
          className="w-full h-full"
          style={{
            border: borderHidden ? 'none' : `2px ${cfg.ui?.holeStyle || 'dashed'} ${cfg.ui?.holeColor || '#ff5252'}`,
            borderRadius: cfg.ui?.holeRadius ?? 4,
          }}
        />
      </div>

      {/* ================= 底部:操作 + 结果 ================= */}
      <footer className="panel shrink-0 border-t px-2.5 py-2 space-y-2">
        <div className="flex items-center gap-2">
          <input
            className="ctl flex-1"
            value={question}
            placeholder="提问/指令(留空则默认:请给出该题目的答案)"
            onChange={(e) => setQuestion(e.target.value)}
          />
          <Btn primary icon="scan" disabled={busy} onClick={run}>{busy ? '处理中' : '识别'}</Btn>
          <IconBtn icon="snip" tip="重新框选区域(可设为悬浮窗区域)" onClick={() => app.startSnip()} />
          <IconBtn icon="copy" tip="复制回答" onClick={copy} />
          <IconBtn icon="trash" tip="清空结果" onClick={() => app.setResult(null)} />
          <span className="w-px h-5 mx-0.5" style={{ background: 'var(--c-line)' }} />
          <Icon name="grid" size={14} className="text-muted" />
          <input type="number" className="ctl !w-14 text-right" value={size.w} title="洞口宽度"
                 onChange={(e) => setSize({ ...size, w: +e.target.value })} onBlur={() => resize(size.w, size.h)} />
          <span className="text-muted text-[12px]">×</span>
          <input type="number" className="ctl !w-14 text-right" value={size.h} title="洞口高度"
                 onChange={(e) => setSize({ ...size, h: +e.target.value })} onBlur={() => resize(size.w, size.h)} />
        </div>

        <div className="flex items-center gap-2 flex-wrap drag-handle" {...dragFooter}>
          <Pill tone={modeTone}>{status.text}</Pill>
          {result && !result.error && (
            <>
              <span className="chip">{result.qtype_name}</span>
              <span className="chip">来源: {result.source}</span>
              <span className="chip">OCR: {result.ocr_time?.toFixed(1)}s</span>
              <span className="chip">回答: {result.answer_time?.toFixed(1)}s</span>
            </>
          )}
        </div>

        <div className="grid grid-cols-2 gap-2.5 max-h-[30vh] overflow-auto">
          <Collapse title="识别结果" badge={<span className="hint">{(result?.ocr_text || '').length} 字</span>}>
            <pre className="whitespace-pre-wrap text-[12px] leading-relaxed inset p-2 max-h-40 overflow-auto">
              {result?.ocr_text || '—'}
            </pre>
          </Collapse>
          <Collapse title="回答">
            {result?.error ? (
              <div className="inset p-2 flex items-start gap-2 text-[12.5px]" style={{ color: 'var(--c-danger)' }}>
                <Icon name="alert" size={14} className="mt-0.5" />
                <span>{result.error}</span>
              </div>
            ) : (
              <pre className="whitespace-pre-wrap text-[13px] leading-relaxed inset p-2 max-h-40 overflow-auto">
                {result?.answer || '—'}
              </pre>
            )}
          </Collapse>
        </div>
      </footer>
    </div>
  )
}
