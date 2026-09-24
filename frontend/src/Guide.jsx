import React, { useCallback, useEffect, useMemo, useState } from 'react'
import { call } from './bridge'
import { Icon } from './ui'

/* ============================================================================
   新手教程:气泡文字 + 箭头指引,逐模式引导
   - 目标元素用 data-guide="名字" 标记,步骤里引用同一个名字
   - 高亮区用「超大 box-shadow」做出挖空效果(不挡鼠标)
   - 气泡与箭头的位置按目标在窗口内的位置自动选择方向,并夹在窗口内部
   ============================================================================ */

export const GUIDE_STEPS = {
  overlay: [
    { target: 'mode', title: '四种形态', text: '这里是模式切换:悬浮窗 / 翻译 / 框选 / 迷你条,随时可以换。', place: 'below' },
    { target: 'hole', title: '洞口 = 识别区域', text: '把洞口对准要识别的内容。洞口内部鼠标可以穿透,不会挡住下面的窗口。', place: 'below' },
    { target: 'qbox', title: '提问 / 指令', text: '填写你要的处理方式,例如「只给答案」「解释推理过程」。留空则按默认指令执行;内容在各模式间同步。', place: 'above' },
    { target: 'run', title: '开始识别', text: '点「识别」抓取洞口内容并交给 AI;快捷键 Ctrl+F1 同样可以。', place: 'above' },
    { target: 'engine', title: '云端 / 本地', text: '云端=调用你配置的大模型(更准);本地=内置 OCR 离线识别(免费、不耗额度)。', place: 'below' },
    { target: 'model', title: '当前模型', text: '显示正在使用的平台与模型,点击进入设置更换;状态点绿色表示 Key 已配置。', place: 'below' },
    { target: 'result', title: '结果区', text: '左边是识别到的原文,右边是 AI 的回答,可用右上角图标复制。', place: 'above' },
  ],
  mini: [
    { target: 'mini-drag', title: '迷你条', text: '这是迷你条:贴在任务栏上方,不占地方。按住空白处可拖动位置。', place: 'below' },
    { target: 'mini-qbox', title: '直接输入要求', text: '在这里输入提问或指令,和悬浮窗共用同一份内容。', place: 'below' },
    { target: 'mini-run', title: '框选识别', text: '点这个按钮进入全屏框选(快捷键 Ctrl+Shift+A);识别结果会显示在这一行的文字里。', place: 'below' },
    { target: 'mini-mode', title: '换回悬浮窗', text: '点这里的模式按钮可以切回悬浮窗;把迷你条左右拉宽到 560 以上也会自动切回。', place: 'below' },
  ],
  translate: [
    { target: 'tr-lang', title: '语言方向', text: '选择「从什么语言」翻译成「什么语言」。这个选择会写进请求,模型会严格按它输出。', place: 'below' },
    { target: 'tr-snip', title: '框选并翻译', text: '点这里进入全屏框选,松开鼠标后自动翻译所选区域。', place: 'below' },
    { target: 'tr-reuse', title: '复用上次区域', text: '已经框选过就点这里:直接重新捕获同一块区域,适合字幕、连续内容。', place: 'below' },
    { target: 'tr-display', title: '展示方式', text: '双语对照=原文与译文都显示;仅译文=只显示结果,适合阅读。', place: 'below' },
    { target: 'tr-qbox', title: '附加要求', text: '可补充要求,例如「保持专业术语」「译文更口语化」;留空则按默认翻译指令。', place: 'below' },
    { target: 'tr-engine', title: '云端 / 本地翻译', text: '云端=大模型翻译(质量更好);本地=端侧模型离线翻译,首次使用会提示下载。', place: 'below' },
  ],
  settings: [
    { target: 'set-nav', title: '设置分类', text: '左侧是分类:模型 / 行为 / 提示词 / 翻译 / 外观 / 主题 / 历史。', place: 'right' },
    { target: 'set-save', title: '保存方式', text: '改动是即时保存的;点「关闭并保存」即可退出设置(设置窗口会同时释放内存)。', place: 'below' },
    { target: 'set-guide', title: '新手教程', text: '想再看一遍引导,可以在这里重新播放任意模式的教程。', place: 'above' },
  ],
  snip: [
    { target: 'snip-hint', title: '自由框选', text: '按住鼠标左键拖拽,框住要识别或翻译的区域;松开鼠标后会出现操作条。', place: 'below' },
    { target: 'snip-actions', title: '框选后做什么', text: '识别 / 翻译此区域 / 设为悬浮窗区域,三个动作任选;Esc 取消。', place: 'above' },
  ],
}

/** 引导控制:由后端在「首次进入该模式」时发 guideStart 事件触发(避免隐藏窗口提前播放) */
export function useGuide(mode) {
  const [open, setOpen] = useState(false)
  const markDone = useCallback(() => {
    call('guide_done', mode)
  }, [mode])

  const stop = useCallback(async () => {
    setOpen(false)
    try { await call('guide_end', mode) } catch (e) { /* 忽略 */ }
    markDone()                       // 看过或跳过都记一次,避免反复打扰;设置页可重置/重播
  }, [mode, markDone])

  useEffect(() => {
    const onEvent = (e) => {
      if (e?.detail?.type === 'guideStart' && (e.detail.mode || '') === mode) setOpen(true)
    }
    window.addEventListener('ocr-event', onEvent)
    return () => window.removeEventListener('ocr-event', onEvent)
  }, [mode])

  return { open, stop }
}

function rectOf(name) {
  const el = document.querySelector(`[data-guide="${name}"]`)
  if (!el) return null
  const r = el.getBoundingClientRect()
  if (r.width < 2 || r.height < 2) return null
  return { el, x: r.left, y: r.top, w: r.width, h: r.height }
}

