import React, { useEffect, useState } from 'react'
import { call } from './bridge'
import { useApp } from './main'
import {
  Btn, EngineSwitch, Icon, IconBtn, IconSeg, LangPair, Pill, QBox, ResizeHandles, Segmented,
  Tip, useDownloader, useToast, useWindowDrag,
} from './ui'

const MODES = [
  { value: 'overlay', label: '悬浮窗', icon: 'overlay' },
  { value: 'translate', label: '翻译', icon: 'translate' },
  { value: 'snip', label: '框选', icon: 'snip' },
  { value: 'mini', label: '迷你条', icon: 'mini' },
]

const DISPLAYS = [
  { value: 'bilingual', label: '双语对照' },
  { value: 'translated', label: '仅译文' },
  { value: 'source', label: '仅原文' },
]

/** 翻译模式:无洞口,结果区放大;支持双语逐行对照与端侧/云端翻译 */
export default function Translate() {
  const app = useApp()
  const { cfg, status, result, busy } = app
  const toast = useToast()
  const dl = useDownloader()
  const drag = useWindowDrag('translate')
  const tr = cfg.translate || {}
  const [langs, setLangs] = useState([])
  const [question, setQuestion] = useState('')
  const [display, setDisplay] = useState(tr.display || 'bilingual')
  const [topmost, setTopmost] = useState(cfg.window?.always_on_top !== false)

  useEffect(() => { call('languages').then((r) => setLangs(r.list || [])) }, [])
  useEffect(() => setDisplay(tr.display || 'bilingual'), [tr.display])

  const setTr = async (patch) => {
    const next = { ...tr, ...patch }
    app.setCfg({ ...cfg, translate: next })
    for (const [k, v] of Object.entries(patch)) {
      await call('set_config_value', `translate.${k}`, v)  // eslint-disable-line no-await-in-loop
    }
  }
  const setOcr = (cloud) => call('set_config_value', 'ocr.mode', cloud ? 'cloud' : 'local')
    .then(() => app.reload())

  // 切到端侧翻译前检查运行时与语言模型,缺失则弹窗请求下载
  const toggleTranslateEngine = async (cloud) => {
    if (cloud) { await setTr({ mode: 'cloud' }); return }
    const st = await call('local_models_status')
    if (!st?.runtime?.ready) {
      dl.ask('runtime', {
        title: '端侧翻译需要下载推理运行时',
        detail: 'CTranslate2 + sentencepiece(只需下载一次)',
        size: '约 62 MB',
        onDone: async () => {
          const st2 = await call('local_models_status')
          if (!st2?.mt?.ready) {
            dl.ask('mt', { size: '约 79 MB', onDone: () => setTr({ mode: 'local' }) })
          } else {
            await setTr({ mode: 'local' })
          }
        },
      })
      return
    }
    if (!st?.mt?.ready) {
      dl.ask('mt', {
        title: '端侧翻译需要下载该语言模型',
        detail: `端侧翻译模型 ${st?.mt?.pair || ''}(CTranslate2 int8 + 分词模型)`,
        size: '约 79 MB',
        note: '离线可用、不消耗 API 额度;换语言对需另下模型',
        onDone: () => setTr({ mode: 'local' }),
      })
      return
    }
    await setTr({ mode: 'local' })
  }

  const pairs = result?.pairs || []
  const cloud = (tr.mode || 'cloud') === 'cloud'
  const ocrCloud = (cfg.ocr?.mode || 'cloud') === 'cloud'
  const tone = { idle: 'ok', working: 'warn', ok: 'ok', danger: 'danger' }[status.tone] || 'muted'

  return (
    <div className="h-full flex flex-col overflow-hidden mode-enter relative">
      <ResizeHandles which="translate" />
      {/* 顶部:图标 + 两个引擎开关 */}
      <header className="panel shrink-0 h-10 px-2 flex items-center gap-2 drag-handle" {...drag}>
        <span className="logo-o w-[22px] h-[22px] text-[11px] no-drag">O</span>
        <IconSeg size="sm" value="translate" options={MODES} onChange={(m) => app.setMode(m)} />
        <span className="flex-1" />
        <EngineSwitch cloud={ocrCloud} onChange={setOcr} label="识别" tips={['云端', '本地']} />
        <EngineSwitch cloud={cloud} onChange={toggleTranslateEngine}
                      label="翻译" tips={['云端', '本地']} />
        <IconBtn icon="pin" tip={topmost ? '取消置顶' : '窗口置顶'} active={topmost}
                 onClick={async () => { const n = !topmost; setTopmost(n); await call('set_topmost', n) }} />
        <IconBtn icon="settings" tip="设置" onClick={() => call('open_settings')} />
        <IconBtn icon="power" tip="退出(Ctrl+Q)" danger onClick={() => app.quit()} />
      </header>

      {/* 操作行:语言方向 + 显示方式 + 捕获 */}
      <div className="shrink-0 px-2.5 py-2 flex items-center gap-2 flex-wrap border-b" style={{ borderColor: 'var(--c-line)' }}>
        <LangPair languages={langs} source={tr.source_lang || '自动检测'} target={tr.target_lang || '中文'}
                  onChange={(s, t) => setTr({ source_lang: s, target_lang: t })} />
        <Segmented size="sm" value={display} options={DISPLAYS} onChange={(v) => setTr({ display: v })} />
        <span className="flex-1" />
        <IconBtn icon="refresh" tip="自动刷新(定时重新捕获并翻译)" active={!!tr.auto_refresh}
                 onClick={async () => { await call('set_auto_refresh', !tr.auto_refresh); app.reload() }} />
        <Btn primary icon="scan" disabled={busy} onClick={() => call('run_translate', question)}>
          {busy ? '处理中' : '捕获并翻译'}
        </Btn>
        <IconBtn icon="snip" tip="框选新区域并翻译" onClick={() => call('snip_translate')} />
        <IconBtn icon="copy" tip="复制译文" onClick={() => {
          navigator.clipboard.writeText(pairs.map((p) => p.dst).join('\n')); toast('已复制译文')
        }} />
        <IconBtn icon="trash" tip="清空结果" onClick={() => app.setResult(null)} />
      </div>

      {/* 附加要求 */}
      <div className="shrink-0 px-2.5 pt-2">
        <QBox value={question} onChange={setQuestion} rows={2} className="no-drag"
              presets={cfg.behavior?.question_presets} history={cfg.behavior?.question_history}
              placeholder="附加要求(可选):例如「保持专业术语」「译文更口语化」「只翻译正文」…" />
      </div>

      {/* 结果区:原文 / 译文 大面板 */}
      <div className="flex-1 min-h-0 px-2.5 py-2 grid grid-cols-2 gap-2.5">
        <section className="card p-0 flex flex-col min-h-0">
          <div className="flex items-center gap-2 px-3 h-9 border-b shrink-0" style={{ borderColor: 'var(--c-line)' }}>
            <Icon name="text" size={14} className="text-muted" />
            <span className="font-semibold text-[12.5px]">识别原文</span>
            <span className="chip">{tr.source_lang || '自动检测'}</span>
            <span className="flex-1" />
            <span className="hint">{(result?.ocr_text || '').length} 字</span>
          </div>
          <pre className="flex-1 min-h-0 overflow-auto whitespace-pre-wrap text-[12.5px] leading-relaxed p-2.5 m-0">
            {result?.ocr_text || '识别原文将显示在这里'}
          </pre>
        </section>

        <section className="card p-0 flex flex-col min-h-0">
          <div className="flex items-center gap-2 px-3 h-9 border-b shrink-0" style={{ borderColor: 'var(--c-line)' }}>
            <Icon name="translate" size={14} className="text-muted" />
            <span className="font-semibold text-[12.5px]">译文</span>
            <span className="chip">{tr.target_lang || '中文'}</span>
            {result?.engine && <span className="chip">{result.engine}</span>}
            <span className="flex-1" />
            {result?.answer_time > 0 && <span className="hint">{result.answer_time.toFixed(1)}s</span>}
          </div>
          <div className="flex-1 min-h-0 overflow-auto p-2.5">
            {result?.error ? (
              <div className="flex items-start gap-2 text-[12.5px]" style={{ color: 'var(--c-danger)' }}>
                <Icon name="alert" size={14} className="mt-0.5" />
                <span>{result.error}</span>
              </div>
            ) : pairs.length ? (
              <div className="translate-pairs">
                {pairs.map((p, i) => (
                  <div className="pair-block" key={i}>
                    {display !== 'translated' && <div className="pair-src">{p.src || '—'}</div>}
                    {display !== 'source' && <div className="pair-dst">{p.dst || '—'}</div>}
                  </div>
                ))}
              </div>
            ) : (
              <div className="hint">
                还没有翻译结果:点击「捕获并翻译」复用上次区域,或点「框选新区域」(Ctrl+Shift+A)选择要翻译的内容。
              </div>
            )}
          </div>
        </section>
      </div>

      {/* 状态行 */}
      <footer className="panel shrink-0 border-t px-2.5 h-9 flex items-center gap-2">
        <Pill tone={tone}>{status.text}</Pill>
        {result && !result.error && (
          <>
            <span className="chip">OCR: {result.ocr_time?.toFixed(1)}s</span>
            <span className="chip">{cloud ? '云端翻译' : '端侧翻译'}</span>
            {tr.auto_refresh && <span className="chip">自动刷新 {(tr.auto_interval_ms || 2500) / 1000}s</span>}
          </>
        )}
        <span className="flex-1" />
        <Tip text="翻译提示词可在「设置 → 翻译设置」中修改">
          <span className="hint">端侧引擎:{tr.engine === 'auto' ? '自动' : tr.engine}</span>
        </Tip>
      </footer>
    </div>
  )
}
