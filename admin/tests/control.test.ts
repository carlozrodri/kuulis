import { describe, expect, it } from 'vitest'
import en from '../i18n/locales/en.json'
import es from '../i18n/locales/es.json'
import type { FlagRules } from '../app/types/api'
import {
  announcementFormFrom,
  announcementPayload,
  announcementStatus,
  audienceSummary,
  defaultAnnouncementForm,
  flagSummary,
  maintenanceFormFrom,
  maintenancePayload,
  normalizeRules,
  pausePayload,
  sameFlagState,
  upsertPause,
  validateAnnouncement,
  validateMaintenance,
  validatePause,
} from '../app/utils/control'
import type { Translate } from '../app/utils/control'

/** Minimal vue-i18n stand-in: looks the key up in a locale file and fills {placeholders}. */
function translator(messages: unknown): Translate {
  return (key, params = {}) => {
    const text = key.split('.').reduce<unknown>((node, k) => (node as Record<string, unknown> | undefined)?.[k], messages)
    if (typeof text !== 'string') throw new Error(`missing ${key}`)
    return text.replace(/\{(\w+)\}/g, (_, name: string) => String(params[name]))
  }
}
const tEs = translator(es)
const tEn = translator(en)
const rules = (over: Partial<FlagRules> = {}): FlagRules => ({ platforms: [], min_build: null, areas: [], roles: [], percent: 100, ...over })

describe('flag summary', () => {
  it('describes who gets it in plain language', () => {
    expect(flagSummary(true, rules({ percent: 20, roles: ['driver'], areas: ['Caracas'], min_build: 7 }), tEs, 'es'))
      .toBe('20 % de los motorizados en Caracas con build ≥ 7')
    expect(flagSummary(true, rules({ percent: 20, roles: ['driver'], areas: ['Caracas'], min_build: 7 }), tEn, 'en'))
      .toBe('20 % of drivers in Caracas with build ≥ 7')
    expect(flagSummary(true, rules(), tEs, 'es')).toBe('todas las personas')
    expect(flagSummary(true, rules({ roles: ['passenger', 'driver'], areas: ['Caracas', 'Valencia'], platforms: ['android', 'ios'] }), tEs, 'es'))
      .toBe('todas las personas en Caracas y Valencia que usan Android o iOS')
  })

  it('says nobody when off or at 0 %', () => {
    expect(flagSummary(false, rules({ percent: 50 }), tEs, 'es')).toBe('nadie (está apagada).')
    expect(flagSummary(true, rules({ percent: 0 }), tEs, 'es')).toBe('nadie (0 %).')
  })

  it('ignores rules that do not narrow anything', () => {
    expect(flagSummary(true, rules({ platforms: ['android', 'ios', 'web'], min_build: 0 }), tEn, 'en')).toBe('everyone')
  })
})

describe('flag rules', () => {
  it('normalizes what is sent', () => {
    expect(normalizeRules({ platforms: ['ios', 'android', 'ios'], min_build: 0, areas: ['B', 'A', 'B'], roles: ['driver', 'passenger'], percent: 140.4 }))
      .toEqual({ platforms: ['android', 'ios'], min_build: null, areas: ['B', 'A'], roles: ['passenger', 'driver'], percent: 100 })
    expect(normalizeRules(rules({ min_build: 12.7, percent: -3 }))).toMatchObject({ min_build: 12, percent: 0 })
  })

  it('compares saved and edited state', () => {
    expect(sameFlagState({ enabled: true, rules: rules({ roles: ['driver', 'passenger'] }) }, { enabled: true, rules: rules({ roles: ['passenger', 'driver'] }) })).toBe(true)
    expect(sameFlagState({ enabled: true, rules: rules() }, { enabled: false, rules: rules() })).toBe(false)
    expect(sameFlagState({ enabled: true, rules: rules({ percent: 50 }) }, { enabled: true, rules: rules() })).toBe(false)
  })
})

