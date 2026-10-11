import { describe, expect, it } from 'vitest'
import en from '../i18n/locales/en.json'
import es from '../i18n/locales/es.json'

function keys(value: unknown, prefix = ''): string[] {
  if (value === null || typeof value !== 'object' || Array.isArray(value)) return [prefix]
  return Object.entries(value).flatMap(([k, v]) => keys(v, prefix ? `${prefix}.${k}` : k))
}

describe('locales', () => {
  it('es and en have the same keys', () => {
    expect(keys(en).sort()).toEqual(keys(es).sort())
  })

  it('has no empty texts', () => {
    const empty = (locale: unknown) => keys(locale).filter((path) => {
      const text = path.split('.').reduce<unknown>((node, k) => (node as Record<string, unknown>)[k], locale)
      return typeof text === 'string' && text.trim() === ''
    })
    expect(empty(es)).toEqual([])
    expect(empty(en)).toEqual([])
  })
})
