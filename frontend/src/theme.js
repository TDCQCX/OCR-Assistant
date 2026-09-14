/**
 * 主题系统:预设主题 + 自定义主题。
 * 主题通过 CSS 变量注入,支持实时切换、导出/导入 JSON。
 *
 * 分区色关系(card 最亮 → panel 为窗口面板 → sub 为卡片内嵌区),
 * 保证「面板 / 卡片 / 内嵌控件」三层有明显区分度。
 */
export const PRESETS = {
  light: {
    name: '浅色',
    colors: {
      bg: '#eef1f6', panel: '#e4e9f2', card: '#ffffff', sub: '#f3f6fb', hover: '#e8edf6',
      fg: '#222834', muted: '#6b7484', line: '#dde3ec',
      accent: '#2f6fed', accentFg: '#ffffff', ok: '#2fa84f', warn: '#d98a13', danger: '#e5484d',
    },
  },
  dark: {
    name: '深色',
    colors: {
      bg: '#12151b', panel: '#181c24', card: '#232936', sub: '#1b202a', hover: '#2b3241',
      fg: '#e9edf5', muted: '#8d97a9', line: '#333c4c',
      accent: '#4c8dff', accentFg: '#ffffff', ok: '#3fb950', warn: '#e3a008', danger: '#f85149',
    },
  },
  gray: {
    name: '灰色',
    colors: {
      bg: '#4c525d', panel: '#565d69', card: '#6b7381', sub: '#616875', hover: '#78808f',
      fg: '#f7f8fb', muted: '#d2d7e0', line: '#868f9e',
      accent: '#9dbcff', accentFg: '#161c26', ok: '#7bd88f', warn: '#ffc26b', danger: '#ff8b84',
    },
  },
  eyecare: {
    name: '护眼',
    colors: {
      bg: '#d8f0dc', panel: '#cbe9d1', card: '#f4fbf5', sub: '#e3f4e6', hover: '#d3eed8',
      fg: '#1f3a26', muted: '#4a6b55', line: '#aedcb8',
      accent: '#2f8f4e', accentFg: '#ffffff', ok: '#2f8f4e', warn: '#a9741a', danger: '#c0392b',
    },
  },
  contrast: {
    name: '高对比',
    colors: {
      bg: '#000000', panel: '#0a0a0a', card: '#151515', sub: '#0e0e0e', hover: '#242424',
      fg: '#ffffff', muted: '#c8c8c8', line: '#5f5f5f',
      accent: '#ffd400', accentFg: '#000000', ok: '#00e676', warn: '#ffab00', danger: '#ff5252',
    },
  },
}

/** 自定义主题缺省分区色时,按主色/文字色推导,保证三层对比关系 */
function withDerived(colors) {
  const c = { ...colors }
  const mix = (a, b, pct) => `color-mix(in srgb, ${a} ${pct}%, ${b})`
  if (!c.sub) c.sub = mix(c.fg || '#000', c.card || '#fff', 5)
  if (!c.hover) c.hover = mix(c.fg || '#000', c.card || '#fff', 10)
  if (!c.panel) c.panel = mix(c.fg || '#000', c.card || '#fff', 4)
  return c
}

/** 把主题(预设或自定义)写入 CSS 变量;ui 用于面板不透明度等附加项 */
export function applyTheme(theme, ui) {
  const raw = theme?.colors || PRESETS.light.colors
  const c = withDerived(raw)
  const root = document.documentElement
  const opacity = Number(ui?.panelOpacity ?? 96)
  const map = {
    '--c-bg': c.bg, '--c-card': c.card, '--c-fg': c.fg,
    '--c-muted': c.muted, '--c-line': c.line, '--c-accent': c.accent,
    '--c-accent-fg': c.accentFg || '#ffffff', '--c-ok': c.ok, '--c-warn': c.warn,
    '--c-danger': c.danger, '--c-sub': c.sub, '--c-hover': c.hover,
    '--c-accent-soft': `color-mix(in srgb, ${c.accent} 14%, transparent)`,
    '--c-panel': `color-mix(in srgb, ${c.panel} ${opacity}%, transparent)`,
  }
  Object.entries(map).forEach(([k, v]) => v && root.style.setProperty(k, v))
  if (theme?.radius != null) root.style.setProperty('--radius', `${theme.radius}px`)
  if (theme?.fontSize != null) root.style.setProperty('--font-size', `${theme.fontSize}px`)
}

export function resolveTheme(ui) {
  // ui: { theme: 'light'|'dark'|... | 'custom', customTheme: {...} }
  if (ui?.theme === 'custom' && ui?.customTheme) return ui.customTheme
  return PRESETS[ui?.theme] || PRESETS.light
}

export const COLOR_FIELDS = [
  ['bg', '底色'], ['panel', '面板'], ['card', '卡片'], ['sub', '内嵌区'],
  ['fg', '正文'], ['muted', '次要文字'], ['line', '边框'], ['accent', '主色'],
  ['accentFg', '主色文字'], ['ok', '成功'], ['warn', '警告'], ['danger', '错误'],
]
