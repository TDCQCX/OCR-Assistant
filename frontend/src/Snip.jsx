import React, { useEffect, useState } from 'react'
import { call } from './bridge'
import { applyTheme, resolveTheme } from './theme'
import Guide, { useGuide } from './Guide'
import { Btn, EngineSwitch, Icon, LangPair, Logo, QBox } from './ui'

/** 自由截图模式:全屏遮罩 + 拖拽框选 → 识别 / 翻译 / 设为悬浮窗区域 */
export default function Snip() {
  const [sel, setSel] = useState(null)
  const [start, setStart] = useState(null)
  const [dragging, setDragging] = useState(false)
  const [cfg, setCfg] = useState(null)
  const [langs, setLangs] = useState([])
  const [question, setQuestion] = useState('')
  const guide = useGuide('snip')

  useEffect(() => {
    call('get_state').then((s) => {
      setCfg(s.config)
      setQuestion(s.config?.behavior?.default_question || '请回答识别到的内容')
      applyTheme(resolveTheme(s.config.ui), s.config.ui)
    })
    call('languages').then((r) => setLangs(r.list || []))
  }, [])

  useEffect(() => {
    const onKey = (e) => {
      if (e.key === 'Escape') call('cancel_snip')
      if (e.key === 'Enter' && sel) confirm('run')
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [sel])

  const down = (e) => {
    if (e.button !== 0) return
    setStart({ x: e.clientX, y: e.clientY })
    setSel(null)
    setDragging(true)
  }
  const move = (e) => {
    if (!dragging || !start) return
    const x = Math.min(start.x, e.clientX)
    const y = Math.min(start.y, e.clientY)
    const w = Math.abs(e.clientX - start.x)
    const h = Math.abs(e.clientY - start.y)
    setSel({ x, y, w, h })
  }
  const up = () => setDragging(false)

  const confirm = (action) => {
    if (!sel || sel.w < 8 || sel.h < 8) return
    call('finish_snip', { x: sel.x, y: sel.y, w: sel.w, h: sel.h, dpr: window.devicePixelRatio, action },
         question)
  }

  const tr = cfg?.translate || {}
  const setTr = async (patch) => {
    const next = { ...tr, ...patch }
    setCfg({ ...cfg, translate: next })
    for (const [k, v] of Object.entries(patch)) {
      await call('set_config_value', `translate.${k}`, v)  // eslint-disable-line no-await-in-loop
    }
  }
  const toggleOcr = async (cloud) => {
    await call('set_config_value', 'ocr.mode', cloud ? 'cloud' : 'local')
    setCfg({ ...cfg, ocr: { ...(cfg.ocr || {}), mode: cloud ? 'cloud' : 'local' } })
  }

  const shade = 'rgba(0,0,0,0.45)'
  const active = sel && sel.w > 4 && sel.h > 4

  return (
    <div className="h-full w-full relative" onMouseDown={down} onMouseMove={move} onMouseUp={up}>
      {/* 遮罩:四块阴影围出选区 */}
      {!active && <div className="absolute inset-0" style={{ background: shade }} />}
      {active && (
        <>
          <div className="absolute" style={{ background: shade, left: 0, top: 0, right: 0, height: sel.y }} />
          <div className="absolute" style={{ background: shade, left: 0, top: sel.y + sel.h, right: 0, bottom: 0 }} />
          <div className="absolute" style={{ background: shade, left: 0, top: sel.y, width: sel.x, height: sel.h }} />
          <div className="absolute" style={{ background: shade, left: sel.x + sel.w, top: sel.y, right: 0, height: sel.h }} />
          <div
            className="absolute pointer-events-none"
            style={{
              left: sel.x, top: sel.y, width: sel.w, height: sel.h,
              border: `2px solid ${cfg?.ui?.holeColor || '#4c8dff'}`,
              borderRadius: 4,
            }}
          />
          {/* 尺寸提示 */}
          <div
            className="absolute px-2 py-1 rounded-ctl text-[12px] pointer-events-none"
            style={{ left: sel.x, top: Math.max(0, sel.y - 30), background: 'var(--c-panel)', border: '1px solid var(--c-line)', color: 'var(--c-fg)' }}
          >
            {Math.round(sel.w)} × {Math.round(sel.h)}
          </div>
          {/* 操作条:识别 / 翻译 / 设为悬浮窗区域,并内嵌引擎开关与提问输入 */}
          <div
            className="absolute rounded-card border shadow-xl p-2.5 space-y-2"
            style={{
              left: Math.max(8, Math.min(sel.x, window.innerWidth - 560)),
              top: Math.min(sel.y + sel.h + 8, window.innerHeight - 170),
              width: 540,
              background: 'var(--c-panel)', borderColor: 'var(--c-line)',
            }}
            onMouseDown={(e) => e.stopPropagation()}
          >
            <div className="flex items-center gap-2 flex-wrap">
              <Btn primary icon="scan" onClick={() => confirm('run')}>识别</Btn>
              <Btn icon="translate" onClick={() => confirm('translate')}>翻译此区域</Btn>
              <Btn icon="overlay" onClick={() => confirm('region')}>设为悬浮窗区域</Btn>
              <span className="flex-1" />
              <Btn icon="close" onClick={() => call('cancel_snip')}>取消</Btn>
            </div>
            <div className="flex items-center gap-2 flex-wrap">
              <EngineSwitch cloud={(cfg?.ocr?.mode || 'cloud') === 'cloud'} onChange={toggleOcr}
                            label="识别" tips={['云端', '本地']} />
              <EngineSwitch cloud={(tr.mode || 'cloud') === 'cloud'} onChange={(v) => setTr({ mode: v ? 'cloud' : 'local' })}
                            label="翻译" tips={['云端', '本地']} />
              <span className="flex-1" />
              <LangPair languages={langs} source={tr.source_lang || '自动检测'} target={tr.target_lang || '中文'}
                        onChange={(s, t) => setTr({ source_lang: s, target_lang: t })} />
            </div>
            <QBox value={question} onChange={setQuestion} rows={2}
                  presets={cfg?.behavior?.question_presets} history={cfg?.behavior?.question_history}
                  placeholder="提问/指令(Enter 识别;留空则默认指令)" />
          </div>
        </>
      )}

      {/* 顶部提示 */}
      {!active && (
        <div
          className="absolute left-1/2 -translate-x-1/2 top-8 px-4 py-2 rounded-card border shadow-xl text-center"
          data-guide="snip-hint"
          style={{ background: 'var(--c-panel)', borderColor: 'var(--c-line)' }}
        >
          <div className="flex items-center justify-center gap-2 font-semibold">
            <Logo size={18} />
            自由截图模式
          </div>
          <div className="hint mt-1">按住鼠标左键拖拽框选区域 · 松开后可识别 / 翻译 / 设为悬浮窗区域 · Esc 取消</div>
          <div className="flex items-center justify-center gap-2 mt-2" data-guide="snip-actions">
            <span className="chip">识别</span>
            <span className="chip">翻译此区域</span>
            <span className="chip">设为悬浮窗区域</span>
            <span className="chip">Esc 取消</span>
          </div>
        </div>
      )}
      <Guide mode="snip" open={guide.open} onClose={guide.stop} />
    </div>
  )
}
