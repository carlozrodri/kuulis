import type { ReferralAdmin, ReferralProgram, ReferralStatus } from '~/types/api'
import { fromLocalInput, toLocalInput } from '~/utils/promotions'

type BadgeColor = 'neutral' | 'info' | 'success' | 'error' | 'warning' | 'primary'

/** Doc 22 limits (same as the API validation). */
export const REFERRAL_LIMITS = {
  reward_usd: [0, 1000],
  required_trips: [1, 500],
  window_days: [1, 365],
  monthly_cap: [0, 1000],
  budget_usd: [0, 1_000_000],
} as const
export const REFERRAL_NOTE_MAX = 500

export function referralStatusColor(status: ReferralStatus | string): BadgeColor {
  return ({ pending: 'info', qualified: 'warning', held: 'warning', rewarded: 'success', rejected: 'neutral' } as Record<string, BadgeColor>)[status] ?? 'neutral'
}

export type ReferralAction = 'release' | 'reject' | 'reopen'

/**
 * What the team can do with a referral: pay a held or waiting reward, reject anything not paid
 * (an unreviewed shared-identity alert is "marked as reviewed"), and reopen a rejection.
 */
export function referralActions(referral: Pick<ReferralAdmin, 'status' | 'reason' | 'reviewed_at'>): ReferralAction[] {
  switch (referral.status) {
    case 'held':
    case 'qualified':
      return ['release', 'reject']
    case 'pending':
      return ['reject']
    case 'rejected':
      return referral.reason === 'shared_identity' && !referral.reviewed_at ? ['reopen', 'reject'] : ['reopen']
    default:
      return []
  }
}

/** An alert: a held reward or a shared-identity rejection nobody looked at yet. */
export const isReferralAlert = (referral: Pick<ReferralAdmin, 'status' | 'reason' | 'reviewed_at'>) =>
  referral.status === 'held' || (referral.status === 'rejected' && referral.reason === 'shared_identity' && !referral.reviewed_at)

/** 0–100 for the progress bar of the invited driver's trips. */
export function referralProgress(referral: Pick<ReferralAdmin, 'trips' | 'required_trips'>): number {
  if (referral.required_trips <= 0) return 0
  return Math.min(100, Math.round((referral.trips / referral.required_trips) * 100))
}

/** List query: "alerts" is a filter of its own, "all" sends nothing. */
export function referralsQuery(filters: { status: ReferralStatus | 'all' | 'alerts', q: string, limit: number, offset: number }) {
  return {
    limit: filters.limit,
    offset: filters.offset,
    ...(filters.status === 'alerts' ? { alerts: true } : filters.status !== 'all' ? { status: filters.status } : {}),
    ...(filters.q ? { q: filters.q } : {}),
  }
}

/** Editable copy: amounts as numbers and dates as `datetime-local` values. */
export interface ReferralProgramForm {
  enabled: boolean
  reward_usd: number
  required_trips: number
  window_days: number
  referred_free_month: boolean
  monthly_cap: number
  budget_usd: number
  starts_at: string
  ends_at: string
}

export function toProgramForm(program: ReferralProgram): ReferralProgramForm {
  return {
    enabled: program.enabled,
    reward_usd: Number(program.reward_usd),
    required_trips: program.required_trips,
    window_days: program.window_days,
    referred_free_month: program.referred_free_month,
    monthly_cap: program.monthly_cap,
    budget_usd: Number(program.budget_usd),
    starts_at: toLocalInput(program.starts_at),
    ends_at: toLocalInput(program.ends_at),
  }
}

export function fromProgramForm(form: ReferralProgramForm): ReferralProgram {
  return {
    enabled: form.enabled,
    reward_usd: form.reward_usd.toFixed(2),
    required_trips: form.required_trips,
    window_days: form.window_days,
    referred_free_month: form.referred_free_month,
    monthly_cap: form.monthly_cap,
    budget_usd: form.budget_usd.toFixed(2),
    starts_at: fromLocalInput(form.starts_at),
    ends_at: fromLocalInput(form.ends_at),
  }
}

/** i18n key of the first problem in the form, or null when it can be saved. */
export function programFormError(form: ReferralProgramForm): string | null {
  for (const [key, [min, max]] of Object.entries(REFERRAL_LIMITS)) {
    const value = form[key as keyof typeof REFERRAL_LIMITS]
    if (!Number.isFinite(value) || value < min || value > max) return `referrals.program.errors.${key}`
  }
  const start = fromLocalInput(form.starts_at)
  const end = fromLocalInput(form.ends_at)
  if (start && end && end <= start) return 'referrals.program.errors.dates'
  return null
}
