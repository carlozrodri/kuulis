// Brand tokens for 9:16 video (marketing/brand/visual.md). Values come from web/app/assets/css/tokens.css:
// new names only, never new colors.
export const color = {
  primary: '#0E7C5A',
  primaryDeep: '#0A5C43',
  accent: '#FFC83D',
  night: '#07120E',
  night2: '#0D1D17',
  ink: '#14201B',
  white: '#FFFFFF',
} as const

export const font = {
  poster: "'Archivo Poster', 'Arial Narrow', sans-serif",
  sans: "'Plus Jakarta Sans', system-ui, sans-serif",
} as const

export const FPS = 30

// Seconds the brand close card lasts when a template appends it.
export const CIERRE_S = 1.2

export const formats = {
  vertical: { width: 1080, height: 1920 },
  feed: { width: 1080, height: 1350 },
} as const
export type Formato = keyof typeof formats

// Safe text area on a 1080×1920 frame: the networks draw the account, caption and buttons outside it.
export const safe = {
  top: 150,
  bottom: 420,
  left: 60,
  right: 180,
} as const
