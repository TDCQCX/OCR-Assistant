/** Tailwind 配置:颜色全部映射到 CSS 变量,便于全局/自定义主题实时切换 */
export default {
  content: ['./index.html', './selector.html', './src/**/*.{js,jsx}'],
  theme: {
    extend: {
      colors: {
        bg: 'var(--c-bg)',
        card: 'var(--c-card)',
        fg: 'var(--c-fg)',
        muted: 'var(--c-muted)',
        line: 'var(--c-line)',
        accent: 'var(--c-accent)',
        accentfg: 'var(--c-accent-fg)',
        panel: 'var(--c-panel)',
        ok: 'var(--c-ok)',
        warn: 'var(--c-warn)',
        danger: 'var(--c-danger)',
      },
      borderRadius: {
        card: 'var(--radius)',
        ctl: 'calc(var(--radius) * 0.7)',
      },
      fontFamily: {
        sans: ['"Microsoft YaHei UI"', '"Microsoft YaHei"', 'system-ui', 'sans-serif'],
      },
      keyframes: {
        fadein: { '0%': { opacity: 0, transform: 'translateY(4px)' }, '100%': { opacity: 1, transform: 'none' } },
        pop: { '0%': { opacity: 0, transform: 'scale(.96)' }, '100%': { opacity: 1, transform: 'scale(1)' } },
      },
      // 统一缓动(与 index.css 的 --ease-out 一致);只动 transform/opacity,尽量留在合成层
      animation: {
        fadein: 'fadein .18s cubic-bezier(.22,.61,.36,1)',
        pop: 'pop .16s cubic-bezier(.22,.61,.36,1)',
      },
    },
  },
  plugins: [],
}
