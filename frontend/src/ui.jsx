import React, { createContext, useContext, useEffect, useRef, useState } from 'react'
import { call } from './bridge'

/* ============================ 扁平图标(纯 CSS/SVG,无 emoji) ============================ */
const PATHS = {
  overlay: <><rect x="3" y="4.5" width="18" height="15" rx="2.5" /><rect x="7.5" y="8.5" width="9" height="7" rx="1.2" /></>,
  mini: <><rect x="2.5" y="9" width="19" height="6" rx="3" /><path d="M7 12h4" /></>,
  snip: <path d="M4 9V6.5A2.5 2.5 0 0 1 6.5 4H9M15 4h2.5A2.5 2.5 0 0 1 20 6.5V9M20 15v2.5a2.5 2.5 0 0 1-2.5 2.5H15M9 20H6.5A2.5 2.5 0 0 1 4 17.5V15" />,
  scan: <><path d="M4 8V6a2 2 0 0 1 2-2h2M16 4h2a2 2 0 0 1 2 2v2M20 16v2a2 2 0 0 1-2 2h-2M8 20H6a2 2 0 0 1-2-2v-2" /><path d="M4 12h16" /></>,
  settings: <><circle cx="12" cy="12" r="3.1" /><path d="M12 3.6v2.2M12 18.2v2.2M4.1 12h2.2M17.7 12h2.2M6.4 6.4l1.6 1.6M16 16l1.6 1.6M17.6 6.4L16 8M8 16l-1.6 1.6" /></>,
  close: <path d="M6.5 6.5l11 11M17.5 6.5l-11 11" />,
  power: <><path d="M12 4v8" /><path d="M7.6 7.2a7 7 0 1 0 8.8 0" /></>,
  pin: <><path d="M12 13.5V20" /><path d="M8 4h8l-.9 4.6 2.4 2.4V13H6.5v-2l2.4-2.4z" /></>,
  copy: <><rect x="9" y="9" width="11" height="11" rx="2" /><path d="M15 6.6A2.6 2.6 0 0 0 12.4 4H6a2 2 0 0 0-2 2v6.4A2.6 2.6 0 0 0 6.6 15" /></>,
  trash: <><path d="M4.5 7h15" /><path d="M9.5 7V4.8h5V7" /><path d="M6.5 7l.9 12.2h9.2L17.5 7" /><path d="M10.4 11v5M13.6 11v5" /></>,
  history: <><circle cx="12" cy="12" r="7.8" /><path d="M12 7.8V12l3 1.8" /></>,
  palette: <><path d="M12 4a8 8 0 1 0 0 16c1.6 0 2.2-1 2.2-2.1 0-1-.6-1.9-2.2-1.9h-1.4a2 2 0 0 1 0-4H16a4 4 0 0 0 4-4c0-2.3-3.6-4-8-4z" /><circle cx="8.6" cy="10.2" r="1.2" /></>,
  info: <><circle cx="12" cy="12" r="8.2" /><path d="M12 11v5.2" /><path d="M12 7.9v.2" /></>,
  chip: <><rect x="7" y="7" width="10" height="10" rx="2.2" /><path d="M10 3.4v2.4M14 3.4v2.4M10 18.2v2.4M14 18.2v2.4M3.4 10h2.4M3.4 14h2.4M18.2 10h2.4M18.2 14h2.4" /></>,
  sliders: <><path d="M4 8.5h9M17.5 8.5H20M4 15.5h3M11.5 15.5H20" /><circle cx="15" cy="8.5" r="2" /><circle cx="9" cy="15.5" r="2" /></>,
  plus: <path d="M12 5.5v13M5.5 12h13" />,
  chevron: <path d="M9.5 6.5l5.5 5.5-5.5 5.5" />,
  eye: <><path d="M2.8 12S6.4 5.8 12 5.8 21.2 12 21.2 12 17.6 18.2 12 18.2 2.8 12 2.8 12z" /><circle cx="12" cy="12" r="2.9" /></>,
  eyeOff: <><path d="M4 4l16 16" /><path d="M9.6 5.9A9.9 9.9 0 0 1 12 5.8c5.6 0 9.2 6.2 9.2 6.2a17.6 17.6 0 0 1-3.4 4.2M6.4 7.9A17.3 17.3 0 0 0 2.8 12S6.4 18.2 12 18.2c.9 0 1.8-.2 2.6-.5" /></>,
  folder: <path d="M3.2 7.4A2.2 2.2 0 0 1 5.4 5.2h3.3l1.6 2h8.3a2.2 2.2 0 0 1 2.2 2.2v7a2.2 2.2 0 0 1-2.2 2.2H5.4a2.2 2.2 0 0 1-2.2-2.2z" />,
  link: <><path d="M14.5 4H20v5.5" /><path d="M20 4l-8.6 8.6" /><path d="M18 14v4.2A1.8 1.8 0 0 1 16.2 20H5.8A1.8 1.8 0 0 1 4 18.2V7.8A1.8 1.8 0 0 1 5.8 6H10" /></>,
  refresh: <><path d="M20 12a8 8 0 1 1-2.4-5.7" /><path d="M20 4.4V9h-4.6" /></>,
  alert: <><path d="M12 4.4l8.4 15.2H3.6z" /><path d="M12 10v4M12 16.9v.2" /></>,
  check: <path d="M5.5 12.8l4.2 4.2L18.6 7.4" />,
  image: <><rect x="3.4" y="5" width="17.2" height="14" rx="2.2" /><circle cx="9" cy="10" r="1.6" /><path d="M4 17.4l4.6-4.6 3.4 3.4 2.4-2.4L20 17.4" /></>,
  grid: <><rect x="4" y="4" width="7" height="7" rx="1.6" /><rect x="13" y="4" width="7" height="7" rx="1.6" /><rect x="4" y="13" width="7" height="7" rx="1.6" /><rect x="13" y="13" width="7" height="7" rx="1.6" /></>,
  download: <><path d="M12 4v10" /><path d="M8 10.5l4 4 4-4" /><path d="M5 19.5h14" /></>,
  upload: <><path d="M12 20V10" /><path d="M8 13.5l4-4 4 4" /><path d="M5 4.5h14" /></>,
  text: <><path d="M5 6.5h14M5 12h9M5 17.5h6" /></>,
  link2: <><path d="M5 12h14" /><path d="M12 5v14" /></>,
}

