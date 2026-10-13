import { describe, expect, it } from 'vitest'
import en from '../i18n/locales/en.json'
import es from '../i18n/locales/es.json'
import type { CampaignRead } from '../app/types/api'
import {
  campaignFormFrom,
  campaignMoment,
  campaignPayload,
  campaignRates,
  defaultCampaignForm,
  segmentFromForm,
  segmentSummary,
  validateCampaign,
} from '../app/utils/campaigns'
import type { Translate } from '../app/utils/control'

function translator(messages: unknown): Translate {
  return (key, params = {}) => {
    const text = key.split('.').reduce<unknown>((node, k) => (node as Record<string, unknown> | undefined)?.[k], messages)
    if (typeof text !== 'string') throw new Error(`missing ${key}`)
    return text.replace(/\{(\w+)\}/g, (_, name: string) => String(params[name]))
  }
}
const tEs = translator(es)
const tEn = translator(en)

const filled = () => ({ ...defaultCampaignForm(), name: 'Promo octubre', title_es: '¡Hola!' })

describe('campaign segment', () => {
  it('sends only the conditions that are on', () => {
    const form = { ...filled(), audience: 'passengers' as const, activeOn: true, active_days: 30, inactive_days: 99, fee_pending: true, locale: 'en' as const }
    expect(segmentFromForm(form)).toEqual({
      audience: 'passengers',
      cities: [],
      active_days: 30,
      inactive_days: null,
      // Passengers never have a fee.
      fee_pending: false,
      new_without_ride_days: null,
      app_version_below: null,
      locale: 'en',
    })
  })

  it('describes the audience in plain language', () => {
    const segment = { audience: 'drivers' as const, cities: ['Caracas', 'Valencia'], fee_pending: true, app_version_below: '1.4.0', inactive_days: 14 }
    expect(segmentSummary(segment, tEs, 'es')).toBe('Motorizados en Caracas o Valencia · sin entrar hace 14 días · con cuota pendiente · app menor a 1.4.0')
    expect(segmentSummary({ audience: 'all', cities: [], fee_pending: false, locale: 'en' }, tEn, 'en')).toBe('Everyone · in English')
  })
})

describe('campaign form', () => {
  it('round-trips a saved campaign and trims the payload', () => {
    const saved = {
      name: 'Vuelve',
      segment: { audience: 'all', cities: ['Caracas'], fee_pending: false, new_without_ride_days: 7 },
      channels: ['email', 'push'],
      title_es: 'Te extrañamos',
      body_es: '',
      title_en: null,
      body_en: null,
      deep_link: '/wallet',
      scheduled_at: null,
    } as unknown as CampaignRead
    const form = campaignFormFrom(saved)
    expect(form.newOn).toBe(true)
    expect(form.when).toBe('now')
    form.body_en = '  ignored without a title  '
    const payload = campaignPayload(form)
    expect(payload.channels).toEqual(['push', 'email'])
    expect(payload).toMatchObject({ title_en: null, body_en: null, deep_link: '/wallet', scheduled_at: null })
    expect(payload.segment.new_without_ride_days).toBe(7)
  })

  it('validates the essentials', () => {
    expect(validateCampaign(filled())).toEqual([])
    const form = { ...filled(), name: 'x', title_es: ' ', channels: [], deep_link: 'wallet', versionOn: true, app_version_below: 'v1' }
    expect(validateCampaign(form)).toEqual(['name', 'version', 'channels', 'titleEs', 'deepLink'])
    expect(validateCampaign({ ...filled(), activeOn: true, active_days: 7, inactiveOn: true, inactive_days: 30 })).toEqual(['activeInactive'])
    expect(validateCampaign({ ...filled(), deep_link: 'https://kuulis.app/promo' })).toEqual([])
  })

  it('only checks a past date when sending', () => {
    const form = { ...filled(), when: 'later' as const, scheduled_at: '2026-10-01T09:00' }
    const now = new Date('2026-10-13T12:00:00')
    expect(validateCampaign(form, { now })).toEqual([])
    expect(validateCampaign(form, { forSend: true, now })).toEqual(['schedulePast'])
    expect(validateCampaign({ ...form, scheduled_at: '' }, { forSend: true, now })).toEqual(['scheduleMissing'])
    expect(campaignPayload(form).scheduled_at).toBe(new Date('2026-10-01T09:00').toISOString())
  })
})

describe('campaign results', () => {
  it('computes rates without dividing by zero', () => {
    expect(campaignRates({ targeted: 200, sent: 150, skipped: 30, opened: 30, pushed: 120, delivered: 108 }))
      .toEqual({ openRate: 0.2, deliveryRate: 0.9, progress: 0.9 })
    expect(campaignRates(null)).toEqual({ openRate: null, deliveryRate: null, progress: null })
  })

  it('picks the date that matters for each status', () => {
    const base = { scheduled_at: '2026-10-10T12:00:00Z', started_at: '2026-10-10T12:01:00Z', finished_at: '2026-10-10T12:30:00Z', created_at: '2026-10-09T08:00:00Z' }
    expect(campaignMoment({ ...base, status: 'sent' })).toEqual({ key: 'sentAt', at: base.finished_at })
    expect(campaignMoment({ ...base, status: 'scheduled' })).toEqual({ key: 'scheduledFor', at: base.scheduled_at })
    expect(campaignMoment({ ...base, status: 'draft', scheduled_at: null })).toEqual({ key: 'createdAt', at: base.created_at })
  })
})
