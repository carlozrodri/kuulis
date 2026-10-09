import type {
  AdminCharge,
  AdminTopUp,
  AdminTransfer,
  Charge,
  ChargeStatus,
  FeeTier,
  Month,
  PartyRef,
  TopUpStatus,
  WalletEntry,
  WalletEntryKind,
} from '~/types/api'

type BadgeColor = 'neutral' | 'info' | 'success' | 'error' | 'warning' | 'primary'

export const topUpStatusColor: Record<TopUpStatus, BadgeColor> = {
  pending: 'warning',
  unmatched: 'info',
  completed: 'success',
  rejected: 'neutral',
}

export const chargeStatusColor: Record<ChargeStatus, BadgeColor> = {
  pending: 'warning',
  paid: 'success',
  waived: 'neutral',
}

export const walletEntryColor: Record<WalletEntryKind, BadgeColor> = {
  promo_credit: 'primary',
  top_up: 'success',
  transfer_in: 'info',
  transfer_out: 'info',
  subscription_fee: 'warning',
  adjustment: 'neutral',
}

const toNumber = (value: string | number | null | undefined): number | null => {
  if (value === null || value === undefined || value === '') return null
  const n = Number(value)
  return Number.isFinite(n) ? n : null
}

/** "12.5" → "12,50 USDT". The wallet is in USDT (= USD), so the unit is spelled out. */
export function formatUsdt(value: string | number | null | undefined, locale: string, signed = false): string {
  const n = toNumber(value)
  if (n === null) return '—'
  const text = new Intl.NumberFormat(locale, {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
    ...(signed ? { signDisplay: 'exceptZero' as const } : {}),
  }).format(n)
  return `${text} USDT`
}

/** Sum of decimal strings, rounded to the cent (avoids float noise like 0.30000000000000004). */
export function sumAmounts(values: (string | number | null | undefined)[]): number {
  const cents = values.reduce<number>((acc, v) => acc + Math.round((toNumber(v) ?? 0) * 100), 0)
  return cents / 100
}

// ---- People on list rows ----------------------------------------------------------------------

/** The driver on a top-up/charge row: nested `user` per the contract, flat `user_*` keys tolerated. */
export function ownerOf(row: AdminTopUp | AdminCharge): PartyRef | null {
  if (row.user?.id) return row.user
  if (row.user_id) return { id: row.user_id, name: row.user_name ?? null, email: row.user_email ?? null }
  return null
}

export function transferParties(row: AdminTransfer): { sender: PartyRef | null, recipient: PartyRef | null } {
  return { sender: row.sender ?? row.from_user ?? null, recipient: row.recipient ?? row.to_user ?? null }
}

export function walletLink(userId: string): string {
  return `/wallets/${userId}`
}

// ---- Months (Caracas time, "2026-10") ----------------------------------------------------------

export const CARACAS_TZ = 'America/Caracas'
const MONTH = /^(\d{4})-(0[1-9]|1[0-2])$/

export function isMonth(value: string | null | undefined): value is Month {
  return !!value && MONTH.test(value)
}

/** Month in progress in Caracas. */
export function caracasMonth(now: Date = new Date()): Month {
  const parts = new Intl.DateTimeFormat('en-CA', { timeZone: CARACAS_TZ, year: 'numeric', month: '2-digit' }).formatToParts(now)
  const year = parts.find(p => p.type === 'year')?.value
  const month = parts.find(p => p.type === 'month')?.value
  return `${year}-${month}`
}

export function addMonths(month: Month, n: number): Month {
  const [y, m] = month.split('-').map(Number)
  const index = y! * 12 + (m! - 1) + n
  return `${Math.floor(index / 12)}-${String((index % 12) + 1).padStart(2, '0')}`
}

/** "2026-10" → "octubre de 2026". */
export function formatMonth(month: string | null | undefined, locale: string): string {
  if (!isMonth(month)) return month || '—'
  const [y, m] = month.split('-').map(Number)
  return new Intl.DateTimeFormat(locale, { month: 'long', year: 'numeric', timeZone: 'UTC' }).format(new Date(Date.UTC(y!, m! - 1, 1)))
}

/** `count` months going back from `from` (inclusive), newest first. */
export function monthsBack(from: Month, count: number): Month[] {
  return Array.from({ length: count }, (_, i) => addMonths(from, -i))
}

