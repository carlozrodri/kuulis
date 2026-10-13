import { describe, expect, it } from 'vitest'
import type { SafetyAlert } from '../app/types/api'
import { alertDetail, alertPosition, shouldRing, trackLine } from '../app/utils/safety'
import { defaultSettings, settingsToPayload, validateSettings } from '../app/utils/settings'

const alert = (values: Partial<SafetyAlert>) => ({ kind: 'sos', lat: null, lng: null, driver_location: null, details: {}, ...values }) as SafetyAlert

describe('safety center (doc 11)', () => {
  it('rings once per new open alert', () => {
    expect(shouldRing(null, { open: 0, acknowledged: 0, latest_id: null })).toBe(false)
    expect(shouldRing(null, { open: 1, acknowledged: 0, latest_id: 'a' })).toBe(true)
    expect(shouldRing({ open: 1, acknowledged: 0, latest_id: 'a' }, { open: 1, acknowledged: 0, latest_id: 'a' })).toBe(false)
    expect(shouldRing({ open: 1, acknowledged: 0, latest_id: 'a' }, { open: 2, acknowledged: 0, latest_id: 'b' })).toBe(true)
    expect(shouldRing({ open: 1, acknowledged: 0, latest_id: 'a' }, { open: 0, acknowledged: 1, latest_id: null })).toBe(false)
  })

  it('places an alert and reads its details', () => {
    expect(alertPosition(alert({ lat: 10.5, lng: -66.9 }))).toEqual([10.5, -66.9])
    expect(alertPosition(alert({ driver_location: { lat: 10.4, lng: -66.8, heading: null } }))).toEqual([10.4, -66.8])
    expect(alertPosition(alert({}))).toBeNull()
    expect(alertDetail(alert({ kind: 'stop', details: { minutes: 12 } }))).toBe('12 min')
    expect(alertDetail(alert({ kind: 'deviation', details: { distance_m: 840 } }))).toBe('840 m')
    expect(alertDetail(alert({ kind: 'overtime', details: { minutes: 65, estimated_minutes: 30 } }))).toBe('65 / 30 min')
    expect(trackLine([[10.49, -66.88, 1], [10.5, -66.87, 2]])).toEqual([[10.49, -66.88], [10.5, -66.87]])
    expect(trackLine(undefined)).toEqual([])
  })

  it('validates the safety settings', () => {
    const form = defaultSettings()
    expect(validateSettings(form)).toEqual([])
    form.safety.night_start = '25:00'
    form.safety.stop_minutes = 1
    expect(validateSettings(form).map(i => i.key)).toEqual(['nightHours', 'safetyNumber'])
    form.safety.pin_areas = ['Valencia', 'Caracas']
    expect(settingsToPayload(form).safety.pin_areas).toEqual(['Caracas'])
  })
})
