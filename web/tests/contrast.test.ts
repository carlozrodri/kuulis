import { readFileSync } from 'node:fs'
import { describe, expect, it } from 'vitest'

// Contrast of the final color tokens, light and dark (docs/website-redesign/08 §4): text pairs at least 4.5:1,
// the focus ring and large figures at least 3:1 (WCAG 1.4.3 and 1.4.11). Read from tokens.css, so a color change
// that breaks a pair fails here.
const css = readFileSync(new URL('../app/assets/css/tokens.css', import.meta.url), 'utf8')
const dark = css.slice(css.indexOf('prefers-color-scheme: dark'))

function tokens(block: string, base: Record<string, string> = {}) {
  const values = { ...base }
  for (const [, name, value] of block.matchAll(/--([\w-]+):\s*([^;]+);/g)) values[name!] = value!.trim()
  return values
}
const LIGHT = tokens(css.slice(0, css.indexOf('prefers-color-scheme: dark')))
const DARK = tokens(dark, LIGHT)

type Rgba = [number, number, number, number]
function color(values: Record<string, string>, name: string): Rgba {
  let value = values[name]!
  while (value.startsWith('var(')) value = values[value.slice(6, -1)]!
  const hex = value.match(/^#([\da-f]{3}|[\da-f]{6})$/i)?.[1]
  if (hex) {
    const full = hex.length === 3 ? [...hex].map(c => c + c).join('') : hex
    return [0, 2, 4].map(i => parseInt(full.slice(i, i + 2), 16)).concat(1) as Rgba
  }
  const rgb = value.match(/^rgb\((\d+) (\d+) (\d+) \/ (\d+)%\)$/)
  if (rgb) return [Number(rgb[1]), Number(rgb[2]), Number(rgb[3]), Number(rgb[4]) / 100]
  throw new Error(`${name}: ${value}`)
}

const luminance = ([r, g, b]: Rgba) => {
  const [lr, lg, lb] = [r, g, b].map((c) => {
    const s = c / 255
    return s <= 0.03928 ? s / 12.92 : ((s + 0.055) / 1.055) ** 2.4
  })
  return 0.2126 * lr! + 0.7152 * lg! + 0.0722 * lb!
}

/** Contrast of a foreground (possibly translucent) over an opaque background. */
function ratio(values: Record<string, string>, fg: string, bg: string) {
  const back = color(values, bg)
  const front = color(values, fg)
  const a = front[3]
  const blended = [0, 1, 2].map(i => front[i]! * a + back[i]! * (1 - a)).concat(1) as Rgba
  const [hi, lo] = [luminance(blended), luminance(back)].sort((x, y) => y - x)
  return (hi! + 0.05) / (lo! + 0.05)
}

const TEXT: [string, string][] = [
  ['text', 'bg'], ['text', 'surface'], ['text', 'surface-alt'],
  ['muted', 'bg'], ['muted', 'surface'], ['muted', 'surface-alt'],
  ['primary', 'bg'], ['primary', 'surface'],
  ['on-primary', 'primary'], ['on-accent', 'accent'], ['on-accent', 'accent-pressed'],
  ['on-band', 'band-brand'], ['on-band', 'band-ink'], ['on-band-soft', 'band-brand'], ['on-band-soft', 'band-ink'],
  ['accent', 'band-ink'],
  ['danger', 'danger-soft'], ['success', 'success-soft'], ['danger', 'surface'],
]
const NON_TEXT: [string, string][] = [
  ['focus-outer', 'bg'], ['focus-inner', 'band-brand'], ['focus-inner', 'band-ink'], ['accent', 'band-brand'],
]

describe.each([['light', LIGHT], ['dark', DARK]] as const)('%s', (_, values) => {
  it.each(TEXT)('%s on %s is at least 4.5:1', (fg, bg) => {
    expect(ratio(values, fg, bg)).toBeGreaterThanOrEqual(4.5)
  })
  it.each(NON_TEXT)('%s on %s is at least 3:1', (fg, bg) => {
    expect(ratio(values, fg, bg)).toBeGreaterThanOrEqual(3)
  })
})
