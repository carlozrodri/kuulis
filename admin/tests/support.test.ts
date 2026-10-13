import { describe, expect, it } from 'vitest'
import { parseInline, parseMarkdown } from '../app/utils/markdown'
import {
  contentTypeFromKey,
  formatMinutesSpan,
  helpfulRate,
  isAllowedAttachment,
  messageSide,
  normalizeTag,
  normalizeTags,
  slaState,
  slugify,
  thenFromAction,
  ticketContact,
} from '../app/utils/support'

const NOW = Date.parse('2026-10-13T12:00:00Z')

describe('support tickets (doc 13)', () => {
  it('reads the answer deadline', () => {
    const base = { status: 'open' as const, waiting_on: 'staff' as const, overdue: false }
    expect(slaState({ ...base, sla_due_at: '2026-10-13T11:59:00Z' }, NOW)).toBe('overdue')
    expect(slaState({ ...base, sla_due_at: '2026-10-13T12:30:00Z' }, NOW)).toBe('soon')
    expect(slaState({ ...base, sla_due_at: '2026-10-14T12:00:00Z' }, NOW)).toBe('ok')
    expect(slaState({ ...base, overdue: true, sla_due_at: null }, NOW)).toBe('overdue')
    // Waiting on the user or closed: no deadline running.
    expect(slaState({ ...base, waiting_on: 'user', sla_due_at: '2026-10-13T11:00:00Z' }, NOW)).toBeNull()
    expect(slaState({ ...base, status: 'resolved', overdue: true, sla_due_at: null }, NOW)).toBeNull()
    expect(slaState({ status: 'open', sla_due_at: undefined }, NOW)).toBeNull()
  })

  it('formats average times', () => {
    expect(formatMinutesSpan(null)).toBe('—')
    expect(formatMinutesSpan(44.6)).toBe('45 min')
    expect(formatMinutesSpan(60)).toBe('1 h')
    expect(formatMinutesSpan(200)).toBe('3 h 20 min')
    expect(formatMinutesSpan(1440 * 2 + 240)).toBe('2 d 4 h')
    expect(formatMinutesSpan(1440)).toBe('1 d')
  })

  it('computes the useful share', () => {
    expect(helpfulRate(0, 0)).toBeNull()
    expect(helpfulRate(3, 1)).toBe(0.75)
  })

  it('normalizes tags and slugs', () => {
    expect(normalizeTag('  Pago Móvil ')).toBe('pago-movil')
    expect(normalizeTags(['Cobro', 'cobro', ' ', 'App caída'])).toEqual(['cobro', 'app-caida'])
    expect(slugify('¿Cómo pago al motorizado?')).toBe('como-pago-al-motorizado')
  })

  it('maps saved reply actions to the composer choice', () => {
    expect(thenFromAction('resolve')).toBe('resolve')
    expect(thenFromAction('none')).toBe('keep')
    expect(thenFromAction('wait_user')).toBe('wait_user')
    expect(thenFromAction(undefined)).toBe('wait_user')
  })

  it('names web contacts without an account', () => {
    expect(ticketContact({ reporter: null, contact_name: 'Ana', contact_email: 'ana@x.com', source: 'web' })).toEqual({ name: 'Ana', email: 'ana@x.com', web: true })
    expect(ticketContact({ reporter: { id: '1', name: 'Luis', email: 'l@x.com' }, source: 'app' })).toEqual({ name: 'Luis', email: 'l@x.com', web: false })
  })

  it('lays out the conversation and checks attachments', () => {
    expect(messageSide('user')).toBe('left')
    expect(messageSide('staff')).toBe('right')
    expect(messageSide('system')).toBe('center')
    expect(isAllowedAttachment({ type: 'image/png' })).toBe(true)
    expect(isAllowedAttachment({ type: 'application/pdf' })).toBe(false)
    expect(contentTypeFromKey('uploads/u1/abc.PNG')).toBe('image/png')
    expect(contentTypeFromKey('uploads/u1/abc.heic')).toBe('image/heic')
    expect(contentTypeFromKey('uploads/u1/abc')).toBe('image/jpeg')
  })
})

describe('help article Markdown', () => {
  it('reads inline marks and keeps unsafe links as text', () => {
    expect(parseInline('Paga con **Pago Móvil** y [lee más](https://kuulis.app).')).toEqual([
      { text: 'Paga con ' },
      { text: 'Pago Móvil', bold: true },
      { text: ' y ' },
      { text: 'lee más', href: 'https://kuulis.app' },
      { text: '.' },
    ])
    expect(parseInline('[x](javascript:alert(1))')[0]).toEqual({ text: '[x](javascript:alert(1)' })
    expect(parseInline('*ojo*')).toEqual([{ text: 'ojo', italic: true }])
  })

  it('splits headings, paragraphs and lists', () => {
    const blocks = parseMarkdown('# Título\n\nUna línea\nque sigue.\n\n- uno\n- dos\n  continúa\n\n1. a\n2. b')
    expect(blocks.map(b => b.type)).toEqual(['heading', 'paragraph', 'list', 'list'])
    expect(blocks[1]).toEqual({ type: 'paragraph', inlines: [{ text: 'Una línea que sigue.' }] })
    expect(blocks[2]).toMatchObject({ ordered: false, items: [[{ text: 'uno' }], [{ text: 'dos' }, { text: ' ' }, { text: 'continúa' }]] })
    expect(blocks[3]).toMatchObject({ ordered: true })
  })
})