export function Icon({ name, size = 16, className = '', strokeWidth = 1.6 }) {
  const body = PATHS[name] || PATHS.info
  return (
    <svg
      width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor"
      strokeWidth={strokeWidth} strokeLinecap="round" strokeLinejoin="round"
      className={`shrink-0 ${className}`} aria-hidden="true"
    >
      {body}
    </svg>
  )
}

/** 纯图标按钮(悬停显示文字说明) */
export function IconBtn({ icon, tip, active, primary, danger, size = 16, className = '', ...rest }) {
  const tone = primary
    ? 'icon-btn-primary'
    : danger ? 'hover:text-danger' : active ? 'icon-btn-active' : ''
  return (
    <button type="button" title={tip} aria-label={tip}
            className={`icon-btn ${tone} ${className}`} {...rest}>
      <Icon name={icon} size={size} />
    </button>
  )
}

/* ============================ 拖拽窗口(受控,pointerup 必定结束) ============================ */
export function useWindowDrag(which) {
  const st = useRef(null)
  const onPointerDown = (e) => {
    if (e.button !== 0) return
    if (e.target.closest('button,input,select,textarea,a,label,.no-drag')) return
    st.current = { id: e.pointerId, x: e.screenX, y: e.screenY }
    try { e.currentTarget.setPointerCapture(e.pointerId) } catch { /* 忽略 */ }
    call('drag_begin', which, e.screenX, e.screenY)
  }
  const onPointerMove = (e) => {
    if (!st.current || st.current.id !== e.pointerId) return
    call('drag_move', which, e.screenX, e.screenY)
  }
  const end = () => {
    if (!st.current) return
    st.current = null
    call('drag_end', which)
  }
  return {
    onPointerDown, onPointerMove, onPointerUp: end,
    onPointerCancel: end, onLostPointerCapture: end,
  }
}

/* ============================ 基础控件 ============================ */
export function Card({ title, icon, desc, right, children, className = '' }) {
  return (
    <section className={`card p-3.5 animate-fadein ${className}`}>
      {(title || right) && (
        <header className="flex items-center gap-2.5 mb-3">
          {icon && <span className="card-icon"><Icon name={icon} size={15} /></span>}
          <div className="min-w-0">
            {title && <h3 className="font-semibold text-[13.5px] truncate">{title}</h3>}
            {desc && <p className="hint mt-0.5">{desc}</p>}
          </div>
          <div className="flex-1" />
          <div className="flex items-center gap-2">{right}</div>
        </header>
      )}
      {children}
    </section>
  )
}

export function Btn({ primary, danger, ghost, icon, className = '', children, ...rest }) {
  const tone = primary ? 'btn-primary' : danger ? 'btn-danger' : ghost ? 'btn-ghost' : ''
  return (
    <button type="button" className={`btn ${tone} ${className}`} {...rest}>
      {icon && <Icon name={icon} size={15} />}
      {children}
    </button>
  )
}

