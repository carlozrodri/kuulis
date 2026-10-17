import { describe, expect, it } from 'vitest'
import en from '../i18n/locales/en.json'
import es from '../i18n/locales/es.json'
import { englishPath } from '../i18n/pages'

type Messages = { [key: string]: string | Messages }

function flatten(messages: Messages, prefix = ''): Record<string, string> {
  return Object.fromEntries(Object.entries(messages).flatMap(([key, value]) =>
    typeof value === 'string' ? [[`${prefix}${key}`, value]] : Object.entries(flatten(value, `${prefix}${key}.`))))
}

describe('translations', () => {
  const spanish = flatten(es)
  const english = flatten(en)

  it('have the same keys in both languages', () => {
    expect(Object.keys(english).sort()).toEqual(Object.keys(spanish).sort())
  })

  it('have no empty text', () => {
    expect(Object.entries({ ...spanish, ...english }).filter(([, value]) => !value.trim()).map(([key]) => key)).toEqual([])
  })
})

describe('englishPath', () => {
  it('maps Spanish paths to their English URL', () => {
    expect(englishPath('/')).toBe('/en')
    expect(englishPath('/motorizados')).toBe('/en/drivers')
    expect(englishPath('/descargar')).toBe('/en/download')
    expect(englishPath('/ayuda')).toBe('/en/help')
    expect(englishPath('/ayuda/como-pagar')).toBe('/en/help/como-pagar')
    expect(englishPath('/contacto')).toBe('/en/contact')
    expect(englishPath('/legal/terms')).toBe('/en/legal/terms')
  })
})
