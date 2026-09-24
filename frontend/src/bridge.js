/**
 * pywebview 桥接层。
 * 若不在 pywebview 环境中(如浏览器调试),自动降级为内存 Mock,便于前端独立开发。
 */
const pending = []
let api = null

function flush() {
  while (pending.length && api) pending.shift()(api)
}

window.addEventListener('pywebviewready', () => {
  api = window.pywebview.api
  flush()
})

/**
 * 后端事件总入口。必须在这里注册:框选页(selector.html)是独立入口,
 * 不会走 main.jsx 的 <App>,否则收不到 status / result / guideStart 等推送。
 */
if (typeof window !== 'undefined' && !window.__ocrEvent) {
  window.__ocrEvent = (ev) => {
    if (!ev) return
    window.dispatchEvent(new CustomEvent('ocr-event', { detail: ev }))
    if (typeof window.__ocrStateHandler === 'function') window.__ocrStateHandler(ev)
  }
}

export function ready(cb) {
  if (api) return cb(api)
  pending.push(cb)
}

/** 调用后端方法(自动等待 pywebview 就绪) */
export function call(method, ...args) {
  return new Promise((resolve, reject) => {
    ready((a) => {
      const fn = a[method]
      if (typeof fn !== 'function') return reject(new Error(`后端方法不存在: ${method}`))
      try {
        Promise.resolve(fn(...args)).then(resolve).catch(reject)
      } catch (e) {
        reject(e)
      }
    })
  })
}

/* ---------------- 浏览器调试用 Mock ---------------- */
if (!window.pywebview && !window.__MOCK__) {
  window.__MOCK__ = true
}

export const isMock = () => !!window.__MOCK__

export function mockApi(impl) {
  window.pywebview = { api: impl }
  api = impl
  flush()
}