export function Switch({ checked, onChange, label, hint }) {
  return (
    <label className="flex items-center gap-3 cursor-pointer">
      <button
        type="button"
        onClick={() => onChange(!checked)}
        className="w-11 h-6 rounded-full border transition-colors relative shrink-0"
        style={{
          background: checked ? 'var(--c-accent)' : 'var(--c-sub)',
          borderColor: checked ? 'var(--c-accent)' : 'var(--c-line)',
        }}
      >
        <span
          className="absolute top-[2px] w-[18px] h-[18px] rounded-full transition-all"
          style={{ left: checked ? 22 : 2, background: '#fff', boxShadow: '0 1px 2px rgba(0,0,0,.28)' }}
        />
      </button>
      {(label || hint) && (
        <span className="min-w-0">
          {label && <span className="font-medium">{label}</span>}
          {hint && <span className="hint block">{hint}</span>}
        </span>
      )}
    </label>
  )
}

export function Segmented({ value, options, onChange, size = 'md' }) {
  const pad = size === 'sm' ? 'px-2.5 h-7 text-[12px]' : 'px-3.5 h-8'
  return (
    <div className="seg">
      {options.map((o) => {
        const active = value === o.value
        return (
          <button
            key={o.value}
            type="button"
            title={o.tip || o.label}
            onClick={() => onChange(o.value)}
            className={`seg-item ${pad}`}
            data-active={active ? '1' : '0'}
          >
            {o.icon && <Icon name={o.icon} size={14} />}
            {!o.iconOnly && o.label}
          </button>
        )
      })}
    </div>
  )
}

export function Field({ label, hint, children, width = 130 }) {
  return (
    <div className="inset px-3 py-2">
      <div className="flex items-start gap-3">
        <div className="shrink-0 pt-1.5" style={{ width }}>
          <div className="font-medium">{label}</div>
          {hint && <div className="hint mt-0.5 leading-snug">{hint}</div>}
        </div>
        <div className="flex-1 min-w-0">{children}</div>
      </div>
    </div>
  )
}

export function ColorInput({ value, onChange, title }) {
  return (
    <label className="flex items-center gap-2 cursor-pointer" title={title}>
      <input
        type="color"
        value={value || '#000000'}
        onChange={(e) => onChange(e.target.value)}
        className="w-7 h-7 rounded-ctl border border-line bg-transparent p-0 cursor-pointer"
      />
      <span className="text-[11px] text-muted font-mono">{(value || '').toUpperCase()}</span>
    </label>
  )
}

export function Pill({ tone = 'muted', children }) {
  const colors = { ok: 'var(--c-ok)', warn: 'var(--c-warn)', danger: 'var(--c-danger)', accent: 'var(--c-accent)' }
  const c = colors[tone]
  return (
    <span className="pill">
      <span className="w-1.5 h-1.5 rounded-full shrink-0" style={{ background: c || 'var(--c-muted)' }} />
      {children}
    </span>
  )
}

/* ============================ 可折叠区块 ============================ */
export function Collapse({ title, badge, children, defaultOpen = true, trailing }) {
  const [open, setOpen] = useState(defaultOpen)
  return (
    <div className="min-w-0">
      <button type="button" className="flex items-center gap-2 w-full py-1 font-semibold" onClick={() => setOpen(!open)}>
        <span className="text-muted transition-transform" style={{ transform: open ? 'rotate(90deg)' : 'none' }}>
          <Icon name="chevron" size={13} />
        </span>
        <span>{title}</span>
        {badge}
        <span className="flex-1" />
        {trailing}
      </button>
      {open && <div className="mt-1.5 animate-fadein">{children}</div>}
    </div>
  )
}

/* ============================ 轻量提示 ============================ */
const ToastCtx = createContext(() => {})
export const useToast = () => useContext(ToastCtx)

export function ToastHost({ children }) {
  const [list, setList] = useState([])
  const push = (text, tone = 'ok') => {
    const id = Math.random().toString(36).slice(2)
    setList((l) => [...l, { id, text, tone }])
    setTimeout(() => setList((l) => l.filter((t) => t.id !== id)), 2600)
  }
  return (
    <ToastCtx.Provider value={push}>
      {children}
      <div className="fixed bottom-4 right-4 z-[9999] space-y-2 pointer-events-none">
        {list.map((t) => (
          <div key={t.id} className="toast" data-tone={t.tone}>
            <Icon name={t.tone === 'danger' ? 'alert' : 'check'} size={14} />
            <span>{t.text}</span>
          </div>
        ))}
      </div>
    </ToastCtx.Provider>
  )
}

/* ============================ 键盘快捷键 ============================ */
export function useKey(combo, handler) {
  useEffect(() => {
    const onKey = (e) => {
      const parts = combo.toLowerCase().split('+')
      const key = parts.pop()
      const needCtrl = parts.includes('ctrl')
      const needShift = parts.includes('shift')
      if (needCtrl !== (e.ctrlKey || e.metaKey)) return
      if (needShift !== e.shiftKey) return
      if (e.key.toLowerCase() !== key) return
      e.preventDefault()
      handler(e)
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [combo, handler])
}
