// Appearance: theme presets + font choices. Themes are applied as a
// `data-theme` attribute on <html> (CSS provides :root[data-theme="..."]
// overrides); the font is applied by overriding the --font-sans variable.
// Both are persisted to localStorage and re-applied at boot (see main.tsx).

export type ThemeKey = 'light' | 'dark' | 'ocean' | 'violet' | 'sunset' | 'forest'
export type FontKey = 'inter' | 'system' | 'rounded' | 'serif' | 'mono'

export const THEMES: { key: ThemeKey; label: string; accent: string; surface: string }[] = [
  { key: 'light', label: 'Light', accent: '#0053fd', surface: '#fbfcfe' },
  { key: 'dark', label: 'Dark', accent: '#4f8cff', surface: '#0d1117' },
  { key: 'ocean', label: 'Ocean', accent: '#0e7490', surface: '#f5fbfd' },
  { key: 'violet', label: 'Violet', accent: '#7c3aed', surface: '#fbf9ff' },
  { key: 'sunset', label: 'Sunset', accent: '#ea580c', surface: '#fffaf5' },
  { key: 'forest', label: 'Forest', accent: '#15803d', surface: '#f6fdf8' }
]

export const FONTS: { key: FontKey; label: string; stack: string }[] = [
  { key: 'inter', label: 'Inter', stack: 'Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif' },
  { key: 'system', label: 'System', stack: 'system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif' },
  { key: 'rounded', label: 'Rounded', stack: 'ui-rounded, "SF Pro Rounded", "Hiragino Maru Gothic ProN", Quicksand, system-ui, sans-serif' },
  { key: 'serif', label: 'Serif', stack: 'Georgia, Cambria, "Times New Roman", serif' },
  { key: 'mono', label: 'Mono', stack: 'ui-monospace, SFMono-Regular, Menlo, Consolas, monospace' }
]

const THEME_LS = 'hive.theme'
const FONT_LS = 'hive.font'

export function getTheme(): ThemeKey {
  const v = localStorage.getItem(THEME_LS)
  return THEMES.some(t => t.key === v) ? (v as ThemeKey) : 'light'
}

export function getFont(): FontKey {
  const v = localStorage.getItem(FONT_LS)
  return FONTS.some(f => f.key === v) ? (v as FontKey) : 'inter'
}

export function applyTheme(key: ThemeKey) {
  document.documentElement.setAttribute('data-theme', key)
  localStorage.setItem(THEME_LS, key)
}

export function applyFont(key: FontKey) {
  const font = FONTS.find(f => f.key === key) || FONTS[0]
  document.documentElement.style.setProperty('--font-sans', font.stack)
  localStorage.setItem(FONT_LS, key)
}

export function initAppearance() {
  applyTheme(getTheme())
  applyFont(getFont())
}
