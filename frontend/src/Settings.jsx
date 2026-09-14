import React, { useEffect, useState } from 'react'
import { call } from './bridge'
import { useApp } from './main'
import { applyTheme, resolveTheme, PRESETS, COLOR_FIELDS } from './theme'
import { Btn, Card, ColorInput, Field, Icon, IconBtn, Pill, Segmented, Switch, useToast } from './ui'

const NAV = [
  { key: 'model', label: '模型设置', icon: 'chip' },
  { key: 'general', label: '常规设置', icon: 'sliders' },
  { key: 'translate', label: '翻译设置', icon: 'translate' },
  { key: 'appearance', label: '外观主题', icon: 'palette' },
  { key: 'history', label: '识别历史', icon: 'history' },
  { key: 'about', label: '关于应用', icon: 'info' },
]

export default function Settings() {
  const app = useApp()
  const [page, setPage] = useState('model')
  return (
    <div className="h-full flex gap-3 p-3" style={{ background: 'var(--c-bg)' }}>
      {/* 左侧导航 */}
      <aside className="w-[168px] shrink-0 flex flex-col gap-1.5">
        <div className="flex items-center gap-2 px-1.5 pb-2">
          <span className="logo-o w-[26px] h-[26px] text-[12px]">O</span>
          <div className="min-w-0">
            <div className="font-semibold text-[14px] leading-tight">OCR 助手</div>
            <div className="hint leading-tight">v{app.version}</div>
          </div>
        </div>
        {NAV.map((n) => {
          const active = page === n.key
          return (
            <button
              key={n.key}
              onClick={() => setPage(n.key)}
              className={`nav-item ${active ? 'nav-item-active' : ''}`}
            >
              <Icon name={n.icon} size={16} />
              <span>{n.label}</span>
            </button>
          )
        })}
        <span className="flex-1" />
        <Btn primary icon="check" onClick={() => call('close_settings')}>关闭并保存</Btn>
      </aside>

      {/* 右侧内容 */}
      <main className="flex-1 min-w-0 overflow-auto pr-1">
        {page === 'model' && <ModelPage />}
        {page === 'general' && <GeneralPage />}
        {page === 'translate' && <TranslatePage />}
        {page === 'appearance' && <AppearancePage />}
        {page === 'history' && <HistoryPage />}
        {page === 'about' && <AboutPage />}
      </main>
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

  const reload = async (keep) => {
    const r = await call('list_providers')
    setList(r.list || [])
    const n = keep ?? r.index ?? 0
    setIdx(n)
    loadForm(n)
  }
  const loadForm = async (i) => {
    const f = await call('provider_get', i)
    setForm(f.provider)
    setPreview(f.preview)
  }
  useEffect(() => { reload() }, [])

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

  const ready = (p) => !!(p.api_key || '').trim()
  const configured = list.filter(ready)
  const unconfigured = list.filter((p) => !ready(p))

  const Item = ({ p, i }) => (
    <div
      onClick={() => { setIdx(i); loadForm(i) }}
      className="group flex items-center gap-2 px-2 h-[34px] rounded-ctl border cursor-pointer transition-colors"
      style={{
        background: idx === i ? 'var(--c-accent-soft)' : 'var(--c-card)',
        borderColor: idx === i ? 'var(--c-accent)' : 'var(--c-line)',
        opacity: ready(p) ? 1 : 0.62,
      }}
    >
      <span className="w-5 h-5 rounded-md grid place-items-center text-[10px] font-bold shrink-0"
            style={{ background: p.color || '#8b94a7', color: '#fff' }}>
        {p.name?.[0]}
      </span>
      <span className="truncate flex-1 text-[12.5px]">{p.name}</span>
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
    <div className="flex gap-3 h-full">
      {/* 平台管理 */}
      <div className="w-[212px] shrink-0 flex flex-col gap-2">
        <div className="flex items-center gap-2 px-0.5">
          <Icon name="chip" size={15} className="text-accent" />
          <span className="font-semibold">AI 平台管理</span>
        </div>
        <div className="flex-1 overflow-auto space-y-1.5 pr-1">
          {configured.length > 0 && <div className="hint px-1">已配置({configured.length})</div>}
          {configured.map((p) => <Item key={p.id} p={p} i={list.indexOf(p)} />)}
          {unconfigured.length > 0 && <div className="hint px-1 pt-1">未配置({unconfigured.length})</div>}
          {unconfigured.map((p) => <Item key={p.id} p={p} i={list.indexOf(p)} />)}
        </div>
        <Btn icon="plus" onClick={async () => { await call('provider_add'); reload(list.length) }}>自定义平台</Btn>
      </div>

      {/* 表单 */}
      <div className="flex-1 min-w-0 space-y-3 overflow-auto pr-1">
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

        <div className="space-y-2">
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
          <Field label="模型 ID">
            <input className="ctl" value={form.model || ''} placeholder="例如 qwen3.7-flash-2026-07-15 / gpt-4o-mini"
                   onChange={(e) => patch('model', e.target.value)} />
          </Field>
          <Field label="Base URL">
            <input className="ctl" value={form.base_url || ''} onChange={(e) => patch('base_url', e.target.value)} />
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
            <p className="hint">占位符 {'{model}'} / {'{prompt}'} / {'{image_url}'} 会自动替换为 JSON 值(勿加引号);enable_thinking 由平台开关注入。</p>
            <textarea className="ctl h-72 font-mono text-[12px]" value={tpl} onChange={(e) => setTpl(e.target.value)} />
            <div className="flex justify-end gap-2">
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
          <Field label="默认提问">
            <input className="ctl" value={local.behavior?.default_question || ''}
                   onBlur={(e) => set('behavior.default_question', e.target.value)}
                   onChange={(e) => setLocal({ ...local, behavior: { ...local.behavior, default_question: e.target.value } })} />
          </Field>
          {[['capture', '截图并识别'], ['snip', '自由截图'], ['exit', '退出程序']].map(([k, label]) => (
            <Field key={k} label={`${label} 快捷键`}>
              <input className="ctl !w-40" value={local.hotkeys?.[k] || ''}
                     onChange={(e) => setLocal({ ...local, hotkeys: { ...local.hotkeys, [k]: e.target.value } })}
                     onBlur={(e) => set('hotkeys.' + k, e.target.value)} />
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
            desc="按需下载,不随应用分发;下载后可完全离线使用"
            right={<Btn icon="refresh" onClick={() => call('local_models_status').then(setModels)}>刷新</Btn>}>
        <div className="space-y-2">
          {[
            ['ocr', 'OCR 识别模型', 'RapidOCR PP-OCRv4(检测/识别/方向)', '约 16 MB', models?.ocr],
            ['runtime', '推理运行时', 'CTranslate2 + sentencepiece', '约 62 MB', models?.runtime],
            ['mt', '翻译模型', models?.mt?.pair ? `当前语言对 ${models.mt.pair}` : '当前语言对', '约 79 MB', models?.mt],
          ].map(([kind, name, desc, size, st]) => (
            <div key={kind} className="inset px-3 py-2 flex items-center gap-2.5">
              <span className="card-icon"><Icon name={st?.ready ? 'check' : 'download'} size={14} /></span>
              <div className="min-w-0 flex-1">
                <div className="font-medium">{name}</div>
                <div className="hint truncate">{desc}{st?.size_mb ? ` · 已占用 ${st.size_mb}MB` : ''}</div>
              </div>
              <Pill tone={st?.ready ? 'ok' : 'warn'}>{st?.ready ? '已就绪' : '未下载'}</Pill>
              {st?.ready ? (
                <Btn danger onClick={async () => {
                  toast(await call('remove_local_model', kind)); call('local_models_status').then(setModels)
                }}>删除</Btn>
              ) : (
                <Btn primary icon="download" onClick={() => {
                  call('download_local_model', kind); toast('已开始下载(进度见右下角)')
                }}>{size}</Btn>
              )}
            </div>
          ))}
          <div className="flex items-center gap-2 flex-wrap">
            <Pill tone={status?.ollama ? 'ok' : 'muted'}>{status?.ollama ? 'Ollama 可用' : 'Ollama 未检测到'}</Pill>
            <span className="hint">
              端侧模型目录:{models?.root || 'models/'}(可在文件管理器中删除)
            </span>
          </div>
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
  const [draft, setDraft] = useState(ui.customTheme || resolveTheme(ui))

  const setUi = (patch) => {
    app.setUi(patch)
    applyTheme(resolveTheme({ ...ui, ...patch }), { ...ui, ...patch })
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
        </div>
      </Card>
    </div>
  )
}

/* ======================= 识别历史 ======================= */
function HistoryPage() {
  const app = useApp()
  const toast = useToast()
  useEffect(() => { call('history_list').then(app.setHistory) }, [])
  const list = app.history || []
  return (
    <div className="space-y-3">
      <Card title={`识别历史(${list.length})`} icon="history" right={<Btn danger onClick={async () => { await call('history_clear'); app.setHistory([]); toast('已清空') }}>清空全部</Btn>}>
        {list.length === 0 && <div className="hint">暂无记录</div>}
        <div className="space-y-2">
          {list.map((h, i) => (
            <div key={i} className="rounded-ctl border border-line p-2.5">
              <div className="flex items-center gap-2 mb-1.5">
                <span className="chip">{h.qtype_name || '—'}</span>
                <span className="chip">{h.source}</span>
                <span className="hint">{h.time}</span>
                <span className="flex-1" />
                <Btn onClick={() => { navigator.clipboard.writeText(h.answer || ''); toast('已复制') }}>复制</Btn>
              </div>
              <div className="text-[12px] text-muted line-clamp-2">{h.ocr_text}</div>
              <div className="text-[13px] mt-1 whitespace-pre-wrap">{h.answer}</div>
            </div>
          ))}
        </div>
      </Card>
    </div>
  )
}

/* ======================= 关于应用 ======================= */
function AboutPage() {
  const app = useApp()
  const [days, setDays] = useState({})
  const about = app.cfg.app || {}
  useEffect(() => { call('request_log_days').then(setDays) }, [])

  const weeks = 20
  const cells = []
  const today = new Date()
  for (let i = weeks * 7 - 1; i >= 0; i--) {
    const d = new Date(today.getTime() - i * 86400000)
    const key = d.toISOString().slice(0, 10)
    cells.push(days[key] || 0)
  }
  const levelColors = ['#9aa3b0', '#9be9a8', '#40c463', '#30a14e', '#216e39']

  return (
    <div className="space-y-3">
      <Card>
        <div className="flex items-center gap-4">
          <span className="logo-o w-[52px] h-[52px] text-[24px]">O</span>
          <div className="flex-1">
            <div className="text-[19px] font-bold">OCR 助手</div>
            <div className="hint">版本 v{app.version} · {about.features}</div>
          </div>
          <Btn primary onClick={() => call('open_url', about.github)}>获取新版本</Btn>
        </div>
      </Card>

      <Card title="请求记录(最近 20 周)" icon="grid" right={<Btn onClick={() => call('request_log_days').then(setDays)}>刷新</Btn>}>
        <div className="grid grid-flow-col grid-rows-7 gap-[3px]">
          {cells.map((c, i) => (
            <span key={i} className="w-[11px] h-[11px] rounded-[2px]" style={{ background: levelColors[Math.min(4, c)] }} title={`${c} 次请求`} />
          ))}
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
            {about.qq_group && <Btn onClick={() => { navigator.clipboard.writeText(about.qq_group) }}>复制群号</Btn>}
          </div>
        </div>
      </Card>

      <Card title={`开源许可证:${about.license || 'MIT'}`} icon="info">
        <p className="hint">MIT License — 允许自由使用、修改与分发,需保留版权声明。</p>
      </Card>
    </div>
  )
}
