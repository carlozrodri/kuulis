import { describe, expect, it } from '@jest/globals';

import { isLegalKind, parseInline, parseMarkdown } from '@/lib/legal';

describe('legal markdown', () => {
  it('splits bold runs', () => {
    expect(parseInline('El **monto** es fijo')).toEqual([
      { text: 'El ', bold: false },
      { text: 'monto', bold: true },
      { text: ' es fijo', bold: false },
    ]);
  });

  it('parses the blocks the legal texts use', () => {
    const blocks = parseMarkdown(
      [
        '> **Borrador** pendiente',
        '> de revisión.',
        '',
        '## 1. Quiénes somos',
        'Kuulis conecta',
        'personas.',
        '',
        '- Uno',
        '  sigue',
        '- Dos',
        '',
        '1. Primero',
        '2. Segundo',
        '',
        '| Dato | Plazo |',
        '| --- | --- |',
        '| Chat | 180 días |',
      ].join('\n'),
    );
    expect(blocks.map((b) => b.type)).toEqual(['quote', 'heading', 'paragraph', 'list', 'list', 'table']);
    expect(blocks[0]).toEqual({
      type: 'quote',
      spans: [
        { text: 'Borrador', bold: true },
        { text: ' pendiente de revisión.', bold: false },
      ],
    });
    expect(blocks[2]).toEqual({ type: 'paragraph', spans: [{ text: 'Kuulis conecta personas.', bold: false }] });
    expect(blocks[3]).toMatchObject({ ordered: false, items: [[{ text: 'Uno sigue' }], [{ text: 'Dos' }]] });
    expect(blocks[4]).toMatchObject({ ordered: true });
    expect(blocks[5]).toMatchObject({ header: [[{ text: 'Dato' }], [{ text: 'Plazo' }]], rows: [[[{ text: 'Chat' }], [{ text: '180 días' }]]] });
  });

  it('knows the kinds', () => {
    expect(isLegalKind('terms')).toBe(true);
    expect(isLegalKind('cookies')).toBe(false);
  });
});
