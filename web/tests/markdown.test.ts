import { describe, expect, it } from 'vitest'
import { parseInline, parseMarkdown } from '../app/utils/markdown'
import { usd } from '../app/utils/format'

describe('legal markdown', () => {
  it('parses bold runs', () => {
    expect(parseInline('a **b** c')).toEqual([
      { text: 'a ', bold: false },
      { text: 'b', bold: true },
      { text: ' c', bold: false },
    ])
  })

  it('parses safe links only', () => {
    expect(parseInline('Ve a [Contacto](/contacto) o [web](https://kuulis.app).')).toEqual([
      { text: 'Ve a ', bold: false },
      { text: 'Contacto', bold: false, href: '/contacto' },
      { text: ' o ', bold: false },
      { text: 'web', bold: false, href: 'https://kuulis.app' },
      { text: '.', bold: false },
    ])
    expect(parseInline('[x](javascript:alert(1))')[0]).not.toHaveProperty('href')
    expect(parseInline('[x](//evil.example)')[0]).toEqual({ text: 'x', bold: false })
  })

  it('parses headings, lists, quotes and tables', () => {
    const blocks = parseMarkdown('> **Borrador**\n\n## 1. Uso\nTexto que\nsigue.\n\n- uno\n- dos\n\n| Dato | Plazo |\n|---|---|\n| Chat | 180 días |')
    expect(blocks.map(b => b.type)).toEqual(['quote', 'heading', 'paragraph', 'list', 'table'])
    expect(blocks[2]).toEqual({ type: 'paragraph', spans: [{ text: 'Texto que sigue.', bold: false }] })
    const table = blocks[4] as Extract<typeof blocks[number], { type: 'table' }>
    expect(table.rows).toHaveLength(1)
  })
})

describe('usd', () => {
  it('drops cents only when whole', () => {
    expect(usd(5)).toBe('$5')
    expect(usd(2.4)).toBe('$2.40')
  })
})
