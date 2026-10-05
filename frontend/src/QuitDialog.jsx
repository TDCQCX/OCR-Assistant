import React, { useEffect, useState } from 'react'
import { call } from './bridge'
import { useApp } from './main'
import { Btn, Icon, Logo } from './ui'

/**
 * 退出确认弹窗:点右上角电源键 / Ctrl+Q 时弹出。
 * 三个选择:最小化到任务栏(程序继续跑) / 直接关闭 / 再想想。
 * 勾选「记住选择」后写入 behavior.quit_action,下次不再询问(可在设置 → 常规 里改回)。
 */
export default function QuitDialog({ mode }) {
  const app = useApp()
  const [open, setOpen] = useState(false)
  const [remember, setRemember] = useState(false)

  // 只在"当前显示的、放得下弹窗的模式窗口"里渲染。
  // 判定**不看 cfg.mode** —— 配置广播到各窗口有延迟,窗口刚显示或刚切换模式时
  // cfg.mode 还可能是旧值,那样 confirmQuit 会被误判过滤掉,表现为"退出按钮没反应"。
  // 后端在事件里显式带上目标模式(mode 字段),这里按它判断即可。
  useEffect(() => {
    const wanted = (m) => m && m !== 'mini' && m === mode
    const onEvent = (e) => {
      const ev = e?.detail
      if (!ev) return
      if (ev.type === 'confirmQuit') {
        if (wanted(ev.mode || (app.cfg?.mode || 'overlay'))) setOpen(true)
        return
      }
    }
    window.addEventListener('ocr-event', onEvent)

    // 双保险:事件可能在"窗口刚显示、监听还没装好"的瞬间发出,这里主动回拉一次。
    let alive = true
    const pull = () => {
      call('quit_pending').then((target) => {
        if (!alive) return
        if (wanted(target)) setOpen(true)
      }).catch(() => {})
    }
    const t0 = setTimeout(pull, 300)
    const t1 = setTimeout(pull, 1200)
    const t2 = setTimeout(pull, 2400)
    return () => {
      alive = false
      clearTimeout(t0); clearTimeout(t1); clearTimeout(t2)
      window.removeEventListener('ocr-event', onEvent)
    }
  }, [mode])

  const cancel = () => {
    setOpen(false)
    call('clear_quit_pending_for', mode)   // 只清本模式,避免影响其它窗口
  }
  useEffect(() => {
    if (!open) return undefined
    const onKey = (e) => { if (e.key === 'Escape') cancel() }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [open])

  // 弹窗期间:取消洞口穿透(否则被裁掉)+ 迷你条临时加高(100px 高放不下这个弹窗)
  useEffect(() => {
    call('pause_hole', open)
    call('set_modal_room', open)
    return () => { call('pause_hole', false); call('set_modal_room', false) }
  }, [open])

  if (!open) return null

  const choose = async (action) => {
    if (remember) await call('set_quit_action', action)
    setOpen(false)
    call('clear_quit_pending_for', mode)
    if (action === 'tray') await call('minimize_app')
    else if (action === 'exit') await call('quit_app')
  }

  return (
    <div className="modal-mask" style={{ zIndex: 9600 }} onClick={cancel}>
      <div className="modal-card space-y-3" style={{ width: 'min(392px, calc(100vw - 24px))' }}
           onClick={(e) => e.stopPropagation()} data-quit-dialog="1">
        <div className="flex items-center gap-2.5">
          <Logo size={28} />
          <div className="min-w-0">
            <div className="font-semibold text-[14px]">要关闭 OCR 助手吗?</div>
            <div className="hint leading-tight">最小化到托盘后程序仍在后台运行,随时可以唤回</div>
          </div>
        </div>

        <div className="space-y-1.5">
          <button
            type="button"
            className="inset w-full px-3 py-2 flex items-center gap-2.5 text-left transition-colors"
            onClick={() => choose('tray')}
          >
            <Icon name="grid" size={16} className="text-accent" />
            <span className="flex-1">
              <span className="font-medium">最小化到托盘</span>
              <span className="hint block leading-tight">窗口隐藏、程序在后台继续运行;点托盘图标或按 Ctrl+1/2/3 唤回</span>
            </span>
          </button>
          <button
            type="button"
            className="inset w-full px-3 py-2 flex items-center gap-2.5 text-left transition-colors"
            onClick={() => choose('exit')}
          >
            <Icon name="power" size={16} style={{ color: 'var(--c-danger)' }} />
            <span className="flex-1">
              <span className="font-medium" style={{ color: 'var(--c-danger)' }}>直接关闭</span>
              <span className="hint block leading-tight">退出程序(配置与历史已实时保存)</span>
            </span>
          </button>
        </div>

        <label className="flex items-center gap-2 cursor-pointer select-none">
          <input type="checkbox" checked={remember} onChange={(e) => setRemember(e.target.checked)} />
          <span className="hint">记住我的选择,下次不再询问</span>
        </label>

        <div className="flex items-center gap-2">
          <span className="hint flex-1">Esc 或点击空白处 = 取消</span>
          <Btn onClick={cancel}>再想想</Btn>
        </div>
      </div>
    </div>
  )
}
