import React, { createContext, useContext, useEffect, useRef, useState } from 'react'
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

/* ============================ 应用 LOGO(以打包版 exe 图标为唯一来源) ============================ */
/** 图标来源:assets/app.ico → 构建时导出为 webui/logo.png(见 frontend/public/logo.png) */
export function Logo({ size = 22, radius, className = '', style }) {
  const r = radius ?? Math.max(4, Math.round(size * 0.26))
  return (
    <img
      src="logo.png"
      alt="OCR 助手"
      width={size}
      height={size}
      draggable={false}
      className={`shrink-0 select-none ${className}`}
      style={{ width: size, height: size, borderRadius: r, ...style }}
    />
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

/**
 * 悬浮提示。
 *
 * 位置策略(问题17):四个方向都试一遍,按"能完整放下 + 不压住洞口 + 离触发点近"
 * 打分择优,而不是原来的"先上后下"。悬浮窗的洞口是被 SetWindowRgn 从窗口里挖掉的,
 * 提示画在洞口范围内既看不见也点不到,因此必须主动避开。
 */
function holeRect() {
  const el = document.querySelector('[data-guide="hole"]')
  if (!el) return null
  const r = el.getBoundingClientRect()
  if (r.width < 8 || r.height < 8) return null
  return r
}

function overlapArea(a, b) {
  if (!a || !b) return 0
  const w = Math.min(a.right, b.right) - Math.max(a.left, b.left)
  const h = Math.min(a.bottom, b.bottom) - Math.max(a.top, b.top)
  return w > 0 && h > 0 ? w * h : 0
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
    const tw = Math.max(1, t.offsetWidth)
    const th = Math.max(1, t.offsetHeight)
    const vw = window.innerWidth
    const vh = window.innerHeight
    const pad = 6
    const gap = 6
    const hole = holeRect()

    // 候选位置:上 / 下 / 右 / 左(与触发点居中对齐或边缘对齐)
    const cands = [
      { key: 'top', left: wr.left + wr.width / 2 - tw / 2, top: wr.top - th - gap },
      { key: 'bottom', left: wr.left + wr.width / 2 - tw / 2, top: wr.bottom + gap },
      { key: 'right', left: wr.right + gap, top: wr.top + wr.height / 2 - th / 2 },
      { key: 'left', left: wr.left - tw - gap, top: wr.top + wr.height / 2 - th / 2 },
    ]
    // 用户显式指定时,把它排到最前(仍可被更好的位置替换)
    cands.sort((a, b) => (a.key === side ? -1 : b.key === side ? 1 : 0))

    let best = null
    for (const c of cands) {
      const box = { left: c.left, top: c.top, right: c.left + tw, bottom: c.top + th }
      const overflow =
        Math.max(0, pad - box.left) + Math.max(0, pad - box.top) +
        Math.max(0, box.right - (vw - pad)) + Math.max(0, box.bottom - (vh - pad))
      const cover = overlapArea(box, hole) / (tw * th)     // 被洞口吃掉的比例
      const dist = Math.abs(
        (box.left + box.right) / 2 - (wr.left + wr.right) / 2) +
        Math.abs((box.top + box.bottom) / 2 - (wr.top + wr.bottom) / 2)
      // 权重:先保证完整可见,其次不压洞口,最后离触发点近
      const score = overflow * 100 + cover * 1000 + dist * 0.05
      if (!best || score < best.score) best = { score, ...c }
    }

    // 夹进窗口内部(极端情况下宁可压住一点边,也不能跑到窗口外)
    const left = Math.max(pad, Math.min(best.left, Math.max(pad, vw - tw - pad)))
    const top = Math.max(pad, Math.min(best.top, Math.max(pad, vh - th - pad)))
    setPos({ left, top })
  }

  const hide = () => setPos(null)

  return (
    <span ref={wrap} className="tip-wrap"
          onMouseEnter={place} onFocus={place} onMouseLeave={hide} onBlur={hide}>
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

/**
 * 云端 / 本地 引擎开关(问题11)。
 *
 * 旧版是一个滑块 + 一段会随状态变化的文字,滑块与文字互相抢位置,视觉很乱。
 * 新版改为「分段胶囊」:两个选项都常显,选中项用主色高亮,滑动指示条只做 transform
 * 动画(合成层),语义一眼可读,也不用猜滑块在哪一侧。
 */
export function EngineSwitch({ cloud, onChange, label = '', tips = ['云端', '本地'], compact = false }) {
  const idx = cloud ? 0 : 1
  const title = label ? `${label}:${cloud ? tips[0] : tips[1]}` : `${cloud ? tips[0] : tips[1]}`
  return (
    <span className="engine-switch" title={title}>
      {label && !compact && <span className="engine-label">{label}</span>}
      <span className="engine-seg" role="radiogroup" aria-label={label || '引擎'}>
        {/* 滑动指示条:只做 transform,避免逐帧重排 */}
        <span className="engine-seg-thumb" style={{ transform: `translateX(${idx * 100}%)` }} />
        {tips.map((txt, i) => (
          <button
            key={txt}
            type="button"
            role="radio"
            aria-checked={idx === i}
            className="engine-seg-item"
            data-on={idx === i ? '1' : '0'}
            onClick={() => onChange(i === 0)}
          >
            <Icon name={i === 0 ? 'cloud' : 'cpu'} size={12} />
            <span>{txt}</span>
          </button>
        ))}
      </span>
    </span>
  )
}

/** 语言方向选择 [来源] → [目标] */
export function LangPair({ languages, source, target, onChange }) {
  const opts = languages && languages.length ? languages : ['自动检测', '中文']
  return (
    <div className="langpair">
      <LangSelect value={source} options={opts} title="来源语言"
                  onChange={(v) => onChange(v, target)} />
      <Tip text="交换语言方向">
        <button type="button" className="langpair-arrow" aria-label="交换语言方向"
                onClick={() => onChange(target === '自动检测' ? '自动检测' : target,
                                        source === '自动检测' ? '中文' : source)}>
          <Icon name="swap" size={14} />
        </button>
      </Tip>
      <LangSelect value={target} options={opts.filter((l) => l !== '自动检测')} title="目标语言"
                  onChange={(v) => onChange(source, v)} />
    </div>
  )
}

/** 主题化语言下拉:保留原生 select 的行为(键盘/滚轮/多语言列表),
    外观完全走主题令牌,并自绘下拉箭头 —— 之前用的是通用 .ctl,和顶栏其它控件不一致。 */
function LangSelect({ value, options, onChange, title }) {
  return (
    <span className="lang-select" title={title}>
      <select value={value} onChange={(e) => onChange(e.target.value)} aria-label={title}>
        {options.map((l) => <option key={l} value={l}>{l}</option>)}
      </select>
      <span className="lang-caret"><Icon name="chevronDown" size={13} /></span>
    </span>
  )
}

/* ============================ 提问输入(单行输入框,回车提交) ============================ */
/**
 * 单行提问输入(问题13)。
 * 去掉多行 textarea 与「示例提问」下拉按钮;Enter 触发 onSubmit,
 * 输入内容在失焦时自动记忆(供「设置 → 示例提问」里查看/编辑)。
 */
export function QBox({ value, onChange, placeholder, className = '', right, onSubmit, disabled }) {
  return (
    <div className={`qbox ${className}`}>
      <input
        type="text"
        className="ctl qbox-input"
        value={value}
        disabled={disabled}
        placeholder={placeholder || '输入提问/指令(可直接写:请翻译、请解释、请总结…)留空则使用默认指令'}
        onChange={(e) => onChange(e.target.value)}
        onBlur={() => { if ((value || '').trim()) call('remember_question', value.trim()) }}
        onKeyDown={(e) => {
          // 输入法组合中(isComposing / keyCode 229)不触发,避免中文输入被回车打断
          if (e.key === 'Enter' && onSubmit && !e.nativeEvent?.isComposing && e.keyCode !== 229) {
            e.preventDefault()
            onSubmit()
          }
        }}
      />
      {right && <div className="qbox-side">{right}</div>}
    </div>
  )
}

/* ============================ 拖拽窗口(受控,pointerup 必定结束) ============================ */
/* ============================ 窗口拖拽(帧同步:每帧最多一次跨进程调用) ============================ */
/** 把高频 pointermove 合并到 requestAnimationFrame:拖动/缩放更顺滑,也不会把主进程刷爆。
 *  - 窗口被遮挡/最小化时 Chromium 可能暂停 rAF,因此再加 50ms 定时兜底,避免"卡住不动";
 *  - 抬起时必须先 flush 未发出的最后一次移动,否则同一帧内 按下→移动→抬起 会丢掉这次移动。 */
function useFrameCoalesce() {
  const pending = useRef(null)
  const raf = useRef(0)
  const timer = useRef(0)

  const flush = () => {
    if (raf.current) { cancelAnimationFrame(raf.current); raf.current = 0 }
    if (timer.current) { clearTimeout(timer.current); timer.current = 0 }
    const f = pending.current
    pending.current = null
    if (f) f()
  }

  useEffect(() => () => {
    if (raf.current) cancelAnimationFrame(raf.current)
    if (timer.current) clearTimeout(timer.current)
  }, [])

  const schedule = (fn) => {
    pending.current = fn
    if (raf.current || timer.current) return
    raf.current = requestAnimationFrame(flush)
    timer.current = setTimeout(flush, 50)
  }

  return [schedule, flush]
}

/** 拖动/缩放期间给 <body> 打标记:临时关掉元素过渡,避免窗口移动时元素"拖尾" */
function setMoving(on) {
  try { document.body.classList.toggle('dragging', !!on) } catch (e) { /* 忽略 */ }
}

export function useWindowDrag(which) {
  const st = useRef(null)
  const [schedule, flush] = useFrameCoalesce()
  const onPointerDown = (e) => {
    if (e.button !== 0) return
    if (e.target.closest('button,input,select,textarea,a,label,.no-drag,.tip-wrap')) return
    st.current = { id: e.pointerId, x: e.screenX, y: e.screenY }
    try { e.currentTarget.setPointerCapture(e.pointerId) } catch { /* 忽略 */ }
    setMoving(true)
    call('drag_begin', which, e.screenX, e.screenY)
  }
  const onPointerMove = (e) => {
    if (!st.current || st.current.id !== e.pointerId) return
    const x = e.screenX
    const y = e.screenY
    schedule(() => call('drag_move', which, x, y))
  }
  const end = () => {
    if (!st.current) return
    st.current = null
    flush()                     // 先把最后一帧的位置发出去,再结束拖拽
    setMoving(false)
    call('drag_end', which)
  }
  return {
    onPointerDown, onPointerMove, onPointerUp: end,
    onPointerCancel: end, onLostPointerCapture: end,
  }
}

/* ============================ 窗口边框缩放(无边框窗口) ============================ */
const EDGES = ['n', 's', 'e', 'w', 'ne', 'nw', 'se', 'sw']

export function ResizeHandles({ which, onStart, edges }) {
  const st = useRef(null)
  const [schedule, flush] = useFrameCoalesce()
  const start = (edge) => (e) => {
    if (e.button !== 0) return
    st.current = { id: e.pointerId, edge }
    try { e.currentTarget.setPointerCapture(e.pointerId) } catch { /* 忽略 */ }
    if (onStart) onStart()
    setMoving(true)
    call('resize_begin', which, edge, e.screenX, e.screenY)
    e.preventDefault()
    e.stopPropagation()
  }
  const move = (e) => {
    if (!st.current || st.current.id !== e.pointerId) return
    const x = e.screenX
    const y = e.screenY
    schedule(() => call('resize_move', which, x, y))
  }
  const end = () => {
    if (!st.current) return
    st.current = null
    flush()                     // 同上:保证最后一次尺寸变化不会丢
    setMoving(false)
    call('resize_end', which)
  }
  const common = { onPointerMove: move, onPointerUp: end, onPointerCancel: end, onLostPointerCapture: end }
  // 显式传空数组 = 不要任何缩放热区(悬浮窗已取消拖边缩放);未传才用全部边角
  const list = Array.isArray(edges) ? edges : EDGES
  if (!list.length) return null
  return (
    <>
      {list.map((edge) => (
        <span key={edge} className={`rs rs-${edge}`} onPointerDown={start(edge)} {...common} />
      ))}
    </>
  )
}

/* ============================ 端侧模型:档位选择 + 下载进度 ============================ */
const DownloadCtx = createContext({ ask: () => {}, progress: null })
export const useDownloader = () => useContext(DownloadCtx)

const KIND_TITLE = { ocr: '端侧识别模型', mt: '端侧翻译模型', runtime: '端侧推理运行时' }

/** 档位卡片列表(下载弹窗与设置页共用) */
export function ModelTiers({ kind, tiers, current, onSelect, onDownload, onRemove, busyTier }) {
  if (!tiers || !tiers.length) return <div className="hint">暂无可下载的档位</div>
  return (
    <div className="space-y-2">
      {tiers.map((t) => {
        const active = current === t.key
        return (
          <div key={t.key} className={`tier-card ${active ? 'tier-card-active' : ''}`}>
            <div className="flex items-center gap-2 flex-wrap">
              <span className="tier-radio" data-on={active ? '1' : '0'} />
              <span className="font-semibold text-[13px]">{t.name}</span>
              {t.recommend && <span className="chip">推荐</span>}
              {active && <span className="chip" style={{ color: 'var(--c-accent)', borderColor: 'var(--c-accent)' }}>当前</span>}
              <span className="chip">{t.size_mb} MB</span>
              <span className="flex-1" />
              {t.ready
                ? <span className="chip" style={{ color: 'var(--c-ok)', borderColor: 'var(--c-ok)' }}>已下载{t.size_on_disk ? ` · ${t.size_on_disk}MB` : ''}</span>
                : <span className="chip" style={{ color: 'var(--c-warn)', borderColor: 'var(--c-warn)' }}>未下载</span>}
            </div>
            {/* 规格用两列网格:数值纵向对齐,比用「·」串成一行更好比较 */}
            <div className="hint mt-1.5 grid grid-cols-2 gap-x-3 gap-y-0.5 leading-snug">
              <div>速度 {t.speed}</div>
              <div>准确度 {t.quality}</div>
              <div>代价 {t.cost}</div>
              {t.covered && <div className="truncate" title={t.covered}>覆盖 {t.covered}</div>}
            </div>
            <div className="flex items-center gap-2 mt-2">
              <Btn className="!h-7 !text-[12px]" disabled={active} onClick={() => onSelect(t.key)}>
                {active ? '当前使用' : '选为当前档位'}
              </Btn>
              {t.ready
                ? <Btn className="!h-7 !text-[12px]" danger onClick={() => onRemove(t.key)}>删除</Btn>
                : <Btn className="!h-7 !text-[12px]" primary icon="download" disabled={busyTier === t.key}
                        onClick={() => onDownload(t.key)}>
                    {busyTier === t.key ? '下载中…' : '下载'}
                  </Btn>}
            </div>
          </div>
        )
      })}
    </div>
  )
}

export function DownloadHost({ children }) {
  const [req, setReq] = useState(null)
  const [prog, setProg] = useState(null)
  const [data, setData] = useState(null)
  const [busyTier, setBusyTier] = useState('')

  const load = () => call('local_models_status').then(setData)

  useEffect(() => {
    const on = (e) => {
      const ev = e.detail
      if (ev.type !== 'download') return
      setProg(ev)
      if (ev.done) {
        setBusyTier('')
        load()
        if (!ev.error && req?.onDone) req.onDone()
        setTimeout(() => setProg(null), ev.error ? 6000 : 3000)
      }
    }
    window.addEventListener('ocr-event', on)
    return () => window.removeEventListener('ocr-event', on)
  }, [req])

  const ask = (kind, opts = {}) => {
    setReq({ kind, ...opts })
    setData(null)
    load()
  }
  const close = () => setReq(null)

  // 下载确认弹窗居中:打开期间取消洞口穿透(否则被裁掉),并让迷你条临时腾出空间
  useEffect(() => {
    call('pause_hole', !!req)
    call('set_modal_room', !!req)
    return () => { if (req) { call('pause_hole', false); call('set_modal_room', false) } }
  }, [req])

  const tiers = data?.tiers?.[req?.kind] || []
  const current = data?.current?.[req?.kind] || ''
  const source = data?.source || 'auto'

  return (
    <DownloadCtx.Provider value={{ ask, progress: prog, data, reload: load }}>
      {children}
      {req && (
        <div className="modal-mask" onClick={close}>
          {/* 头尾固定、中间滚动:模型档位多时不用整窗滚动,操作按钮始终可见 */}
          <div className="modal-card modal-sheet !w-[520px]" onClick={(e) => e.stopPropagation()}>
            <header className="modal-sheet-head">
              <span className="card-icon"><Icon name="download" size={15} /></span>
              <div className="min-w-0">
                <div className="font-semibold">{KIND_TITLE[req.kind] || '端侧模型'}</div>
                <div className="hint mt-0.5">
                  {req.kind === 'mt'
                    ? '端侧翻译为离线专用模型:不联网、不消耗额度,准确度低于云端大模型'
                    : '模型不随应用分发,首次使用需联网下载一次;可随时在设置里换档或删除'}
                </div>
              </div>
            </header>

            <div className="modal-sheet-body">
            {req.kind === 'mt' && (
              <div className="inset px-3 py-2 mb-2 text-[12px]">
                <b>准确度提示</b>:端侧专用翻译模型(opust-mt int8)质量中等,适合"看懂大意";
                追求准确请把「翻译」开关切回<b>云端</b>。
              </div>
            )}

            {data ? (
              <>
                <ModelTiers kind={req.kind} tiers={tiers} current={current}
                            busyTier={busyTier}
                            onSelect={(t) => call('set_local_tier', req.kind, t)
                              .then(() => load())
                              .then(() => req.onSelect && req.onSelect(t))}
                            onDownload={(t) => { setBusyTier(t); call('download_local_model', req.kind, t) }}
                            onRemove={(t) => call('remove_local_model', req.kind, t).then((m) => { load(); if (req.onDone) req.onDone() })} />
                {req.kind === 'runtime' && (
                  <div className="hint mt-2">运行时约 62MB,只需下载一次(ctranslate2 + sentencepiece)</div>
                )}
                {req.kind === 'mt' && (
                  <>
                    <div className="inset px-3 py-2 mt-2 flex items-center gap-2 text-[12px]">
                      <span className="text-muted shrink-0">轻量档运行时(CTranslate2)</span>
                      {data.runtime?.ready
                        ? <span className="chip" style={{ color: 'var(--c-ok)', borderColor: 'var(--c-ok)' }}>已就绪</span>
                        : <Btn className="!h-7 !text-[12px]" icon="download"
                               onClick={() => { setBusyTier('__rt'); call('download_local_model', 'runtime') }}>下载(约 62MB)</Btn>}
                    </div>
                    <div className="inset px-3 py-2 mt-2 flex items-center gap-2 text-[12px]">
                      <span className="text-muted shrink-0">均衡/全量档运行时(官方模型)</span>
                      {data.hf_runtime?.ready
                        ? <span className="chip" style={{ color: 'var(--c-ok)', borderColor: 'var(--c-ok)' }}>已就绪</span>
                        : <Btn className="!h-7 !text-[12px]" icon="download"
                               onClick={() => { setBusyTier('__hfr'); call('download_local_model', 'hf_runtime') }}>
                             下载(约 2.5GB,仅一次)</Btn>}
                      <span className="hint">官方 NLLB 模型质量最好,但占用大、CPU 上较慢</span>
                    </div>
                  </>
                )}
                <div className="inset px-3 py-2 mt-2 flex items-center gap-2 text-[12px]">
                  <span className="text-muted shrink-0">模型下载源</span>
                  <Segmented size="sm" value={source}
                             options={[{ value: 'auto', label: '自动' }, { value: 'hf', label: '官方' },
                                       { value: 'mirror', label: 'hf-mirror' }]}
                             onChange={(v) => call('set_local_tier', 'source', v).then(load)} />
                  <span className="hint">国内网络建议 hf-mirror</span>
                </div>
              </>
            ) : <div className="hint py-3 text-center">正在读取端侧模型状态…</div>}
            </div>

            <footer className="modal-sheet-foot">
              <span className="hint flex-1">
                {req.kind === 'ocr' ? '识别档位影响小字/表格的识别率;均衡档为推荐值'
                  : '选好档位后点「用这个档位」即可切到端侧'}
              </span>
              {req.kind === 'mt' && (
                <Btn primary disabled={!(data?.mt_tier_ready)} onClick={() => {
                  close()
                  if (req.onDone) req.onDone()
                }}>用这个档位</Btn>
              )}
              <Btn onClick={close}>关闭</Btn>
            </footer>
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
                  style={{ width: '100%',
                           transform: `scaleX(${Math.max(0, Math.min(100, prog.error ? 100 : prog.pct || 0)) / 100})`,
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
        <header className="flex items-start gap-2.5 mb-3">
          {icon && <span className="card-icon"><Icon name={icon} size={15} /></span>}
          <div className="min-w-0">
            {title && <h3 className="font-semibold text-[13.5px] leading-tight truncate">{title}</h3>}
            {desc && <p className="hint mt-1 leading-snug">{desc}</p>}
          </div>
          <div className="flex-1" />
          {/* 右上操作在窄窗口下换行,避免把标题挤没 */}
          <div className="flex items-center gap-2 flex-wrap justify-end">{right}</div>
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
        role="switch"
        aria-checked={!!checked}
        onClick={() => onChange(!checked)}
        className="w-11 h-6 rounded-full border relative shrink-0 transition-colors"
        style={{
          background: checked ? 'var(--c-accent)' : 'var(--c-sub)',
          borderColor: checked ? 'var(--c-accent)' : 'var(--c-line)',
        }}
      >
        {/* 用 transform 滑动:合成层动画,不触发布局 */}
        <span
          className="absolute top-[2px] left-[2px] w-[18px] h-[18px] rounded-full will-change-transform"
          style={{
            background: '#fff', boxShadow: '0 1px 3px rgba(0,0,0,.28)',
            transform: `translateX(${checked ? 20 : 0}px)`,
            transition: 'transform var(--dur-2) var(--ease-out)',
          }}
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
    <div className="inset px-3 py-2.5">
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
