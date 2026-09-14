import React, { createContext, useContext, useEffect, useMemo, useRef, useState } from 'react'
import { call } from './bridge'

/* ============================ 扁平图标(纯 CSS/SVG,无 emoji) ============================ */
const PATHS = {
  overlay: <><rect x="3" y="4.5" width="18" height="15" rx="2.5" /><rect x="7.5" y="8.5" width="9" height="7" rx="1.2" /></>,
  translate: <><path d="M3.5 5.5h9M8 5.5v1.8c0 3.7-2 6.8-4.5 8.2" /><path d="M5.6 11.2c1.1 2 2.8 3.6 4.7 4.6" /><path d="M13 19.5l3.6-8.5 3.6 8.5M14.4 16.4h4.4" /></>,
  mini: <><rect x="2.5" y="9" width="19" height="6" rx="3" /><path d="M7 12h4" /></>,
  snip: <path d="M4 9V6.5A2.5 2.5 0 0 1 6.5 4H9M15 4h2.5A2.5 2.5 0 0 1 20 6.5V9M20 15v2.5a2.5 2.5 0 0 1-2.5 2.5H15M9 20H6.5A2.5 2.5 0 0 1 4 17.5V15" />,
  scan: <><path d="M4 8V6a2 2 0 0 1 2-2h2M16 4h2a2 2 0 0 1 2 2v2M20 16v2a2 2 0 0 1-2 2h-2M8 20H6a2 2 0 0 1-2-2v-2" /><path d="M4 12h16" /></>,
  settings: <><circle cx="12" cy="12" r="3.1" /><path d="M19.1 14.4a1.6 1.6 0 0 0 .3 1.8l.1.1a1.9 1.9 0 1 1-2.7 2.7l-.1-.1a1.6 1.6 0 0 0-1.8-.3 1.6 1.6 0 0 0-1 1.5v.2a1.9 1.9 0 1 1-3.8 0v-.1a1.6 1.6 0 0 0-1-1.5 1.6 1.6 0 0 0-1.8.3l-.1.1a1.9 1.9 0 1 1-2.7-2.7l.1-.1a1.6 1.6 0 0 0 .3-1.8 1.6 1.6 0 0 0-1.5-1H3a1.9 1.9 0 1 1 0-3.8h.1a1.6 1.6 0 0 0 1.5-1 1.6 1.6 0 0 0-.3-1.8l-.1-.1a1.9 1.9 0 1 1 2.7-2.7l.1.1a1.6 1.6 0 0 0 1.8.3H9a1.6 1.6 0 0 0 1-1.5V3a1.9 1.9 0 1 1 3.8 0v.1a1.6 1.6 0 0 0 1 1.5 1.6 1.6 0 0 0 1.8-.3l.1-.1a1.9 1.9 0 1 1 2.7 2.7l-.1.1a1.6 1.6 0 0 0-.3 1.8V9a1.6 1.6 0 0 0 1.5 1h.2a1.9 1.9 0 1 1 0 3.8h-.1a1.6 1.6 0 0 0-1.5 1z" /></>,
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
  chevronDown: <path d="M6.5 9.5l5.5 5.5 5.5-5.5" />,
  swap: <><path d="M7.5 8h11l-2.8-2.8M16.5 16h-11l2.8 2.8" /></>,
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
  cloud: <><path d="M7.5 18.5h9.2a3.8 3.8 0 0 0 .4-7.6A5.4 5.4 0 0 0 6.6 9.6a4.5 4.5 0 0 0 .9 8.9z" /></>,
  cpu: <><rect x="7" y="7" width="10" height="10" rx="2" /><path d="M10 3.5v3M14 3.5v3M10 17.5v3M14 17.5v3M3.5 10h3M3.5 14h3M17.5 10h3M17.5 14h3" /></>,
  columns: <><rect x="3.5" y="5" width="17" height="14" rx="2" /><path d="M12 5v14" /></>,
  list: <><path d="M5 7h14M5 12h14M5 17h9" /></>,
  wand: <><path d="M5.5 18.5L15 9" /><path d="M13.2 6.8l1.4-1.4M17.5 11.1l1.4-1.4M16.4 5.6l1.4 1.4M12.6 12.2l1.4 1.4" /></>,
  edit: <><path d="M15.6 4.6l3.8 3.8" /><path d="M4.5 19.5l1-4.3 9.7-9.7a2.7 2.7 0 0 1 3.8 3.8l-9.7 9.7z" /></>,
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

/* ============================ 悬浮提示(自绘白底黑字,并夹在窗口内部) ============================ */
/** 窗口过小时不再使用悬浮提示(提示框物理上放不下),改为就地展开文字 */
export function useSmallWindow() {
  const [small, setSmall] = useState(false)
  useEffect(() => {
    const on = () => setSmall(window.innerHeight < 170 || window.innerWidth < 400)
    on()
    window.addEventListener('resize', on)
    return () => window.removeEventListener('resize', on)
  }, [])
  return small
}

export function Tip({ text, side = 'top', children }) {
  const wrap = useRef(null)
  const tip = useRef(null)
  const [pos, setPos] = useState(null)
  const small = useSmallWindow()
  if (!text || small) return children

  const place = () => {
    const w = wrap.current
    const t = tip.current
    if (!w || !t) return
    const wr = w.getBoundingClientRect()
    const tw = t.offsetWidth
    const th = t.offsetHeight
    const vw = window.innerWidth
    const vh = window.innerHeight
    const pad = 6
    let x = wr.left + wr.width / 2 - tw / 2          // 相对窗口:尽量居中
    let y = wr.top - th - 6
    if (y < pad) y = wr.bottom + 6                    // 上方放不下就放下方
    y = Math.max(pad, Math.min(y, vh - th - pad))     // 夹在窗口内部
    x = Math.max(pad, Math.min(x, vw - tw - pad))
    setPos({ left: x, top: y })
  }

  return (
    <span ref={wrap} className="tip-wrap"
          onMouseEnter={place} onFocus={place} onMouseLeave={() => setPos(null)}>
      {children}
      <span ref={tip} className="tip" role="tooltip"
            style={pos ? { left: pos.left, top: pos.top, opacity: 1 } : { visibility: 'hidden' }}>
        {text}
      </span>
    </span>
  )
}

/** 纯图标按钮(悬停显示自绘提示) */
export function IconBtn({ icon, tip, active, primary, danger, size = 16, className = '', ...rest }) {
  const tone = primary
    ? 'icon-btn-primary'
    : danger ? 'hover:text-danger' : active ? 'icon-btn-active' : ''
  return (
    <Tip text={tip}>
      <button type="button" aria-label={tip} className={`icon-btn ${tone} ${className}`} {...rest}>
        <Icon name={icon} size={size} />
      </button>
    </Tip>
  )
}

/**
 * 模式切换:选中项在图标旁展开文字说明,未选中项只显示图标。
 * (替代原先的纯图标分段控件,兼顾紧凑与可读性)
 */
export function IconSeg({ value, options, onChange, size = 'md' }) {
  const h = size === 'sm' ? 'h-7' : 'h-8'
  return (
    <div className={`iconseg ${h}`}>
      {options.map((o) => {
        const active = value === o.value
        const item = (
          <button
            key={o.value}
            type="button"
            aria-label={o.label}
            className="iconseg-item"
            data-active={active ? '1' : '0'}
            onClick={() => onChange(o.value)}
          >
            <Icon name={o.icon} size={15} />
            <span className="iconseg-label">{o.label}</span>
          </button>
        )
        return active ? item : <Tip key={o.value} text={o.label}>{item}</Tip>
      })}
    </div>
  )
}

/** 云端 / 本地 引擎开关(开=云端,关=本地;文字精简、过渡平滑) */
export function EngineSwitch({ cloud, onChange, label = '', tips = ['云端', '本地'], compact = false }) {
  return (
    <span className="engine-switch" title={label ? `${label}:${cloud ? tips[0] : tips[1]}` : ''}>
      <button
        type="button"
        className="engine-track"
        data-cloud={cloud ? '1' : '0'}
        data-compact={compact ? '1' : '0'}
        onClick={() => onChange(!cloud)}
        aria-label={`${label} ${cloud ? tips[0] : tips[1]}`}
      >
        <span className="engine-knob" />
        <span className="engine-text">{cloud ? tips[0] : tips[1]}</span>
      </button>
      {label && !compact && <span className="engine-label">{label}</span>}
    </span>
  )
}

/** 语言方向选择 [来源] → [目标] */
export function LangPair({ languages, source, target, onChange }) {
  const opts = languages && languages.length ? languages : ['自动检测', '中文']
  return (
    <div className="langpair">
      <select className="ctl !w-[96px] !h-7 !text-[12px]" value={source}
              onChange={(e) => onChange(e.target.value, target)}>
        {opts.map((l) => <option key={l} value={l}>{l}</option>)}
      </select>
      <Tip text="交换语言方向">
        <button type="button" className="langpair-arrow" onClick={() => onChange(target === '自动检测' ? '自动检测' : target, source === '自动检测' ? '中文' : source)}>
          <Icon name="swap" size={14} />
        </button>
      </Tip>
      <select className="ctl !w-[96px] !h-7 !text-[12px]" value={target}
              onChange={(e) => onChange(source, e.target.value)}>
        {opts.filter((l) => l !== '自动检测').map((l) => <option key={l} value={l}>{l}</option>)}
      </select>
    </div>
  )
}

/* ============================ 提问输入(大输入框 + 示例下拉 + 自输入自动保存) ============================ */
const FALLBACK_PRESETS = [
  '请回答识别到的内容', '请翻译识别到的内容', '请解释识别到的内容',
  '请总结识别到的内容的要点', '请搜索并告诉我相关联的内容',
]

export function QBox({ value, onChange, presets, history, rows = 2, placeholder, className = '', right }) {
  const [open, setOpen] = useState(false)
  const list = useMemo(() => {
    const merged = [...(presets || []), ...(history || [])]
    const seen = new Set()
    return merged.filter((q) => q && !seen.has(q) && seen.add(q))
  }, [presets, history])
  const box = useRef(null)

  useEffect(() => {
    if (!open) return
    const onDoc = (e) => { if (box.current && !box.current.contains(e.target)) setOpen(false) }
    document.addEventListener('mousedown', onDoc)
    return () => document.removeEventListener('mousedown', onDoc)
  }, [open])

  const pick = (q) => { onChange(q); setOpen(false) }

  return (
    <div ref={box} className={`qbox ${className}`}>
      <textarea
        className="ctl qbox-input"
        rows={rows}
        value={value}
        placeholder={placeholder || '输入你的提问/指令(可直接写:请翻译、请解释、请总结…)留空则使用默认指令'}
        onChange={(e) => onChange(e.target.value)}
        onBlur={() => { if ((value || '').trim()) call('remember_question', value.trim()) }}
      />
      <div className="qbox-side">
        {right}
        <Tip text="示例提问">
          <button type="button" className="qbox-more" onClick={() => setOpen(!open)} aria-label="示例提问">
            <Icon name="list" size={15} />
          </button>
        </Tip>
      </div>
      {open && (
        <div className="qbox-menu">
          <div className="qbox-menu-title">示例提问(点击填入;自己输入的内容会自动记住)</div>
          {(list.length ? list : FALLBACK_PRESETS).map((q) => (
            <button key={q} type="button" className="qbox-menu-item" onClick={() => pick(q)}>
              <Icon name="wand" size={13} />
              <span className="truncate">{q}</span>
            </button>
          ))}
        </div>
      )}
    </div>
  )
}

/* ============================ 拖拽窗口(受控,pointerup 必定结束) ============================ */
export function useWindowDrag(which) {
  const st = useRef(null)
  const onPointerDown = (e) => {
    if (e.button !== 0) return
    if (e.target.closest('button,input,select,textarea,a,label,.no-drag,.tip-wrap')) return
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

/* ============================ 窗口边框缩放(无边框窗口) ============================ */
const EDGES = ['n', 's', 'e', 'w', 'ne', 'nw', 'se', 'sw']

export function ResizeHandles({ which, onStart }) {
  const st = useRef(null)
  const start = (edge) => (e) => {
    if (e.button !== 0) return
    st.current = { id: e.pointerId, edge }
    try { e.currentTarget.setPointerCapture(e.pointerId) } catch { /* 忽略 */ }
    if (onStart) onStart()
    call('resize_begin', which, edge, e.screenX, e.screenY)
    e.preventDefault()
    e.stopPropagation()
  }
  const move = (e) => {
    if (st.current && st.current.id === e.pointerId) call('resize_move', which, e.screenX, e.screenY)
  }
  const end = () => {
    if (!st.current) return
    st.current = null
    call('resize_end', which)
  }
  const common = { onPointerMove: move, onPointerUp: end, onPointerCancel: end, onLostPointerCapture: end }
  return (
    <>
      {EDGES.map((edge) => (
        <span key={edge} className={`rs rs-${edge}`} onPointerDown={start(edge)} {...common} />
      ))}
    </>
  )
}

/* ============================ 端侧模型下载(提示 + 进度) ============================ */
const DownloadCtx = createContext({ ask: () => {}, progress: null })
export const useDownloader = () => useContext(DownloadCtx)

export function DownloadHost({ children }) {
  const [req, setReq] = useState(null)
  const [prog, setProg] = useState(null)

  useEffect(() => {
    const on = (e) => {
      const ev = e.detail
      if (ev.type !== 'download') return
      setProg(ev)
      if (ev.done) {
        if (!ev.error && req?.onDone) req.onDone()
        setTimeout(() => setProg(null), ev.error ? 6000 : 3000)
      }
    }
    window.addEventListener('ocr-event', on)
    return () => window.removeEventListener('ocr-event', on)
  }, [req])

  const ask = (kind, opts = {}) => setReq({ kind, ...opts })
  const start = () => {
    const kind = req?.kind
    setReq(null)
    call('download_local_model', kind)
  }

  return (
    <DownloadCtx.Provider value={{ ask, progress: prog }}>
      {children}
      {req && (
        <div className="modal-mask" onClick={() => setReq(null)}>
          <div className="modal-card" onClick={(e) => e.stopPropagation()}>
            <div className="flex items-center gap-2.5 mb-2.5">
              <span className="card-icon"><Icon name="download" size={15} /></span>
              <div className="min-w-0">
                <div className="font-semibold">{req.title || '需要下载端侧模型'}</div>
                <div className="hint mt-0.5">{req.note || '端侧模型不随应用分发,首次使用需联网下载一次'}</div>
              </div>
            </div>
            <div className="inset px-3 py-2 text-[12.5px] space-y-1.5">
              <div className="flex items-center gap-2">
                <span className="text-muted w-[70px] shrink-0">下载内容</span>
                <span className="truncate">{req.detail || '端侧模型'}</span>
              </div>
              <div className="flex items-center gap-2">
                <span className="text-muted w-[70px] shrink-0">体积</span>
                <span>{req.size || '约 16-110 MB'}</span>
              </div>
              <div className="flex items-center gap-2">
                <span className="text-muted w-[70px] shrink-0">保存位置</span>
                <span className="truncate">models/ 目录(可在设置中删除)</span>
              </div>
            </div>
            <div className="flex items-center gap-2 mt-3">
              <span className="hint flex-1">下载完成后自动切换到端侧</span>
              <Btn onClick={() => setReq(null)}>暂不</Btn>
              <Btn primary icon="download" onClick={start}>立即下载</Btn>
            </div>
          </div>
        </div>
      )}
      {prog && (
        <div className="progress-toast">
          <div className="flex items-center gap-2">
            <Icon name={prog.error ? 'alert' : prog.done ? 'check' : 'download'} size={14} />
            <span className="truncate flex-1">
              {prog.error || prog.message || prog.text || '正在下载端侧模型…'}
            </span>
            <span className="hint shrink-0">{prog.pct || 0}%</span>
          </div>
          <div className="progress-track">
            <span className="progress-fill"
                  style={{ width: `${prog.error ? 100 : prog.pct || 0}%`,
                           background: prog.error ? 'var(--c-danger)' : undefined }} />
          </div>
        </div>
      )}
    </DownloadCtx.Provider>
  )
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
            onClick={() => onChange(o.value)}
            className={`seg-item ${pad}`}
            data-active={active ? '1' : '0'}
          >
            {o.icon && <Icon name={o.icon} size={14} />}
            {o.label}
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
    <label className="flex items-center gap-2 cursor-pointer">
      <Tip text={title}>
        <input
          type="color"
          value={value || '#000000'}
          onChange={(e) => onChange(e.target.value)}
          className="w-7 h-7 rounded-ctl border border-line bg-transparent p-0 cursor-pointer"
        />
      </Tip>
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
