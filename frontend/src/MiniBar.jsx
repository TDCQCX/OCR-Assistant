import React, { useState } from 'react'
import { call } from './bridge'
import { useApp } from './main'
import { EngineSwitch, Icon, IconBtn, IconSeg, QBox, Tip, useWindowDrag } from './ui'

const MODES = [
  { value: 'overlay', label: '悬浮窗', icon: 'overlay' },
  { value: 'translate', label: '翻译', icon: 'translate' },
  { value: 'snip', label: '框选', icon: 'snip' },
  { value: 'mini', label: '迷你条', icon: 'mini' },
]

/** 迷你条模式:图标行(选中项展开文字)+ 提问输入行,可自由拖动 */
export default function MiniBar() {
  const app = useApp()
  const { cfg, status, result, busy } = app
  const drag = useWindowDrag('mini')
  const [question, setQuestion] = useState(cfg.behavior?.default_question || '请回答识别到的内容')
  const tone = { idle: 'var(--c-ok)', working: 'var(--c-warn)', ok: 'var(--c-ok)', danger: 'var(--c-danger)' }[status.tone] || 'var(--c-muted)'
  const preview = result?.error ? `失败:${result.error}` : result?.answer || status.text

  const toggleOcr = async (cloud) => {
    await call('set_config_value', 'ocr.mode', cloud ? 'cloud' : 'local')
    await app.reload()
  }

  return (
    <div
      className="h-full w-full flex flex-col rounded-card border border-line overflow-hidden"
      style={{ background: 'var(--c-panel)', boxShadow: 'var(--c-shadow)' }}
    >
      {/* 第一行:图标工具栏 */}
      <div className="flex items-center gap-2 px-2 h-[38px] drag-handle" {...drag}>
        <span className="logo-o w-[22px] h-[22px] text-[11px] no-drag" title="OCR 助手">O</span>
        <span className="w-1.5 h-1.5 rounded-full shrink-0" style={{ background: tone }} />
        <span className="truncate text-[12px] text-muted flex-1 min-w-0">{preview}</span>
        <IconSeg size="sm" value="mini" options={MODES} onChange={(m) => app.setMode(m)} />
        <EngineSwitch cloud={(cfg.ocr?.mode || 'cloud') === 'cloud'} onChange={toggleOcr} tips={['云端', '本地']} />
        <IconBtn icon="scan" tip={busy ? '处理中…' : '框选识别(Ctrl+Shift+A)'} primary disabled={busy}
                 onClick={() => call('run_mini_capture', question)} />
        <IconBtn icon="snip" tip="框选新区域" onClick={() => app.startSnip()} />
        <IconBtn icon="settings" tip="设置" onClick={() => call('open_settings')} />
        <IconBtn icon="power" tip="退出(Ctrl+Q)" danger onClick={() => app.quit()} />
      </div>

      {/* 第二行:提问预输入 */}
      <div className="flex items-center gap-2 px-2 pb-2 pt-0.5">
        <Tip text="提问/指令(自输入会自动记住)">
          <span className="text-muted"><Icon name="edit" size={14} /></span>
        </Tip>
        <QBox value={question} onChange={setQuestion} rows={1} className="flex-1 no-drag"
              presets={cfg.behavior?.question_presets} history={cfg.behavior?.question_history}
              placeholder="提问/指令:留空则识别;也可填「请翻译识别到的内容」等" />
      </div>
    </div>
  )
}
