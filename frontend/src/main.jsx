import React, { createContext, useContext, useEffect, useMemo, useRef, useState } from 'react'
import { createRoot } from 'react-dom/client'
import './index.css'
import { call } from './bridge'
import { applyTheme, applyBackgroundImage, resolveTheme, PRESETS } from './theme'
import { DownloadHost, Icon, ToastHost, useToast } from './ui'
import Overlay from './Overlay'
import MiniBar from './MiniBar'
import Translate from './Translate'
import Settings from './Settings'

export const AppCtx = createContext(null)
export const useApp = () => useContext(AppCtx)

/* ------------------- 应用根 ------------------- */
// 事件总入口已在 bridge.js 中注册(框选页等独立入口也会加载它)
function App() {
  const view = new URLSearchParams(location.search).get('view') || 'overlay'
  const [cfg, setCfg] = useState(null)
  const [status, setStatus] = useState({ text: '就绪', tone: 'idle' })
  const [result, setResult] = useState(null)
  const [history, setHistory] = useState([])
  const [busy, setBusy] = useState(false)
  const [question, setQuestionRaw] = useState('')
  const [version, setVersion] = useState('')
  const [notice, setNotice] = useState(null)
  // 设置窗口打开期间禁用主界面交互(问题7);设置窗自己不受影响
  const [blocked, setBlocked] = useState(false)

  // 初始化:拉取状态 + 注册窗口级状态处理
  useEffect(() => {
    call('get_state').then((s) => {
      setCfg(s.config)
      if (typeof s.modal_block === 'boolean') setBlocked(s.modal_block)
      setVersion(s.version || '')
      if (s.history) setHistory(s.history)
      if (s.config?.behavior?.current_question) setQuestionRaw(s.config.behavior.current_question)
      setStatus({ text: s.key_ready ? '就绪 · Key 已配置' : '就绪 · Key 未配置', tone: s.key_ready ? 'idle' : 'warn' })
    })
    window.__ocrStateHandler = (ev) => {
      // status 只承载「AI 运行状态」(识别中/翻译中/完成/失败),会显示在状态灯旁;
      // notice 是「界面操作反馈」(已切换模式/已置顶…),走轻提示,不污染状态灯。
      if (ev.type === 'status') setStatus({ text: ev.text, tone: ev.tone || 'working' })
      if (ev.type === 'notice') setNotice({ text: ev.text, tone: ev.tone || 'ok', id: Date.now() })
      if (ev.type === 'result') { setResult(ev.data); setBusy(false) }
      if (ev.type === 'error') { setBusy(false); setStatus({ text: '失败', tone: 'danger' }); setResult({ error: ev.text }) }
      if (ev.type === 'config') setCfg(ev.config)
      if (ev.type === 'history') setHistory(ev.data)
      if (ev.type === 'busy') setBusy(!!ev.value)
      if (ev.type === 'modalBlock') setBlocked(!!ev.value)
    }
    return () => { delete window.__ocrStateHandler }
  }, [])

  // 跨窗口同步:任一模式改了提问内容,通过 config 广播让其它模式(独立网页上下文)同步
  useEffect(() => {
    const remote = cfg?.behavior?.current_question
    if (typeof remote === 'string' && remote !== question) setQuestionRaw(remote)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [cfg?.behavior?.current_question])

  // 主题应用(带上 ui.panelOpacity / 图片背景等附加项)
  useEffect(() => { if (cfg) applyTheme(resolveTheme(cfg.ui), cfg.ui) }, [cfg])

  // 图片背景是 data-URI 之外的本地 file:/// 路径,某些窗口(设置/翻译)自己也会
  // 调 applyTheme,这里额外保证一次,避免窗口间不同步。
  useEffect(() => { if (cfg?.ui) applyBackgroundImage(cfg.ui) }, [cfg?.ui?.bgImage, cfg?.ui?.bgImageOpacity,
    cfg?.ui?.bgImageBlur, cfg?.ui?.bgImageFit, cfg?.ui?.bgImageDim])

  const persistRef = useRef(0)
  const setQuestion = (v) => {
    setQuestionRaw(v)
    // 防抖持久化:切换模式/重启后仍保留用户填写的提问
    clearTimeout(persistRef.current)
    persistRef.current = setTimeout(() => call('set_config_value', 'behavior.current_question', v), 700)
  }

  const api = useMemo(() => ({
    cfg, setCfg, status, setStatus, result, setResult, history, setHistory, busy, setBusy, version, view,
    question, setQuestion,
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
    quit() { call('request_quit') },
    minimize() { call('minimize_app') },
    dragBegin(w, x, y) { call('drag_begin', w, x, y) },
    dragMove(w, x, y) { call('drag_move', w, x, y) },
    dragEnd(w) { call('drag_end', w) },
    /** 切换窗口置顶(后端统一处理并广播,状态由 config 回流) */
    toggleTopmost() { return call('toggle_topmost') },
  }), [cfg, status, result, history, busy, version, view, question])

  if (!cfg) return <div className="h-full grid place-items-center text-muted">正在连接后端…</div>

  return (
    <AppCtx.Provider value={api}>
      <ToastHost>
        <DownloadHost>
          {/* app-surface:承载自定义图片背景(问题3)。
              悬浮窗有"洞口"必须保持透明,所以它只拿图片变量、不铺底色(用 surface-transparent);
              设置/翻译/迷你条是整窗不透明的,正常铺底。 */}
          {/* 只有设置窗口是"整窗矩形"所以铺底色;其余窗口的根是圆角外壳,
              底色由外壳自己画 —— 一旦这里再铺一层,圆角外就会露出方形棱角。 */}
          <div className={`relative h-full ${view === 'settings' ? 'app-surface' : 'app-surface surface-transparent'}`}>
            {view === 'settings' ? <Settings />
              : view === 'mini' ? <MiniBar />
                : view === 'translate' ? <Translate />
                  : <Overlay />}
            {/* 设置打开时,主界面盖一层透明的输入拦截层:只挡点击/滚动,不挡视线 */}
            {blocked && view !== 'settings' && (
              <div className="modal-blocker" data-modal-blocker="1" aria-hidden="true" />
            )}
          </div>
          {/* NoticeHost:界面操作反馈的轻提示(不占 AI 状态位) */}
          {notice && <NoticeToast key={notice.id} notice={notice} onDone={() => setNotice(null)} />}
        </DownloadHost>
      </ToastHost>
    </AppCtx.Provider>
  )
}

/** 界面操作反馈的轻提示(问题14):短暂显示后自动消失,与 AI 状态灯互不影响。 */
function NoticeToast({ notice, onDone }) {
  useEffect(() => {
    const t = setTimeout(onDone, 2200)
    return () => clearTimeout(t)
  }, [notice.id])
  return (
    <div className="fixed bottom-3 left-1/2 -translate-x-1/2 z-[9990] pointer-events-none anim-pop">
      <div className="toast" data-tone={notice.tone}>
        <span className="text-muted" style={{ color: notice.tone === 'danger' ? 'var(--c-danger)' : 'var(--c-accent)' }}>
          <Icon name={notice.tone === 'danger' ? 'alert' : 'info'} size={13} />
        </span>
        <span>{notice.text}</span>
      </div>
    </div>
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
