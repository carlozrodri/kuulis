import { describe, expect, it } from 'vitest'
import type { AppConfig } from '../app/types/api'
import { changedSettings, defaultSettings, settingsFromConfig, settingsToPayload, validateSettings } from '../app/utils/settings'

const keys = (form: ReturnType<typeof defaultSettings>) => validateSettings(form).map(i => i.key)

describe('app links and location intervals (doc 10)', () => {
  it('accepts the defaults', () => {
    expect(keys(defaultSettings())).toEqual([])
  })

  it('checks links and intervals', () => {
    const form = defaultSettings()
    form.app_links = { support_whatsapp: '58-412 abc', support_email: 'nope', emergency_number: '12345678901', terms_url: 'ftp://x', privacy_url: 'https://kuulis.app/privacidad' }
    form.location_intervals = { online_seconds: 1, on_ride_seconds: 61 }
    expect(keys(form)).toEqual(['whatsapp', 'supportEmail', 'emergencyNumber', 'termsUrl', 'onlineSeconds', 'onRideSeconds'])
    form.app_links.support_whatsapp = '+58 412-1234567'
    expect(settingsToPayload(form).app_links.support_whatsapp).toBe('+584121234567')
  })

  it('never sends maintenance or city pauses and only sends what changed', () => {
    const config = { ...settingsToPayload(defaultSettings()), maintenance: { enabled: true }, area_pauses: [] } as unknown as AppConfig
    const original = settingsToPayload(settingsFromConfig(config))
    expect(original).not.toHaveProperty('maintenance')
    expect(original).not.toHaveProperty('area_pauses')
    const form = settingsFromConfig(config)
    form.location_intervals.online_seconds = 15
    expect(changedSettings(settingsToPayload(form), original)).toEqual({ location_intervals: { online_seconds: 15, on_ride_seconds: 4 } })
  })
})

describe('support settings (doc 13)', () => {
  it('fills defaults and validates ranges', () => {
    const form = settingsFromConfig({ ...settingsToPayload(defaultSettings()), support: undefined } as unknown as AppConfig)
    expect(form.support.sla_normal_hours).toBe(24)
    form.support.sla_urgent_minutes = 0
    form.support.response_promise_es = 'x'.repeat(121)
    expect(keys(form)).toEqual(['supportNumber', 'supportPromise'])
  })

  it('trims the promise texts', () => {
    const form = defaultSettings()
    form.support.response_promise_en = '  Soon.  '
    expect(settingsToPayload(form).support.response_promise_en).toBe('Soon.')
  })
})
