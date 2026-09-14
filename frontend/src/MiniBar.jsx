import React from 'react'
import { call } from './bridge'
import { useApp } from './main'
import { Icon, IconBtn, useWindowDrag } from './ui'

/** 迷你条模式:纯图标工具条,不遮挡画面,可自由拖动 */
export default function MiniBar() {
  const app = useApp()
  const { status, result, busy } = app
  const drag = useWindowDrag('mini')
  const tone = { idle: 'var(--c-ok)', working: 'var(--c-warn)', ok: 'var(--c-ok)', danger: 'var(--c-danger)' }[status.tone] || 'var(--c-muted)'
  const preview = result?.error ? `失败:${result.error}` : result?.answer || status.text

  return (
    <div
      className="h-full w-full flex items-center gap-2 pl-2 pr-1.5 rounded-card border border-line overflow-hidden drag-handle"
      style={{ background: 'var(--c-panel)', boxShadow: 'var(--c-shadow)' }}
      {...drag}
    >
      <span className="logo-o w-[22px] h-[22px] text-[11px] no-drag" title="OCR 助手">O</span>
      <span className="w-1.5 h-1.5 rounded-full shrink-0" style={{ background: tone }} title={status.text} />
      <span className="truncate text-[12px] text-muted flex-1 min-w-0" title={preview}>{preview}</span>

      <IconBtn icon="overlay" tip="悬浮窗模式" onClick={() => app.setMode('overlay')} />
      <IconBtn icon="scan" tip={busy ? '处理中…' : '框选识别(Ctrl+Shift+A)'} primary disabled={busy}
               onClick={() => app.startSnip()} />
      <IconBtn icon="settings" tip="设置" onClick={() => call('open_settings')} />
      <IconBtn icon="power" tip="退出(Ctrl+Q)" danger onClick={() => app.quit()} />
    </div>
  )
}
