import { describe, expect, it } from 'vitest'
import { chunkCaptions, formatUsd, keepTogether, splitFinalDot, splitHighlight } from '../src/lib/text'

describe('formatUsd', () => {
  it('uses a decimal comma and drops whole decimals', () => {
    expect(formatUsd(2.4)).toBe('$2,40')
    expect(formatUsd(30)).toBe('$30')
    expect(formatUsd(0.1 + 0.2)).toBe('$0,30')
  })
})

describe('keepTogether', () => {
  it('glues the percent sign, fixes "$ 5" and keeps "-$30" whole', () => {
    expect(keepTogether('el 20 % de $ 5')).toBe('el 20 % de $5')
    expect(keepTogether('= -$30')).toBe('= -\u2060$30')
  })
})

describe('splitFinalDot', () => {
  it('separates only a single closing period', () => {
    expect(splitFinalDot('Lo que cobras es tuyo.')).toEqual({ body: 'Lo que cobras es tuyo', dot: true })
    expect(splitFinalDot('¿Cuánto es tuyo?')).toEqual({ body: '¿Cuánto es tuyo?', dot: false })
    expect(splitFinalDot('Y luego...')).toEqual({ body: 'Y luego...', dot: false })
  })
})

describe('splitHighlight', () => {
  it('marks every occurrence', () => {
    expect(splitHighlight('$3 y $3', '$3')).toEqual([
      { text: '$3', highlight: true },
      { text: ' y ', highlight: false },
      { text: '$3', highlight: true },
    ])
  })
  it('matches after gluing the percent sign', () => {
    expect(splitHighlight('quita el 20 %', '20 %').at(-1)).toEqual({ text: '20 %', highlight: true })
  })
  it('returns the text untouched without a highlight', () => {
    expect(splitHighlight('hola')).toEqual([{ text: 'hola', highlight: false }])
  })
})

describe('chunkCaptions', () => {
  it('cuts into cues of at most N words that cover the whole span', () => {
    const cues = chunkCaptions('uno dos tres cuatro cinco seis siete', 1, 5, 3)
    expect(cues.map((c) => c.texto)).toEqual(['uno dos tres', 'cuatro cinco seis', 'siete'])
    expect(cues[0].desdeS).toBe(1)
    expect(cues.at(-1)?.hastaS).toBe(5)
    cues.slice(1).forEach((c, i) => expect(c.desdeS).toBe(cues[i].hastaS))
  })
  it('returns nothing for empty text or an empty span', () => {
    expect(chunkCaptions('', 0, 3)).toEqual([])
    expect(chunkCaptions('hola', 2, 2)).toEqual([])
  })
})
