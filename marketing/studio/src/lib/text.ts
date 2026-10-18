// Pure text helpers shared by the templates and the render script (no React, no Remotion).

/** "$2,40": dollar sign first and decimal comma, as in marketing/brand/tono.md. Whole amounts drop the decimals. */
export function formatUsd(amount: number): string {
  const fixed = Math.round(amount * 100) / 100
  const text = Number.isInteger(fixed) ? String(fixed) : fixed.toFixed(2).replace('.', ',')
  return `$${text}`
}

/**
 * Glues what must not break across lines: "20 %" (Spanish puts a space before %) and "$ 5" typos.
 * Applied to every text a template draws.
 */
export function keepTogether(text: string): string {
  return text
    .replace(/(\d) %/g, '$1\u00a0%')
    .replace(/\$ (\d)/g, '$$$1')
    .replace(/([-−])\$/g, '$1\u2060$$') // word joiner: "-$30" never breaks after the sign
}

/** Splits a headline so its closing period can be painted in the brand yellow. */
export function splitFinalDot(text: string): { body: string; dot: boolean } {
  const trimmed = keepTogether(text).trimEnd()
  if (trimmed.endsWith('.') && !trimmed.endsWith('..')) return { body: trimmed.slice(0, -1), dot: true }
  return { body: trimmed, dot: false }
}

export type Part = { text: string; highlight: boolean }

/** Marks every occurrence of `highlight` (case-sensitive) so it can be drawn in yellow. */
export function splitHighlight(text: string, highlight?: string): Part[] {
  text = keepTogether(text)
  if (!highlight) return [{ text, highlight: false }]
  highlight = keepTogether(highlight)
  const parts: Part[] = []
  let rest = text
  let at = rest.indexOf(highlight)
  while (at !== -1) {
    if (at > 0) parts.push({ text: rest.slice(0, at), highlight: false })
    parts.push({ text: highlight, highlight: true })
    rest = rest.slice(at + highlight.length)
    at = rest.indexOf(highlight)
  }
  if (rest) parts.push({ text: rest, highlight: false })
  return parts
}

export type Cue = { desdeS: number; hastaS: number; texto: string }

/**
 * Turns a voice-over line into subtitle cues of at most `maxWords` words, timed in proportion to their
 * length between `fromS` and `toS`. Used when a script has the voice text but no hand-timed cues.
 */
export function chunkCaptions(text: string, fromS: number, toS: number, maxWords = 4): Cue[] {
  const words = text.split(/\s+/).filter(Boolean)
  if (words.length === 0 || toS <= fromS) return []
  const chunks: string[] = []
  for (let i = 0; i < words.length; i += maxWords) chunks.push(words.slice(i, i + maxWords).join(' '))
  const total = chunks.reduce((sum, c) => sum + c.length, 0)
  const cues: Cue[] = []
  let at = fromS
  chunks.forEach((chunk, i) => {
    const end = i === chunks.length - 1 ? toS : at + ((toS - fromS) * chunk.length) / total
    cues.push({ desdeS: round(at), hastaS: round(end), texto: chunk })
    at = end
  })
  return cues
}

const round = (n: number) => Math.round(n * 1000) / 1000
