import { describe, expect, it } from 'vitest'
import type { ReferralProgram } from '../app/types/api'
import { fromProgramForm, isReferralAlert, programFormError, referralActions, referralProgress, referralsQuery, toProgramForm } from '../app/utils/referrals'

const program: ReferralProgram = {
  enabled: true,
  reward_usd: '5.00',
  required_trips: 20,
  window_days: 30,
  referred_free_month: false,
  monthly_cap: 10,
  budget_usd: '500.00',
  starts_at: null,
  ends_at: null,
}

describe('referrals', () => {
  it('offers the actions each status allows', () => {
    expect(referralActions({ status: 'held', reason: 'risk_score', reviewed_at: null })).toEqual(['release', 'reject'])
    expect(referralActions({ status: 'qualified', reason: 'monthly_cap', reviewed_at: null })).toEqual(['release', 'reject'])
    expect(referralActions({ status: 'pending', reason: null, reviewed_at: null })).toEqual(['reject'])
    expect(referralActions({ status: 'rejected', reason: 'shared_identity', reviewed_at: null })).toEqual(['reopen', 'reject'])
    expect(referralActions({ status: 'rejected', reason: 'expired', reviewed_at: null })).toEqual(['reopen'])
    expect(referralActions({ status: 'rewarded', reason: null, reviewed_at: null })).toEqual([])
  })

  it('flags held rewards and unreviewed shared identities as alerts', () => {
    expect(isReferralAlert({ status: 'held', reason: 'risk_score', reviewed_at: null })).toBe(true)
    expect(isReferralAlert({ status: 'rejected', reason: 'shared_identity', reviewed_at: null })).toBe(true)
    expect(isReferralAlert({ status: 'rejected', reason: 'shared_identity', reviewed_at: '2026-10-17T10:00:00Z' })).toBe(false)
    expect(isReferralAlert({ status: 'pending', reason: null, reviewed_at: null })).toBe(false)
  })

  it('caps the progress at 100', () => {
    expect(referralProgress({ trips: 5, required_trips: 20 })).toBe(25)
    expect(referralProgress({ trips: 25, required_trips: 20 })).toBe(100)
    expect(referralProgress({ trips: 1, required_trips: 0 })).toBe(0)
  })

  it('builds the list query', () => {
    expect(referralsQuery({ status: 'all', q: '', limit: 25, offset: 0 })).toEqual({ limit: 25, offset: 0 })
    expect(referralsQuery({ status: 'alerts', q: 'luis', limit: 25, offset: 25 })).toEqual({ limit: 25, offset: 25, alerts: true, q: 'luis' })
    expect(referralsQuery({ status: 'held', q: '', limit: 25, offset: 0 })).toEqual({ limit: 25, offset: 0, status: 'held' })
  })

  it('round-trips the program form and validates it', () => {
    const form = toProgramForm(program)
    expect(form.reward_usd).toBe(5)
    expect(fromProgramForm(form)).toEqual(program)
    expect(programFormError(form)).toBeNull()
    expect(programFormError({ ...form, required_trips: 0 })).toBe('referrals.program.errors.required_trips')
    expect(programFormError({ ...form, starts_at: '2026-11-02T00:00', ends_at: '2026-11-01T00:00' })).toBe('referrals.program.errors.dates')
  })
})
