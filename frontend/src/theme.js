/**
 * 主题系统:预设主题 + 自定义主题。
 * 主题通过 CSS 变量注入,支持实时切换、导出/导入 JSON。
 */
export const PRESETS = {
  light: {
    name: '浅色',
    colors: {
      bg: '#f2f4f8', card: '#ffffff', panel: 'rgba(255,255,255,0.96)',
      fg: '#252b36', muted: '#6e7686', line: '#e3e7ef',
      accent: '#2f6fed', accentFg: '#ffffff', ok: '#3fb950', warn: '#f5a623', danger: '#f85149',
    },
  },
  dark: {
    name: '深色',
    colors: {
      bg: '#171a21', card: '#1e222d', panel: 'rgba(30,34,45,0.96)',
      fg: '#e8ecf4', muted: '#8b94a7', line: '#2a3140',
      accent: '#4c8dff', accentFg: '#ffffff', ok: '#3fb950', warn: '#f5a623', danger: '#f85149',
    },
  },
  gray: {
    name: '灰色',
    colors: {
      bg: '#5f6672', card: '#686f7d', panel: 'rgba(104,111,125,0.96)',
      fg: '#f7f8fb', muted: '#c6cbd6', line: '#757e8f',
      accent: '#7fa8ff', accentFg: '#ffffff', ok: '#7bd88f', warn: '#ffc26b', danger: '#ff8b84',
    },
  },
  eyecare: {
    name: '护眼',
    colors: {
      bg: '#c7edcc', card: '#e8f7ea', panel: 'rgba(232,247,234,0.96)',
      fg: '#22402a', muted: '#4d6b56', line: '#a9d8b3',
      accent: '#2f8f4e', accentFg: '#ffffff', ok: '#2f8f4e', warn: '#b7791f', danger: '#c0392b',
    },
  },
  contrast: {
    name: '高对比',
    colors: {
      bg: '#000000', card: '#0d0d0d', panel: 'rgba(13,13,13,0.98)',
      fg: '#ffffff', muted: '#c8c8c8', line: '#5a5a5a',
      accent: '#ffd400', accentFg: '#000000', ok: '#00e676', warn: '#ffab00', danger: '#ff5252',
    },
  },
}

/** 把主题(预设或自定义)写入 CSS 变量 */
export function applyTheme(theme) {
  const c = theme?.colors || PRESETS.light.colors
  const root = document.documentElement
  const map = {
    '--c-bg': c.bg, '--c-card': c.card, '--c-panel': c.panel, '--c-fg': c.fg,
    '--c-muted': c.muted, '--c-line': c.line, '--c-accent': c.accent,
    '--c-accent-fg': c.accentFg || '#ffffff', '--c-ok': c.ok, '--c-warn': c.warn,
    '--c-danger': c.danger,
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
  ['bg', '底色'], ['card', '卡片'], ['panel', '面板'], ['fg', '正文'],
  ['muted', '次要文字'], ['line', '边框'], ['accent', '主色'], ['accentFg', '主色文字'],
  ['ok', '成功'], ['warn', '警告'], ['danger', '错误'],
]
