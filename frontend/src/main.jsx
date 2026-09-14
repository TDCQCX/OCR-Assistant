import React, { createContext, useContext, useEffect, useMemo, useState } from 'react'
import { createRoot } from 'react-dom/client'
import './index.css'
import { call } from './bridge'
import { applyTheme, resolveTheme, PRESETS } from './theme'
import { ToastHost, useToast } from './ui'
import Overlay from './Overlay'
import MiniBar from './MiniBar'
import Translate from './Translate'
import Settings from './Settings'

export const AppCtx = createContext(null)
export const useApp = () => useContext(AppCtx)

/* ------------------- 应用根 ------------------- */
function App() {
  const view = new URLSearchParams(location.search).get('view') || 'overlay'
  const [cfg, setCfg] = useState(null)
  const [status, setStatus] = useState({ text: '就绪', tone: 'idle' })
  const [result, setResult] = useState(null)
  const [history, setHistory] = useState([])
  const [busy, setBusy] = useState(false)
  const [version, setVersion] = useState('2.0.0')

  // 初始化:拉取状态 + 注册后端事件
  useEffect(() => {
    call('get_state').then((s) => {
      setCfg(s.config)
      setVersion(s.version || '2.0.0')
      if (s.history) setHistory(s.history)
      setStatus({ text: s.key_ready ? '就绪 · Key 已配置' : '就绪 · Key 未配置', tone: s.key_ready ? 'idle' : 'warn' })
    })
    window.__ocrEvent = (ev) => {
      if (!ev) return
      // 同时派发自定义事件,便于各视图监听(如隐藏洞口边框、快捷键触发)
      window.dispatchEvent(new CustomEvent('ocr-event', { detail: ev }))
      if (ev.type === 'status') setStatus({ text: ev.text, tone: ev.tone || 'working' })
      if (ev.type === 'result') { setResult(ev.data); setBusy(false) }
      if (ev.type === 'error') { setBusy(false); setStatus({ text: '失败', tone: 'danger' }); setResult({ error: ev.text }) }
      if (ev.type === 'config') setCfg(ev.config)
      if (ev.type === 'history') setHistory(ev.data)
      if (ev.type === 'busy') setBusy(!!ev.value)
    }
    return () => { delete window.__ocrEvent }
  }, [])

  // 主题应用(带上 ui.panelOpacity 等附加项)
  useEffect(() => { if (cfg) applyTheme(resolveTheme(cfg.ui), cfg.ui) }, [cfg])

  const api = useMemo(() => ({
    cfg, setCfg, status, setStatus, result, setResult, history, setHistory, busy, setBusy, version, view,
    /** 保存一条 ui 配置并广播到所有窗口 */
    async setUi(patch) {
      const next = { ...cfg, ui: { ...cfg.ui, ...patch } }
      setCfg(next)
      await call('save_ui', patch)
    },
    async setPath(path, value) {
      await call('set_config_value', path, value)
      const s = await call('get_state')
      setCfg(s.config)
    },
    async reload() {
      const s = await call('get_state')
      setCfg(s.config)
    },
    run() { setBusy(true); call('run_pipeline_rect', null) },
    setMode(m) { call('set_mode', m) },
    startSnip() { call('start_snip') },
    quit() { call('quit_app') },
    dragBegin(w, x, y) { call('drag_begin', w, x, y) },
    dragMove(w, x, y) { call('drag_move', w, x, y) },
    dragEnd(w) { call('drag_end', w) },
  }), [cfg, status, result, history, busy, version, view])

  if (!cfg) return <div className="h-full grid place-items-center text-muted">正在连接后端…</div>

  return (
    <AppCtx.Provider value={api}>
      <ToastHost>
        {view === 'settings' ? <Settings />
          : view === 'mini' ? <MiniBar />
            : view === 'translate' ? <Translate />
              : <Overlay />}
      </ToastHost>
    </AppCtx.Provider>
  )
}

/* ------------------- 自由截图选择器(独立窗口) ------------------- */
import Snip from './Snip'
function Root() {
  const view = new URLSearchParams(location.search).get('view')
  if (location.pathname.includes('selector')) return <Snip />
  return <App key={view || 'overlay'} />
}

createRoot(document.getElementById('root')).render(<Root />)
