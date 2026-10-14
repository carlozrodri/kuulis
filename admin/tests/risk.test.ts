import { describe, expect, it } from 'vitest'
import type { AppConfig, RiskSummary, SignalRead } from '../app/types/api'
import { holdStatusColor, isHoldOpen, riskBadgeTotal, riskEvidenceLines, riskOpenCount, riskReasonKey, riskScoreColor, riskUserLink, signalsQuery, signalStatusColor } from '../app/utils/risk'
import { changedSettings, defaultSettings, settingsFromConfig, settingsToPayload, validateSettings } from '../app/utils/settings'

const keys = (form: ReturnType<typeof defaultSettings>) => validateSettings(form).map(i => i.key)
const signal = (kind: SignalRead['kind'], reasons: string[], evidence: Record<string, unknown>) => ({ kind, reasons, evidence })
const lines = (s: ReturnType<typeof signal>) => riskEvidenceLines(s, 'es').map(l => [l.key.replace('risk.evidence.', ''), l.params])

describe('anti-fraud (doc 16)', () => {
  it('colours scores and statuses', () => {
    expect(riskScoreColor(0)).toBe('success')
    expect(riskScoreColor(10)).toBe('neutral')
    expect(riskScoreColor(30)).toBe('warning')
    expect(riskScoreColor(60)).toBe('error')
    expect(riskScoreColor(45, 40)).toBe('error')
    expect(signalStatusColor('open')).toBe('warning')
    expect(signalStatusColor('something_new')).toBe('neutral')
    expect(holdStatusColor('released')).toBe('success')
    expect(isHoldOpen({ status: 'held' })).toBe(true)
    expect(isHoldOpen({ status: 'voided' })).toBe(false)
    expect(riskReasonKey('chain')).toBe('risk.reasons.chain')
  })

  it('links drivers to their profile and the rest to the user page', () => {
    expect(riskUserLink({ id: 'u1', driver_profile_id: 'd1' })).toBe('/drivers/d1')
    expect(riskUserLink({ id: 'u1', driver_profile_id: null })).toBe('/users/u1')
  })

  it('counts open alerts and held payments for the badge', () => {
    const summary: RiskSummary = { open: [{ kind: 'fake_gps', open: 2 }, { kind: 'transfers', open: 3 }, { kind: 'rating_ring', open: 0 }], holds: 4, held_amount: '12.50' }
    expect(riskOpenCount(summary)).toBe(5)
    expect(riskOpenCount(summary, 'transfers')).toBe(3)
    expect(riskOpenCount(summary, 'shared_device')).toBe(0)
    expect(riskBadgeTotal(summary)).toBe(9)
    expect(riskBadgeTotal(null)).toBe(0)
  })

  it('asks for every status with an empty status', () => {
    expect(signalsQuery({ kind: 'all', status: 'all', limit: 25, offset: 0 })).toEqual({ status: '', limit: 25, offset: 0 })
    expect(signalsQuery({ kind: 'fake_gps', status: 'open', limit: 25, offset: 25, userId: 'u1' })).toEqual({ status: 'open', limit: 25, offset: 25, kind: 'fake_gps', user_id: 'u1' })
  })

  it('puts ride evidence in plain words', () => {
    const ride = signal('suspicious_ride', ['little_movement', 'too_short', 'frequent_pair'], {
      distance_m: 3400, path_m: 120, estimate_s: 720, real_s: 50, points: 6, pair_rides: 5, promotion: true,
    })
    expect(lines(ride)).toEqual([
      ['path', { real: '120 m', estimated: '3,4 km' }],
      ['duration', { real: '1 min', estimated: '12 min' }],
      ['pair', { n: 5 }],
      ['promotion', {}],
    ])
    const pair = signal('frequent_pair', ['frequent_pair'], { distance_m: 2000, path_m: 1900, estimate_s: 600, real_s: 580, points: 20, pair_rides: 5, days: 30, promotion: false })
    expect(lines(pair).map(l => l[0])).toEqual(['path', 'duration', 'pairDays'])
    expect(lines(pair)[2]![1]).toEqual({ n: 5, days: 30 })
    const noTrack = signal('suspicious_ride', ['same_device', 'no_track'], { distance_m: 3000, path_m: 0, estimate_s: 600, real_s: 0, points: 0, pair_rides: 1 })
    expect(lines(noTrack).map(l => l[0])).toEqual(['sameDevice', 'noTrack'])
  })

  it('puts the other kinds in plain words', () => {
    expect(lines(signal('shared_device', ['shared_device'], { accounts: ['a', 'b', 'c'], count: 3, platform: 'android', model: 'Redmi 9' })))
      .toEqual([['sharedDevice', { n: 3 }], ['phone', { phone: 'Redmi 9 · android' }]])
    expect(lines(signal('fake_gps', ['mocked'], { lat: 10.48061, lng: -66.90361, ride: true })))
      .toEqual([['mockedOnRide', { lat: '10.48061', lng: '-66.90361' }]])
    expect(lines(signal('fake_gps', ['jumps'], { jumps: 4, last_m: 2500, last_s: 12.5 })))
      .toEqual([['jumps', { n: 4 }], ['lastJump', { distance: '2,5 km', seconds: '12,5' }]])
    expect(lines(signal('transfers', ['chain'], { amount: '25.00', sender_id: 's', recipient_id: 'r', entry_id: 'e' }))[0]![0]).toBe('transfer')
    expect(lines(signal('rating_ring', ['rating_ring'], { rides: 4, days: 30 }))).toEqual([['ratingRing', { n: 4, days: 30 }]])
    // Missing or odd evidence (an older signal) shows nothing instead of breaking.
    expect(lines(signal('fake_gps', ['mocked'], {}))).toEqual([])
  })
})

describe('anti-fraud settings (doc 16)', () => {
  it('shows shares as percentages and sends fractions', () => {
    const config = settingsToPayload(defaultSettings())
    expect(config.risk).toMatchObject({ window_days: 90, freeze_score: 60, min_path_share: 0.3, min_duration_share: 0.3, first_transfer_hold_hours: 24 })
    const form = settingsFromConfig({ ...config, risk: { ...config.risk, min_path_share: 0.25 } })
    expect(form.risk.min_path_share).toBe(25)
    form.risk.freeze_score = 70
    expect(changedSettings(settingsToPayload(form), config)).toEqual({ risk: { ...config.risk, min_path_share: 0.25, freeze_score: 70 } })
  })

  it('fills defaults from an older API', () => {
    const form = settingsFromConfig({ ...settingsToPayload(defaultSettings()), risk: undefined } as unknown as AppConfig)
    expect(form.risk).toMatchObject({ max_accounts_per_device: 2, min_duration_share: 30, rating_ring_rides: 3 })
  })

  it('validates ranges', () => {
    const form = defaultSettings()
    expect(keys(form)).toEqual([])
    form.risk.freeze_score = 5
    expect(keys(form)).toEqual(['riskNumber'])
    form.risk.freeze_score = 60
    form.risk.min_path_share = 101
    expect(keys(form)).toEqual(['riskNumber'])
    form.risk.min_path_share = 12.5
    form.risk.first_transfer_hold_hours = 0
    expect(keys(form)).toEqual([])
  })
})
