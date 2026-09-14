import React, { useEffect, useState } from 'react'
import { call } from './bridge'
import { applyTheme, resolveTheme } from './theme'
import { Btn } from './ui'

/** 自由截图模式:全屏遮罩 + 拖拽框选 → 识别 / 设为悬浮窗区域 */
export default function Snip() {
  const [sel, setSel] = useState(null)
  const [start, setStart] = useState(null)
  const [dragging, setDragging] = useState(false)
  const [cfg, setCfg] = useState(null)

  useEffect(() => {
    call('get_state').then((s) => { setCfg(s.config); applyTheme(resolveTheme(s.config.ui)) })
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
    call('finish_snip', { x: sel.x, y: sel.y, w: sel.w, h: sel.h, dpr: window.devicePixelRatio, action })
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
          {/* 操作条 */}
          <div
            className="absolute flex items-center gap-2 px-3 py-2 rounded-card border shadow-xl"
            style={{
              left: Math.min(sel.x, window.innerWidth - 330),
              top: Math.min(sel.y + sel.h + 8, window.innerHeight - 60),
              background: 'var(--c-panel)', borderColor: 'var(--c-line)',
            }}
            onMouseDown={(e) => e.stopPropagation()}
          >
            <Btn primary onClick={() => confirm('run')}>识别</Btn>
            <Btn onClick={() => confirm('region')}>设为悬浮窗区域</Btn>
            <Btn onClick={() => call('cancel_snip')}>取消</Btn>
          </div>
        </>
      )}

      {/* 顶部提示 */}
      {!active && (
        <div
          className="absolute left-1/2 -translate-x-1/2 top-8 px-4 py-2 rounded-card border shadow-xl text-center"
          style={{ background: 'var(--c-panel)', borderColor: 'var(--c-line)' }}
        >
          <div className="font-bold">自由截图模式</div>
          <div className="hint mt-1">按住鼠标左键拖拽框选区域 · Enter 识别 · Esc 取消</div>
        </div>
      )}
    </div>
  )
}
