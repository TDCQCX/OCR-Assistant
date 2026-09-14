import React, { createContext, useContext, useEffect, useState } from 'react'

/* ------------------------- 基础控件 ------------------------- */
export function Card({ title, desc, right, children, className = '' }) {
  return (
    <section className={`card p-4 animate-fadein ${className}`}>
      {(title || right) && (
        <header className="flex items-center gap-3 mb-3">
          <div className="min-w-0">
            {title && <h3 className="font-bold text-[14px] truncate">{title}</h3>}
            {desc && <p className="hint mt-0.5">{desc}</p>}
          </div>
          <div className="flex-1" />
          {right}
        </header>
      )}
      {children}
    </section>
  )
}

export function Btn({ primary, danger, className = '', ...rest }) {
  const tone = primary ? 'btn-primary border-transparent' : danger ? 'hover:border-danger text-danger' : ''
  return <button className={`btn ${tone} disabled:opacity-50 disabled:cursor-not-allowed ${className}`} {...rest} />
}

export function Switch({ checked, onChange, label, hint }) {
  return (
    <label className="flex items-center gap-3 cursor-pointer">
      <button
        type="button"
        onClick={() => onChange(!checked)}
        className="w-11 h-6 rounded-full border transition-colors relative shrink-0"
        style={{
          background: checked ? 'var(--c-accent)' : 'var(--c-card)',
          borderColor: checked ? 'var(--c-accent)' : 'var(--c-line)',
        }}
      >
        <span
          className="absolute top-[2px] w-[18px] h-[18px] rounded-full bg-white transition-all"
          style={{ left: checked ? 22 : 2, boxShadow: '0 1px 3px rgba(0,0,0,.25)' }}
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
  const pad = size === 'sm' ? 'px-3 py-1 text-[12px]' : 'px-4 py-1.5'
  return (
    <div className="inline-flex gap-1.5">
      {options.map((o) => {
        const active = value === o.value
        return (
          <button
            key={o.value}
            onClick={() => onChange(o.value)}
            className={`${pad} rounded-ctl border font-medium transition-all`}
            style={{
              background: active ? 'var(--c-accent)' : 'var(--c-card)',
              borderColor: active ? 'var(--c-accent)' : 'var(--c-line)',
              color: active ? 'var(--c-accent-fg)' : 'var(--c-fg)',
            }}
          >
            {o.label}
          </button>
        )
      })}
    </div>
  )
}

export function Field({ label, hint, children, width = 120 }) {
  return (
    <div className="rounded-ctl border border-line bg-card/40 px-3 py-2">
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
        className="w-8 h-8 rounded-ctl border border-line bg-transparent p-0 cursor-pointer"
      />
      <span className="text-[11px] text-muted font-mono">{(value || '').toUpperCase()}</span>
    </label>
  )
}

export function Pill({ tone = 'muted', children }) {
  const colors = { ok: 'var(--c-ok)', warn: 'var(--c-warn)', danger: 'var(--c-danger)', accent: 'var(--c-accent)' }
  const c = colors[tone]
  return (
    <span className="inline-flex items-center gap-1.5 px-2 py-0.5 rounded-full text-[11px] border border-line">
      <span className="w-2 h-2 rounded-full" style={{ background: c || 'var(--c-muted)' }} />
      {children}
    </span>
  )
}

/* ------------------------- 可折叠区块 ------------------------- */
export function Collapse({ title, badge, children, defaultOpen = true, trailing }) {
  const [open, setOpen] = useState(defaultOpen)
  return (
    <div className="min-w-0">
      <button className="flex items-center gap-2 w-full py-1 font-bold" onClick={() => setOpen(!open)}>
        <span className="text-muted text-[10px] w-3">{open ? '▼' : '▶'}</span>
        <span>{title}</span>
        {badge}
        <span className="flex-1" />
        {trailing}
      </button>
      {open && <div className="mt-1 animate-fadein">{children}</div>}
    </div>
  )
}

/* ------------------------- 轻量提示 ------------------------- */
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
          <div
            key={t.id}
            className="px-3 py-2 rounded-ctl border shadow-lg animate-pop text-[12px]"
            style={{
              background: 'var(--c-card)',
              borderColor: t.tone === 'danger' ? 'var(--c-danger)' : 'var(--c-line)',
              color: t.tone === 'danger' ? 'var(--c-danger)' : 'var(--c-fg)',
            }}
          >
            {t.text}
          </div>
        ))}
      </div>
    </ToastCtx.Provider>
  )
}

/* ------------------------- 键盘快捷键 ------------------------- */
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