describe('announcements', () => {
  const now = new Date('2026-10-12T12:00:00Z')

  it('computes the status from the dates', () => {
    expect(announcementStatus({ starts_at: '2026-10-13T00:00:00Z', ends_at: '2026-10-14T00:00:00Z' }, now)).toBe('scheduled')
    expect(announcementStatus({ starts_at: '2026-10-12T00:00:00Z', ends_at: '2026-10-14T00:00:00Z' }, now)).toBe('active')
    expect(announcementStatus({ starts_at: '2026-10-01T00:00:00Z', ends_at: '2026-10-12T12:00:00Z' }, now)).toBe('ended')
  })

  it('summarizes the audience', () => {
    expect(audienceSummary({ roles: [], areas: [] }, tEs, 'es')).toBe('Todos')
    expect(audienceSummary({ roles: ['driver'], areas: ['Caracas'] }, tEs, 'es')).toBe('Motorizados en Caracas')
    expect(audienceSummary({ roles: ['passenger', 'driver'], areas: ['Caracas', 'Valencia'] }, tEn, 'en')).toBe('Everyone in Caracas and Valencia')
  })

  it('validates the form', () => {
    const form = defaultAnnouncementForm(now)
    expect(validateAnnouncement(form)).toEqual(['titleEs'])
    form.title.es = 'Hola'
    expect(validateAnnouncement(form)).toEqual([])
    form.ends_at = form.starts_at
    expect(validateAnnouncement(form)).toEqual(['order'])
    form.ends_at = ''
    expect(validateAnnouncement(form)).toEqual(['dates'])
    const withCta = { ...defaultAnnouncementForm(now), title: { es: 'Hola', en: '' }, hasCta: true, ctaKind: 'url' as const, ctaUrl: 'http://kuulis.app' }
    expect(validateAnnouncement(withCta)).toEqual(['ctaLabel', 'ctaUrl'])
    withCta.ctaLabel = { es: 'Ver', en: '' }
    withCta.ctaUrl = 'https://kuulis.app/promo'
    expect(validateAnnouncement(withCta)).toEqual([])
  })

  it('round-trips the API shape with exactly one button destination', () => {
    const input = {
      title: { es: ' Lluvia ', en: 'Rain' },
      body: { es: 'Cuidado', en: '' },
      target: { roles: ['driver' as const], areas: ['Caracas'] },
      cta: { label: { es: 'Ver', en: 'See' }, url: null, screen: 'wallet' as const },
      starts_at: '2026-10-12T12:00:00.000Z',
      ends_at: '2026-10-13T12:00:00.000Z',
      dismissible: false,
      style: 'warning' as const,
    }
    const payload = announcementPayload(announcementFormFrom(input))
    expect(payload).toEqual({ ...input, title: { es: 'Lluvia', en: 'Rain' } })
    const form = announcementFormFrom(input)
    form.ctaKind = 'url'
    form.ctaUrl = 'https://kuulis.app'
    expect(announcementPayload(form).cta).toEqual({ label: { es: 'Ver', en: 'See' }, url: 'https://kuulis.app', screen: null })
    form.hasCta = false
    expect(announcementPayload(form).cta).toBeNull()
  })
})

describe('maintenance and pauses', () => {
  it('sends no areas for every city and keeps the catalogue order', () => {
    const form = maintenanceFormFrom({ enabled: false, message: { es: 'Volvemos pronto', en: '' }, eta: null, areas: [] })
    expect(form.scope).toBe('all')
    expect(maintenancePayload(form, true)).toEqual({ enabled: true, message: { es: 'Volvemos pronto', en: '' }, eta: null, areas: [] })
    form.scope = 'areas'
    form.areas = ['Valencia', 'Caracas']
    expect(maintenancePayload(form, true, ['Caracas', 'Valencia']).areas).toEqual(['Caracas', 'Valencia'])
    form.scope = 'all'
    expect(maintenancePayload(form, true).areas).toEqual([])
  })

  it('validates maintenance', () => {
    const form = maintenanceFormFrom(null)
    expect(validateMaintenance(form)).toEqual(['messageEs'])
    form.message.es = 'x'
    form.scope = 'areas'
    expect(validateMaintenance(form)).toEqual(['areas'])
  })

  it('keeps one pause per city', () => {
    const a = { area: 'Caracas', message: { es: 'a', en: '' }, eta: null }
    const b = { area: 'Valencia', message: { es: 'b', en: '' }, eta: null }
    const c = { area: 'Maracay', message: { es: 'c', en: '' }, eta: null }
    expect(upsertPause([a], b)).toEqual([a, b])
    expect(upsertPause([a, b], { ...a, message: { es: 'nuevo', en: '' } }, 'Caracas')).toEqual([{ ...a, message: { es: 'nuevo', en: '' } }, b])
    expect(upsertPause([a, b], c, 'Caracas')).toEqual([c, b])
    expect(validatePause({ area: 'Caracas', message: { es: 'x', en: '' }, eta: '' }, ['Caracas'])).toEqual(['duplicate'])
    expect(validatePause({ area: '', message: { es: '', en: '' }, eta: '' }, [])).toEqual(['area', 'messageEs'])
    expect(pausePayload({ area: 'Caracas', message: { es: ' x ', en: '' }, eta: '' })).toEqual({ area: 'Caracas', message: { es: 'x', en: '' }, eta: null })
  })
})