/** 气泡 + 箭头 + 挖空高亮 */
export default function Guide({ mode, open, onClose }) {
  const steps = useMemo(() => (GUIDE_STEPS[mode] || []), [mode])
  const [idx, setIdx] = useState(0)
  const [box, setBox] = useState(null)
  const [tick, setTick] = useState(0)

  // 只保留目标真实存在的步骤(窗口过小时某些元素会被隐藏)
  const valid = useMemo(() => steps.filter((s) => !!document.querySelector(`[data-guide="${s.target}"]`)),
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [steps, tick, open])

  useEffect(() => { if (open) setIdx(0) }, [open, mode])

  useEffect(() => {
    if (!open) return undefined
    const measure = () => {
      const step = valid[idx]
      const r = step ? rectOf(step.target) : null
      setBox(r)
      setTick((n) => n + 1)
    }
    measure()
    window.addEventListener('resize', measure)
    const t = setInterval(measure, 400)   // 面板高度会随内容变化,定时校正
    return () => { window.removeEventListener('resize', measure); clearInterval(t) }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open, idx, valid.length])

  if (!open || !valid.length) return null
  const step = valid[Math.min(idx, valid.length - 1)]
  const W = window.innerWidth
  const H = window.innerHeight
  const BW = Math.min(300, Math.max(200, W - 24))       // 气泡宽度
  const GAP = 46                                        // 气泡与目标之间的间距(含箭头长度)

  let place = step.place || 'below'
  let bx = 12
  let by = 12
  if (box) {
    const cx = box.x + box.w / 2
    // 纵向空间不够时自动换成相反方向
    if (place === 'below' && box.y + box.h + GAP + 130 > H) place = 'above'
    if (place === 'above' && box.y - GAP - 130 < 0) place = 'below'
    if (place === 'right' && box.x + box.w + GAP + BW > W) place = 'left'
    if (place === 'left' && box.x - GAP - BW < 0) place = 'right'
    if (place === 'below') { by = box.y + box.h + GAP; bx = cx - BW / 2 }
    else if (place === 'above') { by = box.y - GAP - 112; bx = cx - BW / 2 }
    else if (place === 'right') { bx = box.x + box.w + GAP; by = box.y + box.h / 2 - 50 }
    else { bx = box.x - GAP - BW; by = box.y + box.h / 2 - 50 }
  }
  bx = Math.max(10, Math.min(bx, W - BW - 10))
  by = Math.max(10, Math.min(by, H - 128))

  // 箭头指向目标中心
  let arrow = null
  if (box) {
    const cx = box.x + box.w / 2
    const cy = box.y + box.h / 2
    const AR = 9
    if (place === 'below') {
      arrow = { left: Math.max(14, Math.min(cx - bx - AR, BW - 2 * AR - 14)), top: -AR + 1,
                border: `${AR}px solid transparent`, borderBottom: `${AR}px solid var(--c-accent)` }
    } else if (place === 'above') {
      arrow = { left: Math.max(14, Math.min(cx - bx - AR, BW - 2 * AR - 14)), bottom: -AR + 1,
                border: `${AR}px solid transparent`, borderTop: `${AR}px solid var(--c-accent)` }
    } else if (place === 'right') {
      arrow = { top: Math.max(12, Math.min(cy - by - AR, 76)), left: -AR + 1,
                border: `${AR}px solid transparent`, borderRight: `${AR}px solid var(--c-accent)` }
    } else {
      arrow = { top: Math.max(12, Math.min(cy - by - AR, 76)), right: -AR + 1,
                border: `${AR}px solid transparent`, borderLeft: `${AR}px solid var(--c-accent)` }
    }
  }

  const last = idx >= valid.length - 1
  const next = () => (last ? onClose() : setIdx(idx + 1))
  const prev = () => setIdx(Math.max(0, idx - 1))

  return (
    <div className="fixed inset-0 z-[80] pointer-events-none" data-guide-layer={mode}>
      {/* 挖空高亮:超大阴影把其余区域压暗(不拦截鼠标) */}
      {box && (
        <div
          className="absolute transition-all duration-200"
          style={{
            left: box.x - 4, top: box.y - 4, width: box.w + 8, height: box.h + 8,
            borderRadius: 8, border: '2px solid var(--c-accent)',
            boxShadow: '0 0 0 9999px rgba(8, 12, 18, 0.55)',
          }}
        />
      )}
      {/* 气泡 */}
      <div
        className="absolute rounded-card border shadow-xl p-2.5 pointer-events-auto guide-pop"
        style={{ left: bx, top: by, width: BW, background: 'var(--c-panel)', borderColor: 'var(--c-accent)' }}
      >
        {arrow && <span className="absolute w-0 h-0" style={arrow} />}
        <div className="flex items-center gap-2">
          <Icon name="info" size={14} className="text-[color:var(--c-accent)]" />
          <span className="font-semibold text-[13px]">{step.title}</span>
          <span className="flex-1" />
          <span className="hint">{idx + 1}/{valid.length}</span>
        </div>
        <div className="text-[12.5px] leading-relaxed mt-1.5" style={{ color: 'var(--c-fg)' }}>
          {step.text}
        </div>
        <div className="flex items-center gap-2 mt-2.5">
          <button type="button" className="ctl !h-7 !px-2.5 !text-[12px]" onClick={() => onClose()}>跳过</button>
          <span className="flex-1" />
          {idx > 0 && (
            <button type="button" className="ctl !h-7 !px-2.5 !text-[12px]" onClick={prev}>上一步</button>
          )}
          <button type="button" className="ctl ctl-primary !h-7 !px-3 !text-[12px]" onClick={next}>
            {last ? '开始使用' : '下一步'}
          </button>
        </div>
      </div>
    </div>
  )
}
