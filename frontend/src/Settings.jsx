import React, { useEffect, useMemo, useRef, useState } from 'react'
import { call } from './bridge'
import { useApp } from './main'
import Guide, { useGuide } from './Guide'
import { applyTheme, applyBackgroundImage, resolveTheme, PRESETS, COLOR_FIELDS, BG_FITS } from './theme'
import { Btn, Card, ColorInput, Field, Icon, IconBtn, Logo, ModelTiers, Segmented, Switch, useToast } from './ui'

const NAV = [
  { key: 'model', label: '模型设置', icon: 'chip' },
  { key: 'general', label: '常规设置', icon: 'sliders' },
  { key: 'translate', label: '翻译设置', icon: 'translate' },
  { key: 'appearance', label: '外观主题', icon: 'palette' },
  { key: 'history', label: '识别历史', icon: 'history' },
  { key: 'guide', label: '新手教程', icon: 'wand' },
  { key: 'about', label: '关于应用', icon: 'info' },
]

export default function Settings() {
  const app = useApp()
  const [page, setPage] = useState('model')
  const guide = useGuide('settings')
  return (
    <div className="h-full flex gap-3.5 p-3.5" style={{ background: 'var(--c-bg)' }}>
      {/* 左侧导航 */}
      <aside className="w-[176px] settings-aside gap-1 p-2" data-guide="set-nav">
        <div className="flex items-center gap-2 px-1.5 py-1.5 mb-1 border-b" style={{ borderColor: 'var(--c-line)' }}>
          <Logo size={26} />
          <div className="min-w-0">
            <div className="font-semibold text-[14px] leading-tight truncate">OCR 助手</div>
            <div className="hint leading-tight">v{app.version}</div>
          </div>
        </div>
        <div className="hint px-1.5 pb-1">设置(自动保存)</div>
        {NAV.map((n) => {
          const active = page === n.key
          return (
            <button
              key={n.key}
              onClick={() => setPage(n.key)}
              aria-current={active ? 'page' : undefined}
              className={`nav-item ${active ? 'nav-item-active' : ''}`}
            >
              <Icon name={n.icon} size={16} />
              <span>{n.label}</span>
            </button>
          )
        })}
        <span className="flex-1 min-h-2" />
        <span data-guide="set-save" className="block px-0.5 pb-0.5">
          <Btn primary icon="check" className="w-full" onClick={() => call('close_settings')}>关闭并保存</Btn>
        </span>
      </aside>

      {/* 右侧内容:滚动只发生在内容区内部;模型页自己管理两个栏的滚动(问题1) */}
      <main className="flex-1 min-w-0 h-full">
        <div
          key={page}
          className={`page-enter h-full ${page === 'model' ? 'overflow-hidden' : 'overflow-auto pr-1'}`}
        >
          {page === 'model' && <ModelPage />}
          {page === 'general' && <GeneralPage />}
          {page === 'translate' && <TranslatePage />}
          {page === 'appearance' && <AppearancePage />}
          {page === 'history' && <HistoryPage />}
          {page === 'about' && <AboutPage />}
          {page === 'guide' && <GuidePage onGoPage={setPage} />}
        </div>
      </main>
      <Guide mode="settings" open={guide.open} onClose={guide.stop} />
    </div>
  )
}

/* ======================= 模型 ID 下拉输入 ======================= */
/**
 * 模型 ID 输入(问题2)。
 *
 * 旧实现用 <input list> + <datalist>:在 QtWebEngine 下点击输入框并不会展开候选,
 * 用户以为"下拉不起作用"。这里改成自绘下拉:输入框可以自由输入,右侧按钮/聚焦展开
 * 候选列表,支持键盘上下选择与回车确认。
 */
function ModelIdInput({ value, options = [], onChange, onFetch, fetching, placeholder, autoOpen }) {
  const [open, setOpen] = useState(!!autoOpen)
  const [hint, setHint] = useState(-1)
  const box = useRef(null)
  // 候选列表:输入框里有内容时,把匹配项排到最前,但**不隐藏其它候选** ——
  // 之前用 `hit.length ? hit : options`,已填值时会只剩它自己,表现为"拉到 2 个只显示 1 个"。
  const filtered = useMemo(() => {
    const q = (value || '').trim().toLowerCase()
    if (!q) return options
    const hit = options.filter((m) => m.toLowerCase().includes(q))
    const rest = options.filter((m) => !m.toLowerCase().includes(q))
    return [...hit, ...rest]
  }, [options, value])

  useEffect(() => {
    if (!open) return undefined
    const onDoc = (e) => { if (box.current && !box.current.contains(e.target)) setOpen(false) }
    document.addEventListener('mousedown', onDoc)
    return () => document.removeEventListener('mousedown', onDoc)
  }, [open])

  useEffect(() => { setHint(-1) }, [open, value])

  const pick = (m) => { onChange(m); setOpen(false) }

  const onKey = (e) => {
    if (e.key === 'ArrowDown' || e.key === 'ArrowUp') {
      if (!filtered.length) return
      e.preventDefault()
      if (!open) { setOpen(true); return }
      setHint((i) => {
        const next = e.key === 'ArrowDown' ? i + 1 : i - 1
        return (next + filtered.length) % filtered.length
      })
    } else if (e.key === 'Enter') {
      if (open && hint >= 0 && filtered[hint]) { e.preventDefault(); pick(filtered[hint]) }
      else setOpen(false)
    } else if (e.key === 'Escape') {
      setOpen(false)
    }
  }

  return (
    <div ref={box} className="relative">
      <div className="flex gap-2">
        <input
          className="ctl"
          value={value}
          placeholder={placeholder || '例如 qwen-vl-max / deepseek-chat / gpt-4o-mini'}
          onChange={(e) => onChange(e.target.value)}
          onFocus={() => { if (options.length) setOpen(true) }}
          onKeyDown={onKey}
          role="combobox"
          aria-expanded={open}
          aria-autocomplete="list"
        />
        <button
          type="button"
          className="btn shrink-0"
          disabled={!options.length}
          onClick={() => setOpen((o) => !o)}
          aria-label="展开常用模型"
          title={options.length ? '展开常用模型' : '该平台暂无预设模型'}
        >
          <Icon name="chevronDown" size={15} />
        </button>
        {onFetch && (
          <button
            type="button"
            className="btn shrink-0"
            disabled={!!fetching}
            onClick={onFetch}
            title="按上方 Base URL 从接口拉取该平台可用的模型列表"
            aria-label="从接口拉取模型列表"
          >
            <Icon name="cloud" size={15} className={fetching ? 'animate-spin' : ''} />
            {fetching ? '拉取中…' : '拉取'}
          </button>
        )}
      </div>
      {open && filtered.length > 0 && (
        <div className="model-menu anim-pop" role="listbox">
          <div className="model-menu-title">常用模型(点击填入,也可直接输入)</div>
          {filtered.map((m, i) => (
            <button
              key={m}
              type="button"
              role="option"
              aria-selected={m === value}
              className="model-menu-item"
              data-on={m === value ? '1' : '0'}
              data-hint={hint === i ? '1' : '0'}
              onMouseEnter={() => setHint(i)}
              onClick={() => pick(m)}
            >
              <Icon name="chip" size={13} />
              <span className="truncate">{m}</span>
              {m === value && <Icon name="check" size={13} className="ml-auto shrink-0" />}
            </button>
          ))}
        </div>
      )}
    </div>
  )
}

