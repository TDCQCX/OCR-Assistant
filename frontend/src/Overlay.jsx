import React, { useEffect, useRef, useState } from 'react'
import { call } from './bridge'
import { useApp } from './main'
import { Btn, Collapse, Pill, Segmented, useToast } from './ui'

const MODES = [
  { value: 'overlay', label: '悬浮窗' },
  { value: 'snip', label: '自由截图' },
  { value: 'mini', label: '迷你条' },
]

export default function Overlay() {
  const app = useApp()
  const { cfg, status, result, busy } = app
  const toast = useToast()
  const holeRef = useRef(null)
  const [question, setQuestion] = useState(cfg.behavior?.default_question || '请给出该题目的答案')
  const [providers, setProviders] = useState([])
  const [active, setActive] = useState(cfg.active_provider)
  const [borderHidden, setBorderHidden] = useState(false)
  const [size, setSize] = useState({ w: cfg.window?.width || 640, h: cfg.window?.height || 680 })

  useEffect(() => { call('list_providers').then((p) => { setProviders(p.list || []); setActive(p.active) }) }, [])

  // 后端事件:截图时隐藏洞口边框 / 快捷键触发识别
  useEffect(() => {
    const onEvent = (e) => {
      const ev = e.detail
      if (ev.type === 'hideBorder') setBorderHidden(!!ev.value)
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

  const modeTone = { idle: 'ok', working: 'warn', ok: 'ok', danger: 'danger' }[status.tone] || 'muted'

  return (
    <div className="h-full flex flex-col overflow-hidden">
      {/* ================= 顶部:功能与设置区 ================= */}
      <header
        className="pywebview-drag-region shrink-0 px-3 py-2 flex items-center gap-2 border-b border-line"
        style={{ background: 'var(--c-panel)' }}
      >
        <span className="font-bold px-3 py-1 rounded-card text-accentfg text-[15px] tracking-wide" style={{ background: 'var(--c-accent)' }}>
          OCR 助手
        </span>
        <span className="hint hidden md:block">截图识别 · 智能答题</span>
        <span className="flex-1" />

        <Segmented size="sm" value="overlay" options={MODES} onChange={(m) => app.setMode(m)} />

        <select className="ctl !w-auto !py-1" value={active} onChange={(e) => switchProvider(e.target.value)}>
          {providers.map((p) => (
            <option key={p.id} value={p.id}>{p.name}{p.ready ? '' : '(未配置)'}</option>
          ))}
        </select>

        <Btn title="设置" onClick={() => call('open_settings')}>设置</Btn>
        <Btn title="退出" onClick={() => app.quit()}>退出</Btn>
      </header>

      {/* ================= 中部:透明洞口(可透看后方) ================= */}
      <div className="flex-1 min-h-0 p-0">
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
      <footer className="shrink-0 border-t border-line px-3 py-2 space-y-2" style={{ background: 'var(--c-panel)' }}>
        <div className="flex items-center gap-2">
          <input
            className="ctl flex-1"
            value={question}
            placeholder="提问/指令(留空则默认:请给出该题目的答案)"
            onChange={(e) => setQuestion(e.target.value)}
          />
          <Btn primary disabled={busy} onClick={run}>{busy ? '处理中…' : '截图并识别'}</Btn>
          <Btn onClick={() => app.startSnip()} title="全屏拖框选择区域,可设为悬浮窗区域">重新选区</Btn>
          <Btn onClick={() => { navigator.clipboard.writeText(answerText(result)); toast('已复制') }}>复制</Btn>
          <Btn onClick={() => app.setResult(null)}>清空</Btn>
          <span className="hint">洞口</span>
          <input type="number" className="ctl !w-16 text-right" value={size.w}
                 onChange={(e) => setSize({ ...size, w: +e.target.value })} onBlur={() => resize(size.w, size.h)} />
          <span className="hint">×</span>
          <input type="number" className="ctl !w-16 text-right" value={size.h}
                 onChange={(e) => setSize({ ...size, h: +e.target.value })} onBlur={() => resize(size.w, size.h)} />
        </div>

        <div className="flex items-center gap-2 flex-wrap">
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

        <div className="grid grid-cols-2 gap-3 max-h-[30vh] overflow-auto">
          <Collapse title="识别结果" badge={<span className="hint">{(result?.ocr_text || '').length} 字</span>}>
            <pre className="whitespace-pre-wrap text-[12px] leading-relaxed bg-bg/60 border border-line rounded-ctl p-2 max-h-40 overflow-auto">
              {result?.ocr_text || '—'}
            </pre>
          </Collapse>
          <Collapse title="回答">
            <pre className="whitespace-pre-wrap text-[13px] leading-relaxed bg-bg/60 border border-line rounded-ctl p-2 max-h-40 overflow-auto">
              {result?.error ? `❌ ${result.error}` : result?.answer || '—'}
            </pre>
          </Collapse>
        </div>
      </footer>
    </div>
  )
}

function answerText(result) {
  if (!result) return ''
  return result.error ? '' : result.answer || ''
}
