import { describe, expect, it } from 'vitest'
import type { AppConfig, CancellationCount } from '../app/types/api'
import { cancelReasonKey, groupCancellations, isPauseActive, qualityBadge, shareOf } from '../app/utils/quality'
import { changedSettings, defaultSettings, settingsFromConfig, settingsToPayload, validateSettings } from '../app/utils/settings'

const NOW = Date.parse('2026-10-13T12:00:00Z')
const keys = (form: ReturnType<typeof defaultSettings>) => validateSettings(form).map(i => i.key)

describe('service quality (doc 15)', () => {
  it('labels levels and reasons', () => {
    expect(qualityBadge('review')).toEqual({ color: 'error', variant: 'solid' })
    expect(qualityBadge('ok').color).toBe('success')
    expect(qualityBadge('something_new')).toEqual({ color: 'neutral', variant: 'subtle' })
    expect(cancelReasonKey('no_show')).toBe('quality.reasonCodes.no_show')
    expect(cancelReasonKey(null)).toBe('quality.reasonCodes.none')
  })

  it('knows which pauses still run', () => {
    expect(isPauseActive({ until: '2026-10-13T12:10:00Z', lifted_at: null }, NOW)).toBe(true)
    expect(isPauseActive({ until: '2026-10-13T11:50:00Z', lifted_at: null }, NOW)).toBe(false)
    expect(isPauseActive({ until: '2026-10-13T12:10:00Z', lifted_at: '2026-10-13T11:55:00Z' }, NOW)).toBe(false)
  })

  it('groups cancellations by side, most frequent reason first', () => {
    const rows: CancellationCount[] = [
      { side: 'driver', reason_code: 'no_show', total: 4, counted: 0, reassigned: 0 },
      { side: 'passenger', reason_code: 'changed_plans', total: 2, counted: 1, reassigned: 0 },
      { side: 'driver', reason_code: 'vehicle_problem', total: 6, counted: 6, reassigned: 5 },
      { side: 'passenger', reason_code: null, total: 3, counted: 3, reassigned: 0 },
    ]
    const groups = groupCancellations(rows)
    expect(groups.map(g => g.side)).toEqual(['passenger', 'driver'])
    expect(groups[0]).toMatchObject({ total: 5, counted: 4, reassigned: 0 })
    expect(groups[0]!.rows.map(r => r.reason_code)).toEqual([null, 'changed_plans'])
    expect(groups[1]).toMatchObject({ total: 10, counted: 6, reassigned: 5 })
    expect(groupCancellations(rows.filter(r => r.side === 'driver')).map(g => g.side)).toEqual(['driver'])
    expect(groupCancellations([])).toEqual([])
    expect(shareOf(6, 10)).toBe(0.6)
    expect(shareOf(0, 0)).toBe(0)
  })
})

describe('quality settings (doc 15)', () => {
  it('shows rates as percentages and sends fractions', () => {
    const config = settingsToPayload(defaultSettings())
    expect(config.quality).toMatchObject({ driver_cancel_warn: 0.15, driver_cancel_review: 0.35, dispatch_quality_weight: 0.2, pickup_wait_minutes: 5 })
    const form = settingsFromConfig({ ...config, quality: { ...config.quality, driver_cancel_warn: 0.07 } })
    expect(form.quality.driver_cancel_warn).toBe(7)
    expect(settingsToPayload(form).quality.driver_cancel_warn).toBe(0.07)
    form.quality.dispatch_quality_weight = 35
    expect(changedSettings(settingsToPayload(form), config)).toEqual({ quality: { ...config.quality, driver_cancel_warn: 0.07, dispatch_quality_weight: 0.35 } })
  })

  it('fills defaults from an older API', () => {
    const form = settingsFromConfig({ ...settingsToPayload(defaultSettings()), quality: undefined } as unknown as AppConfig)
    expect(form.quality).toMatchObject({ driver_cancel_low_priority: 25, rating_review_below: 4.3, passenger_pause_hours: 24 })
  })

  it('validates ranges and the order of thresholds', () => {
    const form = defaultSettings()
    expect(keys(form)).toEqual([])
    form.quality.pickup_wait_minutes = 31
    form.quality.driver_cancel_warn = 30
    form.quality.passenger_no_show_warn = 4
    expect(keys(form)).toEqual(['qualityNumber', 'qualityCancelOrder', 'qualityNoShowOrder'])
    // 0 turns the no-show pause off, so any warning count is fine.
    form.quality.pickup_wait_minutes = 5
    form.quality.driver_cancel_warn = 15
    form.quality.passenger_no_show_pause = 0
    expect(keys(form)).toEqual([])
  })
})