/** `count` months going forward from `from` (inclusive). */
export function monthsAhead(from: Month, count: number): Month[] {
  return Array.from({ length: count }, (_, i) => addMonths(from, i))
}

// ---- Charges ------------------------------------------------------------------------------------

/** A pending charge past its due date: the driver is blocked (cannot go online) until it is paid or waived. */
export function isOverdue(charge: Pick<Charge, 'status' | 'due_at' | 'overdue'>, now: number = Date.now()): boolean {
  if (charge.status !== 'pending') return false
  if (typeof charge.overdue === 'boolean') return charge.overdue
  return !!charge.due_at && new Date(charge.due_at).getTime() <= now
}

// ---- Wallet entries -----------------------------------------------------------------------------

export function entryAmountClass(entry: Pick<WalletEntry, 'amount'>): string {
  const n = toNumber(entry.amount) ?? 0
  if (n > 0) return 'text-success'
  if (n < 0) return 'text-error'
  return ''
}

// ---- Fee schedules ------------------------------------------------------------------------------

export const FEE_MAX = 1000
export const TIER_ABOVE_MAX = 1_000_000
export const TIERS_MAX = 50

export interface TierForm { above: number | null, fee: number | null }

export function tiersToForm(tiers: FeeTier[] | null | undefined): TierForm[] {
  return (tiers ?? []).map(tier => ({ above: toNumber(tier.above), fee: toNumber(tier.fee) }))
}

const finite = (v: number | null | undefined): v is number => v !== null && v !== undefined && Number.isFinite(v)

export function tiersToPayload(tiers: TierForm[]): FeeTier[] {
  return tiers.map(tier => ({ above: (finite(tier.above) ? tier.above : 0).toFixed(2), fee: (finite(tier.fee) ? tier.fee : 0).toFixed(2) }))
}

/** The schedule from business-model.md: 0 up to 100 USD, then +5 USD every 100 USD up to 30 USD. */
export function defaultTiers(): TierForm[] {
  return [0, 100, 200, 300, 400, 500, 600].map((above, i) => ({ above, fee: i * 5 }))
}

export interface ScheduleIssue { key: string, params?: Record<string, string | number> }

/**
 * Client-side checks mirroring the contract (the API validates again): the effective month is next month
 * or later; tiers are sorted by `above`, strictly increasing, the first at 0; fees between 0 and 1000.
 * Returns i18n keys under subscriptions.schedules.errors.
 */
export function validateSchedule(effectiveMonth: string, tiers: TierForm[], current: Month = caracasMonth()): ScheduleIssue[] {
  const issues: ScheduleIssue[] = []
  if (!isMonth(effectiveMonth)) issues.push({ key: 'month' })
  else if (effectiveMonth <= current) issues.push({ key: 'monthTooEarly', params: { month: addMonths(current, 1) } })

  if (!tiers.length) issues.push({ key: 'noTiers' })
  if (tiers.length > TIERS_MAX) issues.push({ key: 'tooMany', params: { max: TIERS_MAX } })
  if (tiers.length && tiers[0]!.above !== 0) issues.push({ key: 'firstAbove' })
  tiers.forEach((tier, index) => {
    const n = index + 1
    if (!finite(tier.above) || tier.above < 0 || tier.above > TIER_ABOVE_MAX) issues.push({ key: 'above', params: { n } })
    else if (index > 0 && finite(tiers[index - 1]!.above) && tier.above <= tiers[index - 1]!.above!) issues.push({ key: 'increasing', params: { n } })
    if (!finite(tier.fee) || tier.fee < 0 || tier.fee > FEE_MAX) issues.push({ key: 'fee', params: { n, max: FEE_MAX } })
  })
  return issues
}

/** Fee for a month's earnings: the tier with the highest `above` the earnings exceed; 0 earnings → 0. */
export function feeFor(earnings: number, tiers: TierForm[] | FeeTier[]): number {
  if (!(earnings > 0)) return 0
  let fee = 0
  let best = -Infinity
  for (const tier of tiers) {
    const above = toNumber(tier.above as number | string | null)
    const value = toNumber(tier.fee as number | string | null)
    if (above === null || value === null) continue
    if (earnings > above && above > best) {
      best = above
      fee = value
    }
  }
  return fee
}
