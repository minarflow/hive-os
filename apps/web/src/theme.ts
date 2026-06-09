// Appearance: theme presets + font choices. Themes are applied as a
// `data-theme` attribute on <html> (CSS provides :root[data-theme="..."]
// overrides); the font is applied by overriding the --font-sans variable.
// Both are persisted to localStorage and re-applied at boot (see main.tsx).

export type ThemeKey = 'light' | 'dark' | 'ocean' | 'violet' | 'sunset' | 'forest'
export type FontKey = 'inter' | 'poppins' | 'nunito' | 'merriweather' | 'playfair' | 'robotoslab' | 'jetbrains' | 'oswald' | 'caveat' | 'lobster'

export const THEMES: { key: ThemeKey; label: string; accent: string; surface: string }[] = [
  { key: 'light', label: 'Light', accent: '#0053fd', surface: '#fbfcfe' },
  { key: 'dark', label: 'Dark', accent: '#4f8cff', surface: '#0d1117' },
  { key: 'ocean', label: 'Ocean', accent: '#0e7490', surface: '#f5fbfd' },
  { key: 'violet', label: 'Violet', accent: '#7c3aed', surface: '#fbf9ff' },
  { key: 'sunset', label: 'Sunset', accent: '#ea580c', surface: '#fffaf5' },
  { key: 'forest', label: 'Forest', accent: '#15803d', surface: '#f6fdf8' }
]

// 10 popular Google Fonts, each a distinctly different style. Loaded in index.html.
export const FONTS: { key: FontKey; label: string; stack: string }[] = [
  { key: 'inter', label: 'Inter', stack: 'Inter, ui-sans-serif, system-ui, sans-serif' },
  { key: 'poppins', label: 'Poppins', stack: 'Poppins, ui-sans-serif, system-ui, sans-serif' },
  { key: 'nunito', label: 'Nunito', stack: 'Nunito, ui-sans-serif, system-ui, sans-serif' },
  { key: 'merriweather', label: 'Merriweather', stack: 'Merriweather, Georgia, serif' },
  { key: 'playfair', label: 'Playfair Display', stack: '"Playfair Display", Georgia, serif' },
  { key: 'robotoslab', label: 'Roboto Slab', stack: '"Roboto Slab", Georgia, serif' },
  { key: 'jetbrains', label: 'JetBrains Mono', stack: '"JetBrains Mono", ui-monospace, monospace' },
  { key: 'oswald', label: 'Oswald', stack: 'Oswald, "Arial Narrow", sans-serif' },
  { key: 'caveat', label: 'Caveat', stack: 'Caveat, "Comic Sans MS", cursive' },
  { key: 'lobster', label: 'Lobster', stack: 'Lobster, "Brush Script MT", cursive' }
]

export type FontSizeKey = 'xs' | 'sm' | 'base' | 'lg'
export const FONT_SIZES: { key: FontSizeKey; label: string; px: number }[] = [
  { key: 'xs', label: 'XS', px: 13 },
  { key: 'sm', label: 'Small', px: 14 },
  { key: 'base', label: 'Default', px: 16 },
  { key: 'lg', label: 'Large', px: 18 }
]

const THEME_LS = 'hive.theme'
const FONT_LS = 'hive.font'
const SIZE_LS = 'hive.fontSize'

// Defaults for a fresh install / new browser (no stored preference yet):
// Sunset theme + Inter font + Small size. Users who already picked keep theirs.
export const DEFAULT_THEME: ThemeKey = 'sunset'
export const DEFAULT_FONT: FontKey = 'inter'
export const DEFAULT_FONT_SIZE: FontSizeKey = 'sm'

export function getTheme(): ThemeKey {
  const v = localStorage.getItem(THEME_LS)
  return THEMES.some(t => t.key === v) ? (v as ThemeKey) : DEFAULT_THEME
}

export function getFont(): FontKey {
  const v = localStorage.getItem(FONT_LS)
  return FONTS.some(f => f.key === v) ? (v as FontKey) : DEFAULT_FONT
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

export function getFontSize(): FontSizeKey {
  const v = localStorage.getItem(SIZE_LS)
  return FONT_SIZES.some(s => s.key === v) ? (v as FontSizeKey) : DEFAULT_FONT_SIZE
}

export function applyFontSize(key: FontSizeKey) {
  const size = FONT_SIZES.find(s => s.key === key) || FONT_SIZES[2]
  // The whole UI is rem-based, so scaling the root font-size scales everything.
  document.documentElement.style.fontSize = `${size.px}px`
  localStorage.setItem(SIZE_LS, key)
}

export function initAppearance() {
  applyTheme(getTheme())
  applyFont(getFont())
  applyFontSize(getFontSize())
}
