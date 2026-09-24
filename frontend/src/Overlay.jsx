import React, { useEffect, useRef, useState } from 'react'
import { call } from './bridge'
import { useApp } from './main'
import {
  Btn, Collapse, EngineSwitch, Icon, IconBtn, IconSeg, Pill, QBox, ResizeHandles, Tip,
  useDownloader, useSmallWindow, useToast, useWindowDrag,
} from './ui'

const MODES = [
  { value: 'overlay', label: '悬浮窗', icon: 'overlay' },
  { value: 'translate', label: '翻译', icon: 'translate' },
  { value: 'snip', label: '框选', icon: 'snip' },
  { value: 'mini', label: '迷你条', icon: 'mini' },
]

export default function Overlay() {
  const app = useApp()
  const { cfg, status, result, busy } = app
  const toast = useToast()
  const dl = useDownloader()
  const holeRef = useRef(null)
  const dragHeader = useWindowDrag('overlay')
  const dragFooter = useWindowDrag('overlay')
  const { question, setQuestion } = app  // 全局共享:各模式输入框内容保持同步
  const [borderHidden, setBorderHidden] = useState(false)
  const [size, setSize] = useState({ w: cfg.window?.width || 640, h: cfg.window?.height || 680 })
  const [topmost, setTopmost] = useState(cfg.window?.always_on_top !== false)
  const small = useSmallWindow()

  useEffect(() => {
    call('last_result').then((r) => { if (r && (r.answer || r.ocr_text)) app.setResult(r) })
  }, [])

  // 顶部只显示当前模型与状态:直接由 cfg 派生,设置窗口改动后会随 config 事件立即刷新
  const curProv = (cfg.providers || []).find((p) => p.id === cfg.active_provider) || {}
  const modelName = curProv.model || curProv.name || '未选择模型'
  const modelReady = !!(curProv.api_key || '').trim()

  // 把洞口(OCR 区域)几何上报后端,用于把该区域从窗口"输入/绘制区域"中挖掉 → 鼠标可穿透
  const reportRef = useRef(() => {})
  const chromeRef = useRef(cfg.window?.chromeHeight || 300)
  const editingRef = useRef(false)
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
      })
      // 目标洞口尺寸收敛:面板(尤其底部)高度会随内容换行变化,单次换算会偏小
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
      } else if (!editingRef.current && r.width > 40 && r.height > 40) {
        // 拖边缩放后同步洞口尺寸输入框
        setSize((s) => (Math.abs(s.w - Math.round(r.width)) > 2 || Math.abs(s.h - Math.round(r.height)) > 2
          ? { w: Math.round(r.width), h: Math.round(r.height) } : s))
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
          setSize({ w: holeW, h: holeH })
          wantHoleRef.current = { w: holeW, h: holeH }
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
    const r = holeRef.current.getBoundingClientRect()
    call('run_pipeline_rect', { x: r.x, y: r.y, w: r.width, h: r.height, dpr: window.devicePixelRatio }, q)
  }

  // 输入框填报的是"洞口尺寸":窗口尺寸 = 洞口 + 标题栏/底部面板(并做收敛校正)
  const resize = async (w, h) => {
    setSize({ w, h })
    wantHoleRef.current = { w, h }
    triesRef.current = 0
    await call('resize_main', w, h + chromeRef.current)
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

  return (
    <div className="h-full flex flex-col overflow-hidden mode-enter relative">
      <ResizeHandles which="overlay" onStart={() => { wantHoleRef.current = null }} />
      {/* ================= 顶部:图标工具栏(可拖动) ================= */}
      <header className="panel shrink-0 h-10 px-2 flex items-center gap-2 drag-handle" {...dragHeader}>
        <span className="logo-o w-[22px] h-[22px] text-[11px] no-drag">O</span>
        <IconSeg size="sm" value="overlay" options={MODES} onChange={(m) => app.setMode(m)} />
        <span className="flex-1" />
        <EngineSwitch cloud={(cfg.ocr?.mode || 'cloud') === 'cloud'} onChange={toggleOcr}
                      tips={['云端', '本地']} />
        {/* 只显示当前模型与状态,点击进入设置切换 */}
        <Tip text="点击打开设置,切换模型/平台">
          <button type="button" className="model-chip no-drag" onClick={() => call('open_settings')}>
            <span className="w-1.5 h-1.5 rounded-full shrink-0" style={{ background: modelReady ? 'var(--c-ok)' : 'var(--c-warn)' }} />
            <span className="truncate">{modelName}</span>
          </button>
        </Tip>
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
      <footer className={`panel shrink-0 border-t px-2.5 space-y-2 ${small ? 'py-1.5' : 'py-2'}`}>
        <div className="flex items-start gap-2">
          <QBox value={question} onChange={setQuestion} rows={small ? 1 : 2} className="flex-1 no-drag"
                presets={cfg.behavior?.question_presets} history={cfg.behavior?.question_history}
                placeholder={`提问/指令(留空则默认:${defaultQuestion})`} />
          <div className="flex flex-col gap-1.5">
            <Btn primary icon="scan" disabled={busy} onClick={run}>{busy ? '处理中' : '识别'}</Btn>
            {!small && (
              <Tip text="翻译模式(无洞口,结果区更大)">
                <Btn icon="translate" onClick={() => app.setMode('translate')}>翻译</Btn>
              </Tip>
            )}
          </div>
        </div>

        <div className="flex items-center gap-2 flex-wrap drag-handle" {...dragFooter}>
          <Pill tone={modeTone}>{small ? status.text.slice(0, 6) : status.text}</Pill>
          {!small && result && !result.error && (
            <>
              <span className="chip">{result.qtype_name}</span>
              <span className="chip">来源: {result.source}</span>
              <span className="chip">OCR: {result.ocr_time?.toFixed(1)}s</span>
              <span className="chip">回答: {result.answer_time?.toFixed(1)}s</span>
            </>
          )}
          <span className="flex-1" />
          {!small && (
            <>
              <IconBtn icon="snip" tip="重新框选区域(可设为悬浮窗区域)" onClick={() => app.startSnip()} />
              <IconBtn icon="copy" tip="复制回答" onClick={copy} />
              <IconBtn icon="trash" tip="清空结果" onClick={() => app.setResult(null)} />
              <Icon name="grid" size={14} className="text-muted" />
              <input type="number" className="ctl !w-14 text-right" value={size.w} title="洞口宽度"
                     onFocus={() => { editingRef.current = true }}
                     onChange={(e) => setSize({ ...size, w: +e.target.value })}
                     onBlur={(e) => { editingRef.current = false; resize(+e.target.value, size.h) }} />
              <span className="text-muted text-[12px]">×</span>
              <input type="number" className="ctl !w-14 text-right" value={size.h} title="洞口高度"
                     onFocus={() => { editingRef.current = true }}
                     onChange={(e) => setSize({ ...size, h: +e.target.value })}
                     onBlur={(e) => { editingRef.current = false; resize(size.w, +e.target.value) }} />
            </>
          )}
        </div>

        {!small && (
          <div className="grid grid-cols-2 gap-2.5 max-h-[28vh] overflow-auto">
            <Collapse title="识别结果" badge={<span className="hint">{(result?.ocr_text || '').length} 字</span>}>
              <pre className="whitespace-pre-wrap text-[12px] leading-relaxed inset p-2 max-h-36 overflow-auto">
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
                <pre className="whitespace-pre-wrap text-[13px] leading-relaxed inset p-2 max-h-36 overflow-auto">
                  {result?.answer || '—'}
                </pre>
              )}
            </Collapse>
          </div>
        )}
      </footer>
    </div>
  )
}
