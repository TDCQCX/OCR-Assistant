import React, { useEffect, useState } from 'react'
import { call } from './bridge'
import { useApp } from './main'
import QuitDialog from './QuitDialog'
import Guide, { useGuide } from './Guide'
import { Btn, EngineSwitch, Icon, IconBtn, IconSeg, LangPair, Logo, Pill, QBox, ResizeHandles, Segmented, Tip, useDownloader, useToast, useWindowDrag } from './ui'

const MODES = [
  { value: 'overlay', label: '悬浮窗', icon: 'overlay' },
  { value: 'translate', label: '翻译', icon: 'translate' },
  { value: 'snip', label: '框选', icon: 'snip' },
  { value: 'mini', label: '迷你条', icon: 'mini' },
]

const DISPLAYS = [
  { value: 'bilingual', label: '双语对照' },
  { value: 'translated', label: '仅译文' },
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
  const { question, setQuestion } = app  // 全局共享:与悬浮窗/迷你条同步
  const [display, setDisplay] = useState(tr.display || 'bilingual')
  const [topmost, setTopmost] = useState(cfg.window?.always_on_top !== false)
  const guide = useGuide('translate')

  useEffect(() => {
    call('languages').then((r) => setLangs(r.list || []))
    // 窗口刚显示时页面可能还没就绪,主动回拉最近一次结果
    call('last_result').then((r) => { if (r && (r.pairs || r.ocr_text)) app.setResult(r) })
  }, [])
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

  /**
   * 切到端侧翻译。
   *
   * 修复要点:
   *  1) 就绪判断改用 st.mt_tier_ready(当前档位是否就绪),不再依赖 mt.ready ——
   *     后者是按「语言对」判断的,来源语言选「自动检测」时永远为 false,
   *     于是选完模型再点依然弹窗、且切不过去;
   *  2) 已经就绪时直接切换,不再弹窗;
   *  3) 若确实缺模型,弹窗里选好档位后由「用这个档位」按钮完成切换(见 DownloadHost)。
   */
  const toggleTranslateEngine = async (cloud) => {
    if (cloud) { await setTr({ mode: 'cloud' }); return }

    const goLocal = () => setTr({ mode: 'local' })
    const probe = async () => {
      const st = await call('local_models_status')
      return {
        tierReady: !!st?.mt_tier_ready,      // 当前档位就绪(与语言对无关)
        runtimeReady: !!st?.runtime?.ready,  // 轻量档需要 CTranslate2 运行时
        hfRuntimeReady: !!st?.hf_runtime?.ready,
        tier: st?.mt_tier || '',
        pairReady: !!st?.mt?.ready,
      }
    }

    const st = await probe()
    if (st.tierReady && (st.runtimeReady || st.hfRuntimeReady)) { await goLocal(); return }

    dl.ask('mt', {
      title: '端侧翻译需要先准备模型',
      detail: st.tierReady
        ? '模型已就绪,但缺少推理运行时'
        : `当前档位${st.tier ? `(${st.tier})` : ''}还没有可用模型`,
      note: '选好档位后点右下角「用这个档位」即可切到端侧;离线可用、不消耗 API 额度',
      onDone: goLocal,
    })
  }

  const pairs = result?.pairs || []
  const cloud = (tr.mode || 'cloud') === 'cloud'
  const ocrCloud = (cfg.ocr?.mode || 'cloud') === 'cloud'
  const tone = { idle: 'ok', working: 'warn', ok: 'ok', danger: 'danger' }[status.tone] || 'muted'

  return (
    <div className="window-shell h-full flex flex-col overflow-hidden mode-enter relative"
         style={{ background: 'var(--c-bg)' }}>
      <ResizeHandles which="translate" />
      {/* 顶部:图标 + 两个引擎开关 */}
      <header className="panel shrink-0 drag-handle" {...drag}>
        {/* 第 1 行:品牌 + 模式切换 + 窗口动作 */}
        <div className="h-10 px-2.5 flex items-center gap-2">
          <span className="toolbar-group" title="OCR 助手"><Logo size={22} /></span>
          <span className="no-drag toolbar-group shrink-0">
            <IconSeg size="sm" value="translate" options={MODES} onChange={(m) => app.setMode(m)} />
          </span>
          {/* 引擎开关放在「模式切换」与「右侧窗口控件」之间:有富余则居中,不足则向左靠 */}
          <span className="topbar-center flex items-center justify-center gap-3 whitespace-nowrap min-w-0 flex-1">
            <EngineSwitch cloud={ocrCloud} onChange={setOcr} label="识别" tips={['云端', '本地']} />
            <span data-guide="tr-engine" className="flex items-center shrink-0">
              <EngineSwitch cloud={cloud} onChange={toggleTranslateEngine}
                            label="翻译" tips={['云端', '本地']} />
            </span>
          </span>
          <span className="toolbar-group shrink-0">
            <IconBtn icon="info" tip="新手教程" onClick={() => call('guide_start', 'translate')} />
            <IconBtn icon="pin" tip={topmost ? '取消置顶' : '窗口置顶'} active={topmost}
                     onClick={() => app.toggleTopmost()} />
            <IconBtn icon="settings" tip="设置" onClick={() => call('open_settings')} />
            <IconBtn icon="power" tip="退出(Ctrl+Q)" danger onClick={() => app.quit()} />
          </span>
        </div>
      </header>

      {/* 操作行:语言方向 + 显示方式 + 捕获 */}
      <div className="shrink-0 px-2.5 py-2 flex items-center gap-2 flex-wrap border-b" style={{ borderColor: 'var(--c-line)' }}>
        <span data-guide="tr-lang" className="flex items-center">
          <LangPair languages={langs} source={tr.source_lang || '自动检测'} target={tr.target_lang || '中文'}
                    onChange={(s, t) => setTr({ source_lang: s, target_lang: t })} />
        </span>
        <span data-guide="tr-display" className="flex items-center">
          <Segmented size="sm" value={display} options={DISPLAYS} onChange={(v) => setTr({ display: v })} />
        </span>
        <span className="flex-1" />
        {/* 结果操作组 */}
        <span className="toolbar-group">
          <span data-guide="tr-reuse">
            <IconBtn icon="refresh" tip="复用上次框选区域重新翻译" onClick={() => call('run_translate', question)} />
          </span>
          <IconBtn icon="copy" tip="复制译文" onClick={async () => {
            const text = pairs.map((p) => p.dst).filter(Boolean).join('\n')
            const ok = await call('copy_text', text)
            toast(ok ? '已复制译文' : '复制失败', ok ? 'ok' : 'danger')
          }} />
          <IconBtn icon="trash" tip="清空结果" onClick={() => app.setResult(null)} />
        </span>
        <span className="toolbar-sep" />
        <IconBtn icon="refresh" tip="自动刷新(定时重新捕获并翻译)" active={!!tr.auto_refresh}
                 onClick={async () => { await call('set_auto_refresh', !tr.auto_refresh); app.reload() }} />
        <span data-guide="tr-snip">
          <Btn primary icon="snip" disabled={busy} onClick={() => call('snip_translate')}>
            {busy ? '处理中' : '框选并翻译'}
          </Btn>
        </span>
      </div>

      {/* 附加要求(单行,问题13) */}
      <div className="shrink-0 px-2.5 py-2" data-guide="tr-qbox">
        <QBox value={question} onChange={setQuestion} className="no-drag"
              onSubmit={() => call('run_translate', question)}
              placeholder="附加要求(可选,回车重新翻译):例如「保持专业术语」「译文更口语化」" />
      </div>

      {/* 结果区(问题8):左右两栏 —— 左侧原文,右侧译文;窄窗口自动上下堆叠 */}
      <div className="flex-1 min-h-0 px-2.5 py-2">
        {result?.error ? (
          <div className="result-body result-body-error flex items-start gap-2 text-[12.5px]">
            <Icon name="alert" size={14} className="mt-0.5 shrink-0" />
            <span className="break-anywhere">{result.error}</span>
          </div>
        ) : pairs.length || result?.ocr_text ? (
          <div className={`translate-split ${display === 'translated' ? 'one-col' : ''}`}>
            {display !== 'translated' && (
              <section className="translate-col anim-left">
                <div className="result-pane-head">
                  <Icon name="text" size={13} />
                  <span>原文</span>
                  <span className="stat-chip">{tr.source_lang || '自动检测'}</span>
                  <span className="flex-1" />
                  <span className="hint">{(result?.ocr_text || '').length} 字</span>
                </div>
                <div className="translate-col-body doc-src">{result?.ocr_text || '—'}</div>
              </section>
            )}
            <section className="translate-col anim-right">
              <div className="result-pane-head">
                <Icon name="translate" size={13} />
                <span>译文</span>
                <span className="stat-chip">{tr.target_lang || '中文'}</span>
                {result?.engine && <span className="stat-chip">{result.engine}</span>}
                <span className="flex-1" />
                {result?.answer_time > 0 && <span className="hint">{result.answer_time.toFixed(1)}s</span>}
              </div>
              <div className="translate-col-body doc-dst selectable">
                {pairs.length
                  ? pairs.map((p, i) => <p key={i} className="doc-line">{p.dst || '—'}</p>)
                  : (result?.answer || '—')}
              </div>
            </section>
          </div>
        ) : (
          <div className="h-full grid place-items-center">
            <div className="text-center space-y-2 max-w-[360px]">
              <div className="card-icon mx-auto" style={{ width: 34, height: 34 }}><Icon name="translate" size={17} /></div>
              <div className="text-[13px] font-medium">还没有翻译结果</div>
              <div className="hint leading-relaxed">
                点上方「框选并翻译」选择要翻译的内容(Ctrl+Shift+A);
                已经有框选区域时,点「复用上次区域」即可重新翻译。
              </div>
            </div>
          </div>
        )}
      </div>

      {/* 状态行 */}
      <footer className="status-bar" data-guide="status">
        <Pill tone={tone}>{status.text}</Pill>
        <span className="stat-chip">识别 <b>{ocrCloud ? '云端' : '端侧'}</b></span>
        <span className="stat-chip">翻译 <b>{cloud ? '云端' : '端侧'}</b></span>
        <span className="stat-chip">{tr.source_lang || '自动检测'} → {tr.target_lang || '中文'}</span>
        {result && !result.error && (
          <>
            <span className="stat-chip">OCR <b>{result.ocr_time?.toFixed(1) || '0.0'}s</b></span>
            {result.answer_time > 0 && <span className="stat-chip">翻译 <b>{result.answer_time.toFixed(1)}s</b></span>}
            {result.engine && <span className="stat-chip">引擎 <b>{result.engine}</b></span>}
            <span className="stat-chip">原文 <b>{(result?.ocr_text || '').length}</b> 字</span>
          </>
        )}
        {tr.auto_refresh && (
          <span className="stat-chip" style={{ color: 'var(--c-accent)', borderColor: 'var(--c-accent)' }}>
            自动刷新 {(tr.auto_interval_ms || 2500) / 1000}s
          </span>
        )}
        <span className="flex-1" />
        {!result?.error && result?.segments > 0 && <span className="hint">{result.segments} 段</span>}
      </footer>
      <Guide mode="translate" open={guide.open} onClose={guide.stop} />
      <QuitDialog mode="translate" />
    </div>
  )
}
