import React from 'react'
import { call } from './bridge'
import { useApp } from './main'
import { Btn, Segmented } from './ui'

const MODES = [
  { value: 'overlay', label: '悬浮窗' },
  { value: 'snip', label: '自由截图' },
  { value: 'mini', label: '迷你条' },
]

/** 迷你条模式:不遮挡画面,一键框选识别 */
export default function MiniBar() {
  const app = useApp()
  const { status, result, busy } = app
  const tone = { idle: 'var(--c-ok)', working: 'var(--c-warn)', ok: 'var(--c-ok)', danger: 'var(--c-danger)' }[status.tone] || 'var(--c-muted)'
  const preview = result?.error ? `失败:${result.error}` : result?.answer || status.text

  return (
    <div
      className="h-full w-full pywebview-drag-region flex items-center gap-2 px-3 border border-line rounded-card shadow-lg overflow-hidden"
      style={{ background: 'var(--c-panel)' }}
    >
      <span className="font-bold px-2.5 py-1 rounded-card text-accentfg text-[13px]" style={{ background: 'var(--c-accent)' }}>
        OCR 助手
      </span>
      <span className="w-2 h-2 rounded-full shrink-0" style={{ background: tone }} title={status.text} />
      <span className="truncate text-[12px] text-muted flex-1" title={preview}>{preview}</span>
      <Segmented size="sm" value="mini" options={MODES} onChange={(m) => app.setMode(m)} />
      <Btn primary disabled={busy} onClick={() => app.startSnip()}>{busy ? '处理中…' : '框选识别'}</Btn>
      <Btn onClick={() => call('open_settings')}>设置</Btn>
      <Btn onClick={() => app.quit()}>退出</Btn>
    </div>
  )
}