/* ======================= 模型设置(左:平台卡片 / 右:表单) ======================= */
function ModelPage() {
  const app = useApp()
  const toast = useToast()
  const [list, setList] = useState([])
  const [idx, setIdx] = useState(0)
  const [form, setForm] = useState(null)
  const [preview, setPreview] = useState('')
  const [test, setTest] = useState({ state: 'idle', ms: 0 })
  const [showKey, setShowKey] = useState(false)
  const [tplOpen, setTplOpen] = useState(false)
  const [tpl, setTpl] = useState('')
  const [activeId, setActiveId] = useState('')
  const [models, setModels] = useState([])
  const [fetched, setFetched] = useState([])      // 从接口拉取到的模型
  const [fetching, setFetching] = useState(false)
  const [forceOpen, setForceOpen] = useState(0)   // 递增:请求下拉展开一次

  const reload = async (keep) => {
    const r = await call('list_providers')
    setList(r.list || [])
    setActiveId(r.active || '')
    const n = keep ?? r.index ?? 0
    setIdx(n)
    loadForm(n)
  }
  const loadForm = async (i) => {
    const f = await call('provider_get', i)
    setForm(f.provider)
    setPreview(f.preview)
    setModels(f.models || [])
    setFetched([])                 // 换平台时清掉上一家的拉取结果
  }
  useEffect(() => { reload() }, [])

  // 接口拉取结果由后端异步推送(models 事件)
  useEffect(() => {
    const onEvent = (e) => {
      const ev = e.detail
      if (ev.type !== 'models') return
      setFetching(!!ev.pending)
      if (ev.pending) return
      const list = ev.list || []
      setFetched(list)
      if (ev.ok && list.length) {
        setForceOpen((n) => n + 1)      // 让下拉自动展开,直接看到拉取结果
        toast(`已拉取 ${list.length} 个模型,点选即可填入`)
      } else {
        toast(ev.message || '未能拉取模型列表', 'danger')
      }
    }
    window.addEventListener('ocr-event', onEvent)
    return () => window.removeEventListener('ocr-event', onEvent)
  }, [])

  const patch = async (field, value) => {
    setForm((f) => ({ ...f, [field]: value }))
    await call('provider_set', idx, field, value)
    setPreview(await call('provider_preview', idx))
  }

  const doTest = async () => {
    setTest({ state: 'testing', ms: 0 })
    await call('test_connection', idx)
  }

  // 连通性测试结果由后端异步推送(避免阻塞界面)
  useEffect(() => {
    const onEvent = (e) => {
      const ev = e.detail
      if (ev.type !== 'conn') return
      setTest({ state: ev.ok ? 'ok' : 'fail', ms: ev.ms || 0 })
      if (!ev.ok) toast(ev.message || '连接失败', 'danger')
    }
    window.addEventListener('ocr-event', onEvent)
    return () => window.removeEventListener('ocr-event', onEvent)
  }, [])

  const testStyle = {
    idle: { bg: 'var(--c-accent)', text: '测试连通性', icon: 'link' },
    testing: { bg: 'var(--c-muted)', text: '测试中…', icon: 'refresh' },
    ok: { bg: 'var(--c-ok)', text: '连接成功', icon: 'check' },
    fail: { bg: 'var(--c-danger)', text: '测试失败', icon: 'alert' },
  }[test.state]
  const latencyColor = test.ms < 1500 ? 'var(--c-ok)' : test.ms < 3500 ? 'var(--c-warn)' : 'var(--c-danger)'

  // 平台是否已配置:后端 list_providers 只回传 ready 布尔值(不回传 Key 本身),
  // 因此这里必须认 p.ready;以前只判断 p.api_key 会导致"填了 Key 仍显示未配置"。
  const ready = (p) => p.ready === true || !!(p.api_key || '').trim()
  const configured = list.filter(ready)
  const unconfigured = list.filter((p) => !ready(p))
  const activeItem = list.find((p) => p.id === activeId) || null

  /** 切换"当前使用的平台":只有已配置的平台可选(未配置项不显示选中标记) */
  const pickActive = async (p) => {
    if (!ready(p) || p.id === activeId) return
    const ok = await call('set_active_provider', p.id)
    if (!ok) { toast('该平台尚未配置,请先填写 API Key', 'danger'); return }
    setActiveId(p.id)
    setList((ls) => ls.map((x) => ({ ...x, active: x.id === p.id })))
    await app.reload()
    if (!(p.has_model)) toast(`已切换到「${p.name}」,但还没填模型 ID`, 'warn')
    else toast(`已切换到「${p.name}」`)
  }

  const Item = ({ p, i }) => (
    <div
      onClick={() => { setIdx(i); loadForm(i) }}
      className="group flex items-center gap-2 px-2 h-[34px] rounded-ctl border cursor-pointer transition-colors"
      data-active={p.id === activeId ? '1' : '0'}
      style={{
        background: p.id === activeId ? 'var(--c-accent-soft)'
          : (idx === i ? 'var(--c-sub)' : 'var(--c-card)'),
        borderColor: p.id === activeId ? 'var(--c-accent)' : (idx === i ? 'var(--c-accent)' : 'var(--c-line)'),
        opacity: ready(p) ? 1 : 0.62,
      }}
    >
      <span className="w-5 h-5 rounded-md grid place-items-center text-[10px] font-bold shrink-0"
            style={{ background: p.color || '#8b94a7', color: '#fff' }}>
        {p.name?.[0]}
      </span>
      <span className="truncate flex-1 text-[12.5px]">{p.name}</span>
      {ready(p) && !p.has_model && (
        <span className="hint shrink-0" title="还没填模型 ID" style={{ color: 'var(--c-warn)' }}>缺模型</span>
      )}
      {/* 选中标记:仅已配置的平台显示;点击即切换为"当前使用" */}
      {ready(p) ? (
        <button
          type="button"
          className="shrink-0 grid place-items-center no-drag"
          title={p.id === activeId ? '当前使用中' : '设为使用'}
          aria-pressed={p.id === activeId}
          onClick={(e) => { e.stopPropagation(); pickActive(p) }}
          style={{
            width: 18, height: 18, borderRadius: 999,
            border: `1.5px solid ${p.id === activeId ? 'var(--c-accent)' : 'var(--c-line)'}`,
            background: p.id === activeId ? 'var(--c-accent)' : 'transparent',
            color: p.id === activeId ? 'var(--c-accent-fg)' : 'var(--c-muted)',
          }}
        >
          {p.id === activeId && <Icon name="check" size={11} />}
        </button>
      ) : (
        <span className="shrink-0" style={{ width: 18 }} />
      )}
      <button
        className="opacity-0 group-hover:opacity-100 text-danger p-0.5 rounded hover:bg-danger/10 no-drag"
        title="删除平台"
        onClick={async (e) => {
          e.stopPropagation()
          if (!confirm(`确定删除平台「${p.name}」吗?`)) return
          await call('provider_remove', i)
          toast('已删除'); reload(Math.max(0, i - 1))
        }}
      ><Icon name="close" size={13} /></button>
    </div>
  )

  if (!form) return <div className="hint">加载中…</div>

  return (
    <div className="flex gap-3.5 h-full min-h-0">
      {/* 平台管理(问题1):这一栏固定在窗口中,只有它自己的平台列表在超出时内部滚动,
          不会跟着右侧表单一起滚走 */}
      <div className="w-[228px] settings-column gap-2 p-2.5 h-full">
        <div className="flex items-center gap-2 px-0.5 shrink-0">
          <Icon name="chip" size={15} className="text-accent" />
          <span className="font-semibold">AI 平台管理</span>
          <span className="flex-1" />
        </div>
        <div className="hint px-1 leading-snug shrink-0">
          右侧圆点 = <span style={{ color: 'var(--c-accent)' }}>当前使用</span>的平台;点圆点即可切换。
          未填 Key 的平台不可选中。
        </div>
        <div className="settings-column-scroll space-y-1.5">
          {configured.length > 0 && <div className="hint px-1">已配置({configured.length})</div>}
          {configured.map((p) => <Item key={p.id} p={p} i={list.indexOf(p)} />)}
          {unconfigured.length > 0 && <div className="hint px-1 pt-1">未配置({unconfigured.length})</div>}
          {unconfigured.map((p) => <Item key={p.id} p={p} i={list.indexOf(p)} />)}
        </div>
        {configured.length === 0 && (
          <div className="hint px-1" style={{ color: 'var(--c-warn)' }}>
            还没有可用的平台:请在右侧填写 API Key,填好后会自动选中。
          </div>
        )}
        {activeItem && !activeItem.has_model && (
          <div className="hint px-1" style={{ color: 'var(--c-warn)' }}>
            当前平台「{activeItem.name}」还没填模型 ID,请求会失败。
          </div>
        )}
        <Btn icon="plus" onClick={async () => { await call('provider_add'); reload(list.length) }}>自定义平台</Btn>
      </div>

      {/* 表单:只有这一栏滚动(问题1) */}
      <div className="flex-1 min-w-0 space-y-3.5 overflow-auto pr-1 h-full">
        <Card>
          <div className="flex items-center gap-3">
            <span className="w-10 h-10 rounded-card grid place-items-center text-[17px] font-bold shrink-0"
                  style={{ background: form.color, color: '#fff' }}>
              {form.name?.[0]}
            </span>
            <input className="ctl !w-[200px] font-semibold" value={form.name} onChange={(e) => patch('name', e.target.value)} />
            <span className="flex-1" />
            {test.state === 'ok' && <span style={{ color: latencyColor }} className="font-semibold text-[12.5px]">响应 {(test.ms / 1000).toFixed(1)}s</span>}
            <button
              className="btn border-transparent font-semibold"
              style={{ background: testStyle.bg, color: '#fff' }}
              disabled={test.state === 'testing'}
              onClick={doTest}
            >
              <Icon name={testStyle.icon} size={15} />
              {testStyle.text}
            </button>
          </div>
        </Card>

        <div className="space-y-2.5">
          <Field label="API Key">
            <div className="relative">
              <input
                className="ctl pr-9"
                type={showKey ? 'text' : 'password'}
                value={form.api_key || ''}
                placeholder="在平台控制台申请"
                onChange={(e) => patch('api_key', e.target.value)}
              />
              <span className="absolute right-1 top-1/2 -translate-y-1/2">
                <IconBtn icon={showKey ? 'eyeOff' : 'eye'} tip={showKey ? '隐藏' : '显示'}
                         size={15} onClick={() => setShowKey(!showKey)} />
              </span>
            </div>
          </Field>
          <Field label="模型 ID" hint={models.length ? '可从下拉选择常用模型,也可直接输入' : '该平台请手动填写模型 ID'}>
            <ModelIdInput
              key={`mid-${idx}-${forceOpen}`}
              value={form.model || ''}
              options={fetched.length ? fetched : models}
              fetching={fetching}
              autoOpen={!!forceOpen}
              onChange={(v) => patch('model', v)}
              onFetch={async () => {
                setFetching(true)
                await call('fetch_provider_models', idx)
              }}
            />
          </Field>
          <Field label="Base URL">
            <div className="flex gap-2">
              <input className="ctl" value={form.base_url || ''}
                     placeholder="例如 https://api.deepseek.com/v1"
                     onChange={(e) => patch('base_url', e.target.value)} />
              <Btn onClick={async () => {
                await call('reset_provider_defaults', idx)
                await loadForm(idx)
                toast('已恢复默认地址')
              }}>恢复默认</Btn>
            </div>
          </Field>
          <Field label="官网链接">
            <div className="flex gap-2">
              <input className="ctl" value={form.homepage || ''} onChange={(e) => patch('homepage', e.target.value)} />
              <Btn onClick={() => call('open_url', form.homepage)}>打开</Btn>
            </div>
          </Field>
          <Field label="备注">
            <input className="ctl" value={form.note || ''} onChange={(e) => patch('note', e.target.value)} />
          </Field>
          <Field label="思考模式" hint="开启后推理更强但更慢">
            <Switch checked={!!form.enable_thinking} onChange={(v) => patch('enable_thinking', v)} label={form.enable_thinking ? '已开启' : '已关闭(响应更快)'} />
          </Field>
        </div>

        <Card title="JSON 请求预览" desc="随字段实时生成,可直接编辑模板"
              right={<Btn onClick={async () => { setTpl(await call('get_template')); setTplOpen(true) }}>编辑模板</Btn>}>
          <pre className="text-[12px] leading-relaxed inset p-2 max-h-56 overflow-auto">{preview}</pre>
        </Card>
      </div>

      {tplOpen && (
        <div className="fixed inset-0 bg-black/40 grid place-items-center z-50" onClick={() => setTplOpen(false)}>
          <div className="w-[680px] max-h-[80vh] card p-4 space-y-3" onClick={(e) => e.stopPropagation()}>
            <div className="font-bold">JSON 请求模板</div>
            <p className="hint">占位符 {'{model}'} / {'{prompt}'} / {'{image_url}'} 会自动替换为 JSON 值(勿加引号)。</p>
            <textarea className="ctl h-72 font-mono text-[12px]" value={tpl} onChange={(e) => setTpl(e.target.value)} />
            <div className="flex justify-end gap-2">
              <Btn onClick={async () => { setTpl(await call('reset_template')); toast('已恢复默认模板') }}>恢复默认模板</Btn>
              <Btn onClick={() => setTplOpen(false)}>取消</Btn>
              <Btn primary onClick={async () => {
                const r = await call('set_template', tpl)
                if (r === true) { setTplOpen(false); setPreview(await call('provider_preview', idx)); toast('模板已保存') }
                else toast(String(r), 'danger')
              }}>保存</Btn>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

/** 滑杆 + 数值(设置页统一控件) */
function SliderRow({ value, min, max, step = 1, onChange, suffix = '' }) {
  return (
    <div className="flex items-center gap-3">
      <input
        type="range" className="flex-1" min={min} max={max} step={step} value={value}
        onChange={(e) => onChange(+e.target.value)}
      />
      <span className="hint w-12 text-right tabular-nums">{value}{suffix}</span>
    </div>
  )
}

/* ======================= 快捷键录入(问题5) ======================= */
/** 后端默认值(用于「恢复默认」);与 app/config.py 的 DEFAULT_CONFIG.hotkeys 保持一致 */
const cfgmodDefaults = {
  capture: 'ctrl+f1',
  snip: 'ctrl+shift+a',
  modeOverlay: 'ctrl+1',
  modeMini: 'ctrl+2',
  modeSnip: 'ctrl+3',
  modeTranslate: 'ctrl+4',
  topmost: 'ctrl+t',
  exit: 'ctrl+q',
}

const HOTKEY_FIELDS = [
  ['capture', '识别(截图并识别)', '悬浮窗模式抓取洞口内容;迷你条模式下直接进入框选'],
  ['snip', '自由截图/框选', '进入全屏遮罩拖拽框选'],
  ['modeOverlay', '切到悬浮窗', ''],
  ['modeMini', '切到迷你条', ''],
  ['modeSnip', '切到自由框选', '与「自由截图」同一个目标,可分别设置'],
  ['modeTranslate', '切到翻译模式', ''],
  ['topmost', '切换窗口置顶', '一次按下在置顶/取消置顶之间切换'],
  ['exit', '退出程序', '按退出方式设置处理(询问/托盘/直接退出)'],
]

const MOD_KEYS = new Set(['Control', 'Alt', 'Shift', 'Meta', 'AltGraph', 'CapsLock', 'NumLock', 'ScrollLock'])

/** 把 KeyboardEvent 转成后端 keyboard 库认识的组合键串(如 ctrl+shift+a)。 */
export function comboFromEvent(e) {
  const mods = []
  if (e.ctrlKey) mods.push('ctrl')
  if (e.altKey) mods.push('alt')
  if (e.shiftKey) mods.push('shift')
  if (e.metaKey) mods.push('win')
  const key = normalizeKey(e)
  if (!key) return ''                    // 只按了修饰键:继续等待
  return [...mods, key].join('+')
}

function normalizeKey(e) {
  const k = e.key
  if (!k || MOD_KEYS.has(k)) return ''
  if (k === ' ') return 'space'
  if (k === 'Escape') return 'esc'
  if (k === 'ArrowUp') return 'up'
  if (k === 'ArrowDown') return 'down'
  if (k === 'ArrowLeft') return 'left'
  if (k === 'ArrowRight') return 'right'
  if (k === 'Enter') return 'enter'
  if (k === 'Tab') return 'tab'
  if (k === 'Backspace') return 'backspace'
  if (k === 'Delete') return 'delete'
  if (k === 'Home') return 'home'
  if (k === 'End') return 'end'
  if (k === 'PageUp') return 'page up'
  if (k === 'PageDown') return 'page down'
  if (k === 'Insert') return 'insert'
  if (k === 'PrintScreen') return 'print screen'
  if (k.startsWith('F') && /^F\d{1,2}$/.test(k)) return k.toLowerCase()
  // 字母/数字/标点:统一小写
  if (k.length === 1) return k.toLowerCase()
  return k.toLowerCase()
}

/** 组合键展示:ctrl+shift+a -> Ctrl + Shift + A */
export function prettyCombo(combo) {
  if (!combo) return '未设置'
  return combo.split('+').map((p) => {
    const t = p.trim()
    if (!t) return t
    if (t.length === 1) return t.toUpperCase()
    return t.charAt(0).toUpperCase() + t.slice(1)
  }).join(' + ')
}

/**
 * 快捷键录入框(问题5):聚焦后进入"监听"状态,按下组合键实时显示。
 * 不依赖文本框输入,彻底避免"用户手动敲字符串"造成的格式错误。
 */
function HotkeyInput({ value, defaultValue, onChange }) {
  const [listening, setListening] = useState(false)
  const [preview, setPreview] = useState('')
  const onKeyDown = (e) => {
    if (!listening) return
    e.preventDefault()
    e.stopPropagation()
    if (e.key === 'Backspace' || e.key === 'Delete') {
      onChange('')
      setPreview('')
      setListening(false)
      return
    }
    if (e.key === 'Escape') {
      setPreview('')
      setListening(false)
      return
    }
    const combo = comboFromEvent(e)
    if (!combo) { setPreview(''); return }   // 只按修饰键:显示"等待主键"
    const mods = []
    if (e.ctrlKey) mods.push('Ctrl')
    if (e.altKey) mods.push('Alt')
    if (e.shiftKey) mods.push('Shift')
    if (e.metaKey) mods.push('Win')
    setPreview([...mods, ...(combo.split('+').slice(mods.length)).map((p) => p.toUpperCase())].join(' + '))
    onChange(combo)
  }
  return (
    <div className="flex items-center gap-2">
      <button
        type="button"
        className={`hotkey-box ${listening ? 'hotkey-box-listening' : ''}`}
        onClick={() => { setListening(true); setPreview('') }}
        onBlur={() => { setListening(false); setPreview('') }}
        onKeyDown={onKeyDown}
      >
        {listening
          ? <span className="hotkey-live">{preview || '请按下组合键…'}</span>
          : <span className="font-mono text-[12.5px]">{prettyCombo(value)}</span>}
      </button>
      {listening && (
        <span className="hint shrink-0 flex items-center gap-1">
          <Icon name="info" size={12} />按下即生效
        </span>
      )}
      <span className="flex-1" />
      <Btn
        className="!h-7 !text-[12px] shrink-0"
        disabled={!defaultValue || value === defaultValue}
        onClick={() => onChange(defaultValue)}
        title="恢复该快捷键的默认值"
      >恢复默认</Btn>
    </div>
  )
}

/* ======================= 常规设置 ======================= */
function GeneralPage() {
  const app = useApp()
  const toast = useToast()
  const [local, setLocal] = useState(app.cfg)
  useEffect(() => setLocal(app.cfg), [app.cfg])

  const set = async (path, value) => {
    await call('set_config_value', path, value)
    await app.reload()
  }

  return (
    <div className="space-y-3">
      <Card title="AI 设置" icon="chip">
        <div className="space-y-2">
          <Field label="是否启用云端OCR" hint="云端:用所选大模型识别(更准,耗token);本地:内置 RapidOCR(离线免费、轻量快速)">
            <Segmented
              value={local.ocr?.mode || 'cloud'}
              options={[{ value: 'cloud', label: '云端' }, { value: 'local', label: '本地' }]}
              onChange={(v) => set('ocr.mode', v)}
            />
          </Field>
          <Field label="模型最长响应时间">
            <div className="flex items-center gap-2">
              <input type="number" className="ctl !w-24 text-right" value={local.timeout ?? 180}
                     onChange={(e) => setLocal({ ...local, timeout: +e.target.value })}
                     onBlur={(e) => set('timeout', +e.target.value)} />
              <span className="hint">秒</span>
            </div>
          </Field>
          <Field label="失败自动尝试次数">
            <div className="flex items-center gap-2">
              <input type="number" className="ctl !w-24 text-right" value={local.retry?.max_retries ?? 3}
                     onChange={(e) => setLocal({ ...local, retry: { ...local.retry, max_retries: +e.target.value } })}
                     onBlur={(e) => set('retry.max_retries', +e.target.value)} />
              <span className="hint">次</span>
            </div>
          </Field>
          <Field label="图片压缩上限" hint="发送前长边像素上限">
            <input type="number" className="ctl !w-28 text-right" value={local.capture?.max_side ?? 2048}
                   onBlur={(e) => set('capture.max_side', +e.target.value)} />
          </Field>
        </div>
      </Card>

      <Card title="保存设置" icon="folder">
        <div className="space-y-2">
          <Field label="应用缓存位置">
            <div className="flex gap-2">
              <input className="ctl" value={local.storage?.cache_dir || ''} readOnly />
              <Btn onClick={async () => { const d = await call('pick_directory'); if (d) set('storage.cache_dir', d) }}>浏览…</Btn>
            </div>
          </Field>
          <Field label="题目保存位置">
            <div className="flex gap-2">
              <input className="ctl" value={local.storage?.questions_dir || ''} readOnly />
              <Btn onClick={async () => { const d = await call('pick_directory'); if (d) set('storage.questions_dir', d) }}>浏览…</Btn>
            </div>
          </Field>
          <Field label="本地知识库">
            <Switch checked={!!local.storage?.add_to_knowledge} onChange={(v) => set('storage.add_to_knowledge', v)}
                    label="将 AI 回答自动添加到本地知识库" />
          </Field>
        </div>
      </Card>

      <Card title="行为与快捷键" icon="sliders">
        <div className="space-y-2">
          <Field label="关闭程序时" hint="点电源键或按 Ctrl+Q 时的行为">
            <Segmented value={app.cfg.behavior?.quit_action || 'ask'}
                       options={[{ value: 'ask', label: '每次都问' },
                                 { value: 'tray', label: '最小化到托盘' },
                                 { value: 'exit', label: '直接退出' }]}
                       onChange={(v) => call('set_quit_action', v).then(() => app.reload())} />
          </Field>
          <Field label="默认提问">
            <input className="ctl" value={local.behavior?.default_question || ''}
                   onBlur={(e) => set('behavior.default_question', e.target.value)}
                   onChange={(e) => setLocal({ ...local, behavior: { ...local.behavior, default_question: e.target.value } })} />
          </Field>
          <div className="hint px-1">
            点右侧输入框后「直接按下」组合键即可录入(实时显示);Backspace 清除,禁用某些键请留空。
          </div>
          {HOTKEY_FIELDS.map(([k, label, hint]) => (
            <Field key={k} label={label} hint={hint} width={150}>
              <HotkeyInput
                value={local.hotkeys?.[k] || ''}
                defaultValue={cfgmodDefaults[k] || ''}
                onChange={(v) => {
                  setLocal({ ...local, hotkeys: { ...local.hotkeys, [k]: v } })
                  set('hotkeys.' + k, v)
                }}
              />
            </Field>
          ))}
        </div>
      </Card>

      <Card title="提示词设置" icon="text">
        <div className="space-y-2">
          <div className="hint">回答提示词可用占位符:{'{question}'} {'{ocr_text}'} {'{qtype}'} {'{qtitle}'} {'{options}'}</div>
          <textarea className="ctl h-24 font-mono text-[12px]" value={local.prompts?.ocr || ''}
                    onChange={(e) => setLocal({ ...local, prompts: { ...local.prompts, ocr: e.target.value } })}
                    onBlur={(e) => set('prompts.ocr', e.target.value)} />
          <textarea className="ctl h-32 font-mono text-[12px]" value={local.prompts?.answer || ''}
                    onChange={(e) => setLocal({ ...local, prompts: { ...local.prompts, answer: e.target.value } })}
                    onBlur={(e) => set('prompts.answer', e.target.value)} />
        </div>
      </Card>

      <div className="flex gap-2">
        <Btn onClick={() => call('open_config_file')}>打开配置文件</Btn>
        <Btn onClick={() => call('open_data_dir')}>打开缓存目录</Btn>
        <span className="flex-1" />
        <span className="hint self-center">所有修改自动保存</span>
      </div>
    </div>
  )
}

/* ======================= 翻译设置 ======================= */
function TranslatePage() {
  const app = useApp()
  const toast = useToast()
  const [local, setLocal] = useState(app.cfg)
  const [langs, setLangs] = useState([])
  const [status, setStatus] = useState(null)
  const [models, setModels] = useState(null)
  useEffect(() => setLocal(app.cfg), [app.cfg])
  useEffect(() => {
    call('languages').then((r) => setLangs(r.list || []))
    call('translate_status').then(setStatus)
    call('local_models_status').then(setModels)
  }, [])
  useEffect(() => {
    const onEvent = (e) => {
      const ev = e.detail
      if (ev.type === 'pack') {
        toast(ev.message, ev.ok ? 'ok' : 'danger')
        call('translate_status').then(setStatus)
      }
      if (ev.type === 'download' && ev.done) {
        call('local_models_status').then(setModels)
        if (ev.error) toast(ev.error, 'danger')
        else if (ev.message) toast(ev.message)
      }
    }
    window.addEventListener('ocr-event', onEvent)
    return () => window.removeEventListener('ocr-event', onEvent)
  }, [])

  const set = async (path, value) => {
    await call('set_config_value', path, value)
    await app.reload()
  }
  const tr = local.translate || {}

  return (
    <div className="space-y-3">
      <Card title="翻译方式" icon="translate" desc="云端=当前 AI 平台;端侧=本机模型,离线可用">
        <div className="space-y-2">
          <Field label="翻译引擎" hint="开=云端大模型,关=端侧模型">
            <Segmented value={tr.mode || 'cloud'}
                       options={[{ value: 'cloud', label: '云端翻译', icon: 'cloud' },
                                 { value: 'local', label: '端侧翻译', icon: 'cpu' }]}
                       onChange={(v) => set('translate.mode', v)} />
          </Field>
          <Field label="端侧引擎" hint="自动:优先端侧离线模型,其次本机 Ollama">
            <Segmented value={tr.engine || 'auto'}
                       options={[{ value: 'auto', label: '自动' }, { value: 'argos', label: 'Argos 端侧模型' },
                                 { value: 'ollama', label: 'Ollama' }]}
                       onChange={(v) => set('translate.engine', v)} />
          </Field>
          <Field label="默认语言方向">
            <div className="flex items-center gap-2">
              <select className="ctl !w-[120px]" value={tr.source_lang || '自动检测'}
                      onChange={(e) => set('translate.source_lang', e.target.value)}>
                {langs.map((l) => <option key={l} value={l}>{l}</option>)}
              </select>
              <span className="text-muted">到</span>
              <select className="ctl !w-[120px]" value={tr.target_lang || '中文'}
                      onChange={(e) => set('translate.target_lang', e.target.value)}>
                {langs.filter((l) => l !== '自动检测').map((l) => <option key={l} value={l}>{l}</option>)}
              </select>
            </div>
          </Field>
          <Field label="默认展示方式">
            <Segmented value={tr.display || 'bilingual'}
                       options={[{ value: 'bilingual', label: '双语对照' }, { value: 'translated', label: '仅译文' },
                                 { value: 'source', label: '仅原文' }]}
                       onChange={(v) => set('translate.display', v)} />
          </Field>
        </div>
      </Card>

      <Card title="端侧模型管理" icon="download"
            desc="按需下载,不随应用分发;识别可选三档,翻译为离线专用模型"
            right={<><Segmented size="sm" value={models?.source || 'auto'}
                                 options={[{ value: 'auto', label: '自动' }, { value: 'hf', label: '官方' },
                                           { value: 'mirror', label: 'hf-mirror' }]}
                                 onChange={(v) => call('set_local_tier', 'source', v)
                                   .then(() => call('local_models_status').then(setModels))} />
                     <Btn className="ml-2" icon="refresh"
                          onClick={() => call('local_models_status').then(setModels)}>刷新</Btn></>}>
        <div className="space-y-3">
          <div>
            <div className="flex items-center gap-2 mb-1.5">
              <Icon name="scan" size={14} className="text-muted" />
              <span className="font-medium text-[12.5px]">识别模型(OCR)</span>
              <span className="hint">下载源:{models?.source === 'mirror' ? 'hf-mirror' : models?.source === 'hf' ? '官方' : '自动'}</span>
            </div>
            <ModelTiers kind="ocr" tiers={models?.tiers?.ocr || []} current={models?.current?.ocr}
                        onSelect={(t) => call('set_local_tier', 'ocr', t).then(() => call('local_models_status').then(setModels))}
                        onDownload={(t) => { call('download_local_model', 'ocr', t); toast('已开始下载(进度见右下角)') }}
                        onRemove={async (t) => { toast(await call('remove_local_model', 'ocr', t)); call('local_models_status').then(setModels) }} />
          </div>
          <div>
            <div className="flex items-center gap-2 mb-1.5">
              <Icon name="translate" size={14} className="text-muted" />
              <span className="font-medium text-[12.5px]">翻译模型(端侧)</span>
            </div>
            <ModelTiers kind="mt" tiers={models?.tiers?.mt || []} current={models?.current?.mt}
                        onSelect={(t) => call('set_local_tier', 'mt', t).then(() => call('local_models_status').then(setModels))}
                        onDownload={(t) => { call('download_local_model', 'mt', t); toast('已开始下载(进度见右下角)') }}
                        onRemove={async (t) => { toast(await call('remove_local_model', 'mt', t)); call('local_models_status').then(setModels) }} />
            <div className="inset px-3 py-2 mt-2 flex items-center gap-2 text-[12px]">
              <span className="text-muted shrink-0">推理运行时</span>
              {models?.runtime?.ready
                ? <span className="chip" style={{ color: 'var(--c-ok)', borderColor: 'var(--c-ok)' }}>已就绪</span>
                : <Btn className="!h-7 !text-[12px]" icon="download"
                       onClick={() => { call('download_local_model', 'runtime'); toast('已开始下载运行时') }}>下载(约 62MB)</Btn>}
              <span className="hint">轻量档准确度有限,追求质量请用云端或均衡/全量档</span>
            </div>
          </div>
          <div className="hint">模型目录:{models?.root || 'models/'}(删除档位即释放对应空间)</div>
        </div>
      </Card>

      <Card title="自动刷新" icon="refresh" desc="定时重新捕获同一区域并翻译,适合字幕/连续内容">
        <div className="space-y-2">
          <Field label="自动刷新">
            <Switch checked={!!tr.auto_refresh} onChange={(v) => set('translate.auto_refresh', v)}
                    label={tr.auto_refresh ? '已开启(翻译模式下生效)' : '已关闭'} />
          </Field>
          <Field label="刷新间隔">
            <div className="flex items-center gap-2">
              <input type="number" className="ctl !w-24 text-right" value={tr.auto_interval_ms ?? 2500}
                     onChange={(e) => setLocal({ ...local, translate: { ...tr, auto_interval_ms: +e.target.value } })}
                     onBlur={(e) => set('translate.auto_interval_ms', +e.target.value)} />
              <span className="hint">毫秒</span>
            </div>
          </Field>
        </div>
      </Card>

      <Card title="提问与提示词" icon="text" desc="示例提问用于主界面下拉;自输入内容会自动记住">
        <div className="space-y-2">
          <Field label="示例提问" hint="每行一条">
            <textarea className="ctl h-28 text-[12px]" value={(local.behavior?.question_presets || []).join('\n')}
                      onChange={(e) => setLocal({
                        ...local,
                        behavior: {
                          ...local.behavior,
                          question_presets: e.target.value.split('\n'),
                        },
                      })}
                      onBlur={(e) => set('behavior.question_presets',
                        e.target.value.split('\n').map((s) => s.trim()).filter(Boolean))} />
          </Field>
          <Field label="默认提问">
            <input className="ctl" value={local.behavior?.default_question || ''}
                   onChange={(e) => setLocal({ ...local, behavior: { ...local.behavior, default_question: e.target.value } })}
                   onBlur={(e) => set('behavior.default_question', e.target.value)} />
          </Field>
          <Field label="已记住的提问" hint={`${(local.behavior?.question_history || []).length} 条(最多 20)`}
                 width={150}>
            <div className="flex items-center gap-2 flex-wrap">
              <span className="hint truncate">{(local.behavior?.question_history || []).join(' / ') || '暂无'}</span>
              <Btn onClick={() => set('behavior.question_history', [])}>清空</Btn>
            </div>
          </Field>
          <Field label="翻译提示词" hint="占位符 {source_lang} / {target_lang} / {ocr_text}">
            <textarea className="ctl h-40 font-mono text-[12px]" value={local.prompts?.translate || ''}
                      onChange={(e) => setLocal({ ...local, prompts: { ...local.prompts, translate: e.target.value } })}
                      onBlur={(e) => set('prompts.translate', e.target.value)} />
          </Field>
        </div>
      </Card>
    </div>
  )
}

/* ======================= 外观主题 ======================= */
function AppearancePage() {
  const app = useApp()
  const toast = useToast()
  const ui = app.cfg.ui || {}
  const winCfg = app.cfg.window || {}
  const [draft, setDraft] = useState(ui.customTheme || resolveTheme(ui))

  const setUi = (patch) => {
    const next = { ...ui, ...patch }
    app.setUi(patch)
    applyTheme(resolveTheme(next), next)
    applyBackgroundImage(next)      // 图片背景即时预览(问题3)
  }

  const pickPreset = (key) => {
    setUi({ theme: key })
    applyTheme(PRESETS[key], ui)
    toast(`已切换主题:${PRESETS[key].name}`)
  }

  const editColor = (field, value) => {
    const next = { ...draft, colors: { ...draft.colors, [field]: value } }
    setDraft(next)
    setUi({ theme: 'custom', customTheme: next })
  }

  const applyCustom = () => {
    setUi({ theme: 'custom', customTheme: draft })
    toast('已应用自定义主题')
  }

  return (
    <div className="space-y-3">
      <Card title="全局主题" icon="palette" desc="点击即可全局生效(所有窗口同步)">
        <div className="flex flex-wrap gap-2">
          {Object.entries(PRESETS).map(([key, t]) => (
            <button
              key={key}
              onClick={() => pickPreset(key)}
              className="w-[110px] rounded-card border p-2 text-left transition-transform hover:scale-[1.03]"
              style={{ background: t.colors.bg, borderColor: ui.theme === key ? 'var(--c-accent)' : t.colors.line }}
            >
              <div className="flex gap-1 mb-2">
                {['accent', 'card', 'fg', 'ok', 'danger'].map((c) => (
                  <span key={c} className="w-4 h-4 rounded" style={{ background: t.colors[c] }} />
                ))}
              </div>
              <div className="text-[12px] font-semibold" style={{ color: t.colors.fg }}>{t.name}</div>
            </button>
          ))}
          <button
            onClick={() => setUi({ theme: 'custom' })}
            className="w-[110px] rounded-card border p-2 text-left"
            style={{ borderColor: ui.theme === 'custom' ? 'var(--c-accent)' : 'var(--c-line)' }}
          >
            <div className="text-[12px] font-semibold">自定义</div>
            <div className="hint">编辑下方配色</div>
          </button>
        </div>
      </Card>

      <Card title="自定义主题" icon="grid" desc="逐项调整配色,实时预览" right={<><Btn onClick={applyCustom}>应用</Btn>
        <Btn className="ml-2" onClick={() => call('export_theme', JSON.stringify(draft))}>导出</Btn>
        <Btn className="ml-2" onClick={async () => { const t = await call('import_theme'); if (t) { try { const o = JSON.parse(t); setDraft(o); setUi({ theme: 'custom', customTheme: o }); toast('已导入') } catch { toast('文件格式错误', 'danger') } } }}>导入</Btn></>}>
        <div className="grid grid-cols-2 gap-2">
          {COLOR_FIELDS.map(([key, label]) => (
            <div key={key} className="flex items-center justify-between px-3 py-2 rounded-ctl border border-line">
              <span>{label}</span>
              <ColorInput value={draft.colors?.[key]} onChange={(v) => editColor(key, v)} />
            </div>
          ))}
        </div>
      </Card>

      <Card title="自定义图片背景" icon="image"
            desc="给面板、设置页与翻译页铺一张图片;悬浮窗的洞口区域始终透明,不受影响">
        <div className="space-y-2">
          <Field label="背景图片"
                 hint="选择后立即应用到全部窗口(设置除外);支持 png / jpg / webp / bmp / gif">
            <div className="flex gap-2 items-center">
              <input className="ctl" value={ui.bgImage || ''} readOnly placeholder="未选择图片" />
              <Btn primary onClick={async () => {
                const uri = await call('pick_background_image')
                if (!uri) return
                setUi({ bgImage: uri })
                toast('已应用背景图片')
              }}>选择图片…</Btn>
              <Btn danger disabled={!ui.bgImage} onClick={() => { setUi({ bgImage: '' }); toast('已移除背景图片') }}>移除</Btn>
            </div>
          </Field>
          {ui.bgImage && (
            <>
              <Field label="显示方式">
                <Segmented size="sm" value={ui.bgImageFit || 'cover'}
                           options={BG_FITS.map((f) => ({ value: f.value, label: f.label }))}
                           onChange={(v) => setUi({ bgImageFit: v })} />
              </Field>
              {/* 这里不再另做"预览块":下面的滑杆是直接应用到所有窗口的,
                  改一项就能立刻在旁边(以及各模式窗口)看到真实效果。 */}
              <Field label="不透明度" hint="调节后立即应用到所有窗口,所见即所得">
                <SliderRow value={ui.bgImageOpacity ?? 100} min={10} max={100}
                           onChange={(v) => setUi({ bgImageOpacity: v })} suffix="%" />
              </Field>
              <Field label="模糊" hint="模糊后更容易看清上面的文字">
                <SliderRow value={ui.bgImageBlur ?? 0} min={0} max={30}
                           onChange={(v) => setUi({ bgImageBlur: v })} suffix="px" />
              </Field>
              <Field label="压暗" hint="图片过亮时调高,提升文字对比度">
                <SliderRow value={ui.bgImageDim ?? 0} min={0} max={80}
                           onChange={(v) => setUi({ bgImageDim: v })} suffix="%" />
              </Field>
              <div className="hint px-1">
                提示:当前效果已实时应用到设置页与各模式窗口;如需更明显的对比,可先把窗口切到悬浮窗或翻译模式再回来调。
              </div>
            </>
          )}
        </div>
      </Card>

      <Card title="形态与细节" icon="sliders">
        <div className="space-y-2">
          <Field label="圆角大小">
            <div className="flex items-center gap-3">
              <input type="range" min="0" max="24" value={ui.radius ?? 12}
                     onChange={(e) => setUi({ radius: +e.target.value })} className="flex-1" />
              <span className="hint w-10 text-right">{ui.radius ?? 12}px</span>
            </div>
          </Field>
          <Field label="界面字号">
            <div className="flex items-center gap-3">
              <input type="range" min="11" max="18" value={ui.fontSize ?? 13}
                     onChange={(e) => setUi({ fontSize: +e.target.value })} className="flex-1" />
              <span className="hint w-10 text-right">{ui.fontSize ?? 13}px</span>
            </div>
          </Field>
          <Field label="洞口边框">
            <div className="flex items-center gap-3">
              <ColorInput value={ui.holeColor || '#ff5252'} onChange={(v) => setUi({ holeColor: v })} />
              <Segmented value={ui.holeStyle || 'dashed'}
                         options={[{ value: 'solid', label: '实线' }, { value: 'dashed', label: '虚线' }, { value: 'dotted', label: '点线' }]}
                         onChange={(v) => setUi({ holeStyle: v })} />
            </div>
          </Field>
          <Field label="面板不透明度">
            <div className="flex items-center gap-3">
              <input type="range" min="60" max="100" value={ui.panelOpacity ?? 96}
                     onChange={(e) => setUi({ panelOpacity: +e.target.value })} className="flex-1" />
              <span className="hint w-10 text-right">{ui.panelOpacity ?? 96}%</span>
            </div>
          </Field>
          <Field label="窗口尺寸" hint="各模式尺寸互相独立;迷你条高度恒定">
            <div className="flex items-center gap-2">
              <Btn onClick={async () => {
                await call('reset_window_sizes')
                toast('已恢复三个模式的默认尺寸')
              }}>恢复默认尺寸</Btn>
              <span className="hint">
                悬浮窗 {winCfg.defaultWidth ?? 640}x{winCfg.defaultHeight ?? 680}
                ,迷你条 {winCfg.defaultMiniWidth ?? 420}x{winCfg.defaultMiniHeight ?? 78}
                ,翻译窗 {winCfg.defaultTranslateWidth ?? 760}x{winCfg.defaultTranslateHeight ?? 620}
              </span>
            </div>
          </Field>
        </div>
      </Card>
    </div>
  )
}

/* ======================= 识别历史(问题4:时间线) ======================= */
/** 相对时间:今天 / 昨天 / N 天前,便于时间线快速定位 */
function relTime(timeStr) {
  if (!timeStr) return ''
  const t = new Date(String(timeStr).replace(/-/g, '/')).getTime()
  if (!t || Number.isNaN(t)) return timeStr
  const diff = Date.now() - t
  const day = 86400000
  if (diff < 60000) return '刚刚'
  if (diff < 3600000) return `${Math.floor(diff / 60000)} 分钟前`
  if (diff < day) return `${Math.floor(diff / 3600000)} 小时前`
  const days = Math.floor(diff / day)
  if (days === 1) return '昨天'
  if (days < 30) return `${days} 天前`
  return timeStr.slice(0, 10)
}

/** 结果来源的视觉编码:模型/知识库/翻译用不同颜色,便于一眼区分 */
function sourceTone(src) {
  const s = String(src || '')
  if (s.includes('知识库')) return { color: 'var(--c-ok)', label: '知识库' }
  if (s.includes('翻译')) return { color: 'var(--c-accent)', label: '翻译' }
  if (s.includes('模型')) return { color: 'var(--c-warn)', label: '模型' }
  return { color: 'var(--c-muted)', label: s || '—' }
}

const HISTORY_FILTERS = [
  { value: 'all', label: '全部' },
  { value: 'answer', label: '识别答题' },
  { value: 'translate', label: '翻译' },
  { value: 'knowledge', label: '本地知识库' },
]

function HistoryPage() {
  const app = useApp()
  const toast = useToast()
  const [filter, setFilter] = useState('all')
  const [expanded, setExpanded] = useState({})
  // 分页渲染:历史最多 100 条,一次性铺满会在切换页面时明显卡顿
  const [limit, setLimit] = useState(30)
  useEffect(() => { call('history_list').then(app.setHistory) }, [])
  const all = app.history || []

  const list = useMemo(() => {
    if (filter === 'all') return all
    return all.filter((h) => {
      const src = String(h.source || '')
      const isTr = h.task === 'translate' || src.includes('翻译')
      if (filter === 'translate') return isTr
      if (filter === 'knowledge') return src.includes('知识库')
      return !isTr && !src.includes('知识库')   // answer
    })
  }, [all, filter])

  // 过滤条件变化时回到第一页,避免"切换筛选后还停在上次的分页深度"
  useEffect(() => { setLimit(30) }, [filter])
  const shown = useMemo(() => list.slice(0, limit), [list, limit])

  // 关键数据:总条数 / 知识库命中率 / 平均总耗时
  const stats = useMemo(() => {
    const total = all.length
    const kb = all.filter((h) => String(h.source || '').includes('知识库')).length
    const durs = all.map((h) => (Number(h.ocr_time) || 0) + (Number(h.answer_time) || 0)).filter((d) => d > 0)
    const avg = durs.length ? durs.reduce((a, b) => a + b, 0) / durs.length : 0
    return { total, kb, avg, kbRate: total ? Math.round((kb * 100) / total) : 0 }
  }, [all])

  return (
    <div className="space-y-3">
      <Card title={`识别历史(${all.length})`} icon="history"
            right={<Btn danger onClick={async () => { await call('history_clear'); app.setHistory([]); toast('已清空') }}>清空全部</Btn>}>
        {/* 关键数据用统计卡片突出(问题4) */}
        <div className="grid grid-cols-3 gap-2 mb-3">
          <div className="inset px-3 py-2">
            <div className="hint">总记录</div>
            <div className="text-[20px] font-bold leading-tight tabular-nums">{stats.total}</div>
          </div>
          <div className="inset px-3 py-2">
            <div className="hint">知识库命中</div>
            <div className="text-[20px] font-bold leading-tight tabular-nums" style={{ color: 'var(--c-ok)' }}>
              {stats.kbRate}<span className="text-[12px] font-normal text-muted">%</span>
            </div>
          </div>
          <div className="inset px-3 py-2">
            <div className="hint">平均耗时</div>
            <div className="text-[20px] font-bold leading-tight tabular-nums">
              {stats.avg ? stats.avg.toFixed(1) : '—'}<span className="text-[12px] font-normal text-muted">s</span>
            </div>
          </div>
        </div>

        <div className="flex items-center gap-2 mb-3">
          <Segmented size="sm" value={filter} options={HISTORY_FILTERS} onChange={setFilter} />
          <span className="flex-1" />
          <span className="hint">共 {list.length} 条</span>
        </div>

        {list.length === 0 && <div className="hint py-3 text-center">暂无记录</div>}
        {/* 时间线:左侧竖轴 + 节点,右侧内容卡片 */}
        <div className="history-timeline">
          {shown.map((h, i) => {
            const tone = sourceTone(h.source)
            const isTr = h.task === 'translate' || String(h.source || '').includes('翻译')
            const open = !!expanded[i]
            const total = (Number(h.ocr_time) || 0) + (Number(h.answer_time) || 0)
            return (
              <div key={i} className="history-item anim-stagger" style={{ '--i': i }}>
                <span className="history-dot" style={{ background: tone.color }} />
                <div className="history-card">
                  <div className="flex items-center gap-2 flex-wrap">
                    <span className="history-time" title={h.time}>{relTime(h.time)}</span>
                    <span className="stat-chip" style={{ color: tone.color, borderColor: tone.color }}>{tone.label}</span>
                    {isTr && <span className="stat-chip">翻译</span>}
                    <span className="flex-1" />
                    {total > 0 && <span className="stat-chip">耗时 <b>{total.toFixed(1)}s</b></span>}
                    <button
                      type="button" className="icon-btn !w-6 !h-6"
                      title={open ? '收起' : '展开全文'}
                      onClick={() => setExpanded((m) => ({ ...m, [i]: !open }))}
                    >
                      <Icon name="chevronDown" size={13}
                            className="transition-transform"
                            style={{ transform: open ? 'rotate(180deg)' : 'none' }} />
                    </button>
                  </div>
                  <div className={`history-src text-[12px] text-muted ${open ? '' : 'clamp-2'}`}>{h.ocr_text}</div>
                  <div className={`history-answer text-[13px] ${open ? '' : 'clamp-3'}`}>{h.answer}</div>
                  <div className="flex items-center gap-2 mt-1.5">
                    <span className="hint">{h.time}</span>
                    <span className="flex-1" />
                    <Btn className="!h-6 !text-[11.5px]" icon="copy" onClick={async () => {
                      const ok = await call('copy_text', h.answer || '')
                      toast(ok ? '已复制' : '复制失败', ok ? 'ok' : 'danger')
                    }}>复制回答</Btn>
                  </div>
                </div>
              </div>
            )
          })}
        </div>
        {list.length > limit && (
          <div className="flex justify-center pt-2">
            <Btn className="!h-7 !text-[12px]" onClick={() => setLimit((n) => n + 30)}>
              加载更多(还有 {list.length - limit} 条)
            </Btn>
          </div>
        )}
      </Card>
    </div>
  )
}

/* ======================= 新手教程 ======================= */
const GUIDE_MODES = [
  { key: 'overlay', label: '悬浮窗', desc: '洞口对准内容 → 填要求 → 识别;四种形态的切换与结果区说明' },
  { key: 'mini', label: '迷你条', desc: '贴边小条:拖动、输入要求、一键框选识别、切回悬浮窗' },
  { key: 'translate', label: '翻译模式', desc: '语言方向、框选并翻译、复用上次区域、双语/仅译文' },
  { key: 'snip', label: '自由框选', desc: '全屏拖拽框选,以及松开后能做的三件事' },
  { key: 'settings', label: '设置窗口', desc: '分类导航、保存方式与本教程入口' },
]

function GuidePage({ onGoPage }) {
  const app = useApp()
  const toast = useToast()
  const done = app.cfg?.ui?.guideDone || {}
  const play = async (mode) => {
    await call('guide_start', mode)
    if (mode === 'settings') return                      // 设置页教程就地播放
    toast(`已切到「${GUIDE_MODES.find((m) => m.key === mode)?.label}」并开始引导`)
    if (mode === 'snip' || mode === 'overlay' || mode === 'mini' || mode === 'translate') {
      call('close_settings')
    }
  }
  return (
    <div className="space-y-3" data-guide="set-guide">
      <Card title="新手教程" icon="wand"
            desc="用气泡与箭头一步步介绍各个模式的界面与操作;教程期间悬浮窗会自动暂停洞口穿透,结束后恢复">
        <div className="space-y-2">
          {GUIDE_MODES.map((m) => (
            <div key={m.key} className="inset px-3 py-2 flex items-center gap-3">
              <div className="min-w-0 flex-1">
                <div className="flex items-center gap-2">
                  <span className="font-medium">{m.label}</span>
                  {done[m.key]
                    ? <span className="chip">已看过</span>
                    : <span className="chip">未看过</span>}
                </div>
                <div className="hint mt-0.5">{m.desc}</div>
              </div>
              <Btn icon="wand" onClick={() => play(m.key)}>重新观看</Btn>
            </div>
          ))}
          <div className="flex items-center gap-2 pt-1">
            <Btn onClick={async () => { await call('guide_reset'); toast('已重置:下次进入各模式会重新引导'); app.reload() }}>
              重置全部教程
            </Btn>
            <span className="hint">重置后,首次进入每个模式都会自动弹出引导</span>
          </div>
        </div>
      </Card>
      <Card title="快捷键" icon="sliders">
        <div className="space-y-1.5">
          {[
            ['Ctrl+F1', '在悬浮窗模式识别洞口内容'],
            ['Ctrl+Shift+A', '进入自由框选(全屏遮罩)'],
            ['Ctrl+1 / 2 / 3', '切换 悬浮窗 / 迷你条 / 框选'],
            ['Enter / Esc', '框选后确认识别 / 取消框选'],
            ['Ctrl+Q', '退出程序'],
          ].map(([k, v]) => (
            <div key={k} className="flex items-center gap-3">
              <span className="chip font-mono">{k}</span>
              <span className="hint">{v}</span>
            </div>
          ))}
        </div>
        <div className="hint mt-2">快捷键可在「常规设置」中修改。</div>
      </Card>
      <Card title="三步上手" icon="check">
        <div className="space-y-1.5 text-[12.5px] leading-relaxed">
          <div>1. 在「模型设置」里选平台并填写 API Key 与模型 ID(设置 → 模型设置)。</div>
          <div>2. 回到悬浮窗,把洞口对准要识别的内容,填一句提问后点「识别」。</div>
          <div>3. 想离线用:把「云端/本地」开关切到本地,按提示下载端侧模型即可。</div>
        </div>
      </Card>
    </div>
  )
}

/* ======================= 关于应用 ======================= */
function AboutPage() {
  const app = useApp()
  const [days, setDays] = useState({})
  const [stats, setStats] = useState(null)
  const about = app.cfg.app || {}
  const loadLog = () => {
    call('request_log_days').then(setDays)
    call('request_log_stats').then(setStats)
  }
  useEffect(() => { loadLog() }, [])

  const weeks = 20
  const cells = []
  const today = new Date()
  for (let i = weeks * 7 - 1; i >= 0; i--) {
    const d = new Date(today.getTime() - i * 86400000)
    const key = d.toISOString().slice(0, 10)
    cells.push(days[key] || 0)
  }
  const levelColors = ['#9aa3b0', '#9be9a8', '#40c463', '#30a14e', '#216e39']
  const total = stats?.total ?? 0
  const failed = stats?.failed ?? 0

  return (
    <div className="space-y-3">
      <Card>
        <div className="flex items-center gap-4">
          <Logo size={52} radius={14} />
          <div className="flex-1">
            <div className="text-[19px] font-bold">OCR 助手</div>
            <div className="hint">版本 v{app.version} · {about.features}</div>
          </div>
          <Btn primary onClick={() => call('open_url', about.github)}>获取新版本</Btn>
        </div>
      </Card>

      <Card title="请求记录(最近 20 周)" icon="grid"
            right={<Btn onClick={loadLog}>刷新</Btn>}>
        {/* 整组居中:左绿块图(略放大)+ 右统计卡片,两者靠近 */}
        <div className="flex items-center justify-center gap-5">
          <div className="shrink-0">
            <div className="grid grid-flow-col grid-rows-7 justify-start auto-cols-max gap-[3px]">
              {cells.map((c, i) => (
                <span key={i} className="w-[13px] h-[13px] rounded-[2px]"
                      style={{ background: levelColors[Math.min(4, c)] }}
                      title={`${c} 次请求`} />
              ))}
            </div>
            <div className="hint mt-2 flex items-center justify-center gap-1.5">
              <span>少</span>
              {levelColors.map((c) => (
                <span key={c} className="w-[10px] h-[10px] rounded-[2px] inline-block"
                      style={{ background: c }} />
              ))}
              <span>多</span>
            </div>
          </div>

          {/* 右:请求次数 / 失败数(紧贴绿块图,不再推到卡片最右) */}
          <div className="w-[152px] shrink-0 space-y-2">
            <div className="inset px-3 py-2">
              <div className="hint">请求次数</div>
              <div className="text-[21px] font-bold leading-tight">{total}</div>
            </div>
            <div className="inset px-3 py-2">
              <div className="hint">请求失败数</div>
              <div className="text-[21px] font-bold leading-tight"
                   style={{ color: failed > 0 ? 'var(--c-danger)' : 'var(--c-ok)' }}>
                {failed}
              </div>
              {stats && stats.total > 0 && (
                <div className="hint mt-0.5">
                  成功率 {stats.success_rate}%{stats.avg_ms ? ` · 平均 ${(stats.avg_ms / 1000).toFixed(1)}s` : ''}
                </div>
              )}
            </div>
            {stats && (
              <div className="hint px-1 leading-snug">
                统计最近 {Math.round((stats.days || 140) / 7)} 周,最多保留 {stats.keep} 条
              </div>
            )}
          </div>
        </div>
      </Card>

      <Card title="网站与社区" icon="link">
        <div className="space-y-2">
          <div className="flex items-center gap-2">
            <span className="w-[110px]">GitHub 仓库</span>
            <span className="text-accent flex-1 truncate">{about.github}</span>
            <Btn onClick={() => call('open_url', about.github)}>打开</Btn>
          </div>
          <div className="flex items-center gap-2">
            <span className="w-[110px]">QQ 交流群</span>
            <span className="flex-1">{about.qq_group || '暂未创建'}</span>
            {about.qq_group && <Btn onClick={async () => { const ok = await call('copy_text', about.qq_group); toast(ok ? '已复制群号' : '复制失败', ok ? 'ok' : 'danger') }}>复制群号</Btn>}
          </div>
        </div>
      </Card>

      <Card title={`开源许可证:${about.license || 'CC BY-NC 4.0'}`} icon="info">
        <p className="hint leading-relaxed">
          {String(about.license || '').toUpperCase().includes('MIT')
            ? 'MIT License — 允许自由使用、修改与分发,需保留版权声明。'
            : 'CC BY-NC 4.0(署名—非商业性使用 4.0 国际):禁止任何商业使用;转载、镜像、二次分发与衍生作品必须标注原作者与项目名、给出原始仓库地址并保留协议全文。个人学习、研究与教学等非商业用途可自由使用与修改。'}
        </p>
        <div className="flex items-center gap-2 mt-2">
          <Btn onClick={() => call('open_url', `${about.github}/blob/master/LICENSE`)}>查看协议全文</Btn>
          <span className="hint">端侧翻译「均衡/全量」档所用 NLLB-200 模型同为 CC BY-NC 4.0</span>
        </div>
      </Card>
    </div>
  )
}
