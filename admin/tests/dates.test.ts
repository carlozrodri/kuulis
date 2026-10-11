import { describe, expect, it } from 'vitest'
import { addDays, caracasToday, daysInRange, endOfMonth, isDay, presetRange, rangeIssue } from '~/utils/dates'

describe('dates', () => {
  it('uses the Caracas calendar day', () => {
    // 02:00 UTC on the 10th is still the 9th in Caracas (UTC-4).
    expect(caracasToday(new Date('2026-10-10T02:00:00Z'))).toBe('2026-10-09')
  })

  it('does day arithmetic across months and leap years', () => {
    expect(addDays('2026-10-31', 1)).toBe('2026-11-01')
    expect(endOfMonth('2028-02-10')).toBe('2028-02-29')
    expect(daysInRange('2026-10-01', '2026-10-31')).toBe(31)
    expect(daysInRange('2026-10-02', '2026-10-01')).toBe(0)
  })

  it('builds presets', () => {
    expect(presetRange('last7', '2026-10-09')).toEqual({ from: '2026-10-03', to: '2026-10-09' })
    expect(presetRange('lastMonth', '2026-03-15')).toEqual({ from: '2026-02-01', to: '2026-02-28' })
  })

  it('validates ranges like the API', () => {
    expect(isDay('2026-02-30')).toBe(false)
    expect(rangeIssue({ from: '2026-10-09', to: '2026-10-01' })).toBe('order')
    expect(rangeIssue({ from: '2025-01-01', to: '2026-10-01' })).toBe('tooLong')
    expect(rangeIssue({ from: '2026-10-01', to: '2026-10-09' })).toBeNull()
  })
})
