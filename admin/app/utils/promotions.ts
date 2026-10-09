import type { DiscountType, Promotion, PromotionInput, PromotionStats, PromotionStatus, VehicleType } from '~/types/api'
import { VEHICLE_TYPES } from '~/types/api'
import { formatMoney } from '~/utils/rides'

type BadgeColor = 'neutral' | 'info' | 'success' | 'error' | 'warning' | 'primary'

export const promotionStatusColor: Record<PromotionStatus, BadgeColor> = {
  active: 'success',
  scheduled: 'info',
  ended: 'neutral',
  exhausted: 'warning',
  inactive: 'neutral',
}

/** Editable copy of a promotion: decimals as numbers, dates as `datetime-local` values (browser time). */
export interface PromotionForm {
  name: string
  description: string
  /** Empty = automatic promotion. */
  code: string
  discount_type: DiscountType
  discount_value: number | null
  max_discount: number | null
  min_fare: number | null
  starts_at: string
  ends_at: string
  budget: number | null
  max_uses_per_passenger: number | null
  max_total_uses: number | null
  first_ride_only: boolean
  service_areas: string[]
  vehicle_types: VehicleType[]
  is_active: boolean
}

export const PROMO_CODE = /^[A-Z0-9]{3,20}$/
export const PROMO_NAME_MAX = 80
export const PROMO_DESCRIPTION_MAX = 500
export const PROMO_AMOUNT_MAX = 1_000_000
export const PROMO_USES_PER_PASSENGER_MAX = 1000
export const PROMO_TOTAL_USES_MAX = 10_000_000

const pad = (n: number) => String(n).padStart(2, '0')

/** ISO timestamp → `YYYY-MM-DDTHH:mm` in the browser's time zone (what `<input type="datetime-local">` binds). */
export function toLocalInput(value: string | Date | null | undefined): string {
  if (!value) return ''
  const d = new Date(value)
  if (Number.isNaN(d.getTime())) return ''
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`
}

/** `datetime-local` value (browser time) → ISO timestamp in UTC, or null when empty/invalid. */
export function fromLocalInput(value: string): string | null {
  if (!value) return null
  const d = new Date(value)
  return Number.isNaN(d.getTime()) ? null : d.toISOString()
}

/** Codes are stored uppercase without spaces (contract). */
export function normalizeCode(code: string): string {
  return code.replace(/\s+/g, '').toUpperCase()
}

export function defaultPromotionForm(now: Date = new Date()): PromotionForm {
  // Starts at the next full hour and runs for 30 days.
  const start = new Date(now)
  start.setMinutes(0, 0, 0)
  start.setHours(start.getHours() + 1)
  const end = new Date(start)
  end.setDate(end.getDate() + 30)
  return {
    name: '',
    description: '',
    code: '',
    discount_type: 'percent',
    discount_value: 20,
    max_discount: null,
    min_fare: 0,
    starts_at: toLocalInput(start),
    ends_at: toLocalInput(end),
    budget: 100,
    max_uses_per_passenger: 1,
    max_total_uses: null,
    first_ride_only: false,
    service_areas: [],
    vehicle_types: [],
    is_active: true,
  }
}

const num = (value: string | number | null | undefined): number | null => {
  if (value === null || value === undefined || value === '') return null
  const n = Number(value)
  return Number.isFinite(n) ? n : null
}

export function promotionToForm(p: Promotion): PromotionForm {
  return {
    name: p.name,
    description: p.description ?? '',
    code: p.code ?? '',
    discount_type: p.discount_type,
    discount_value: num(p.discount_value),
    max_discount: num(p.max_discount),
    min_fare: num(p.min_fare) ?? 0,
    starts_at: toLocalInput(p.starts_at),
    ends_at: toLocalInput(p.ends_at),
    budget: num(p.budget),
    max_uses_per_passenger: p.max_uses_per_passenger ?? 1,
    max_total_uses: p.max_total_uses ?? null,
    first_ride_only: p.first_ride_only,
    service_areas: [...(p.service_areas ?? [])],
    vehicle_types: [...(p.vehicle_types ?? [])],
    is_active: p.is_active,
  }
}

/** A cleared number input may report undefined or NaN: treat both as "empty". */
const opt = (value: number | null | undefined): number | null =>
  value === null || value === undefined || !Number.isFinite(value) ? null : value
const money = (value: number | null | undefined) => opt(value)?.toFixed(2) ?? null

/** Serializes the form to the API body (amounts as 2-decimal strings, empty code → null). */
export function promotionToPayload(form: PromotionForm): PromotionInput {
  return {
    name: form.name.trim(),
    description: form.description.trim() || null,
    code: normalizeCode(form.code) || null,
    discount_type: form.discount_type,
    discount_value: money(form.discount_value) ?? '0.00',
    // The cap only makes sense for percentages.
    max_discount: form.discount_type === 'percent' ? money(form.max_discount) : null,
    min_fare: money(form.min_fare) ?? '0.00',
    starts_at: fromLocalInput(form.starts_at) ?? '',
    ends_at: fromLocalInput(form.ends_at) ?? '',
    budget: money(form.budget) ?? '0.00',
    max_uses_per_passenger: opt(form.max_uses_per_passenger) ?? 1,
    max_total_uses: opt(form.max_total_uses),
    first_ride_only: form.first_ride_only,
    service_areas: [...form.service_areas],
    vehicle_types: VEHICLE_TYPES.filter(v => form.vehicle_types.includes(v)),
    is_active: form.is_active,
  }
}

/** Keys whose value changed, so an edit only PATCHes what the admin touched. */
export function changedPromotion(current: PromotionInput, original: PromotionInput): Partial<PromotionInput> {
  const patch: Record<string, unknown> = {}
  for (const key of Object.keys(current) as (keyof PromotionInput)[]) {
    const a = Array.isArray(current[key]) ? [...(current[key] as string[])].sort() : current[key]
    const b = Array.isArray(original[key]) ? [...(original[key] as string[])].sort() : original[key]
    if (JSON.stringify(a) !== JSON.stringify(b)) patch[key] = current[key]
  }
  return patch as Partial<PromotionInput>
}

/** Credited (completed rides) + reserved (rides in progress): what the budget already owes. */
export function committedBudget(stats: PromotionStats | null | undefined): number {
  if (!stats) return 0
  // Rounded to the cent so float noise never trips the "budget below committed" check.
  return Math.round(((num(stats.credited) ?? 0) + (num(stats.reserved) ?? 0)) * 100) / 100
}

/** Share of the budget used, 0–100. */
export function budgetUsage(promotion: Pick<Promotion, 'budget' | 'stats'>): number {
  const budget = num(promotion.budget) ?? 0
  if (budget <= 0) return 0
  return Math.min(100, Math.max(0, (committedBudget(promotion.stats) / budget) * 100))
}

export interface PromotionIssue { key: string, params?: Record<string, string | number> }

const isWhole = (v: number | null, max: number) => Number.isInteger(v) && v! >= 1 && v! <= max

/**
 * Client-side checks mirroring docs/api/phase-1c.md; the API validates again.
 * `committed` is credited + reserved when editing (the budget cannot go below it).
 * Returns i18n keys under promotions.errors.
 */
export function validatePromotion(form: PromotionForm, committed = 0): PromotionIssue[] {
  const issues: PromotionIssue[] = []
  const name = form.name.trim()
  if (!name) issues.push({ key: 'nameRequired' })
  else if (name.length > PROMO_NAME_MAX) issues.push({ key: 'nameTooLong', params: { max: PROMO_NAME_MAX } })
  if (form.description.trim().length > PROMO_DESCRIPTION_MAX) issues.push({ key: 'descriptionTooLong', params: { max: PROMO_DESCRIPTION_MAX } })

  const code = normalizeCode(form.code)
  if (code && !PROMO_CODE.test(code)) issues.push({ key: 'code' })

  const value = opt(form.discount_value)
  const maxDiscount = opt(form.max_discount)
  const minFare = opt(form.min_fare)
  const budget = opt(form.budget)
  if (form.discount_type === 'percent') {
    if (value === null || !(value >= 1 && value <= 100)) issues.push({ key: 'percent' })
    if (maxDiscount !== null && !(maxDiscount > 0)) issues.push({ key: 'maxDiscount' })
  }
  else if (value === null || !(value > 0)) {
    issues.push({ key: 'fixed' })
  }
  if (minFare === null || !(minFare >= 0)) issues.push({ key: 'minFare' })

  const start = fromLocalInput(form.starts_at)
  const end = fromLocalInput(form.ends_at)
  if (!start || !end) issues.push({ key: 'dates' })
  else if (end <= start) issues.push({ key: 'endBeforeStart' })

  if (budget === null || !(budget > 0)) issues.push({ key: 'budget' })
  else if (committed > 0 && budget < committed) issues.push({ key: 'budgetBelowCommitted', params: { amount: committed.toFixed(2) } })

  if (!isWhole(opt(form.max_uses_per_passenger), PROMO_USES_PER_PASSENGER_MAX)) {
    issues.push({ key: 'maxUsesPerPassenger', params: { max: PROMO_USES_PER_PASSENGER_MAX } })
  }
  if (opt(form.max_total_uses) !== null && !isWhole(opt(form.max_total_uses), PROMO_TOTAL_USES_MAX)) {
    issues.push({ key: 'maxTotalUses', params: { max: PROMO_TOTAL_USES_MAX } })
  }
  const amounts = [value, maxDiscount, minFare, budget]
  if (amounts.some(v => v !== null && v > PROMO_AMOUNT_MAX)) issues.push({ key: 'amountTooLarge', params: { max: PROMO_AMOUNT_MAX } })
  return issues
}

/** "20 %" or "$1.00" (the optional cap is shown separately). */
export function formatDiscount(p: Pick<Promotion, 'discount_type' | 'discount_value'>, locale: string): string {
  if (p.discount_type === 'fixed') return formatMoney(p.discount_value, locale)
  const n = Number(p.discount_value)
  if (!Number.isFinite(n)) return String(p.discount_value)
  return new Intl.NumberFormat(locale, { style: 'percent', maximumFractionDigits: 2 }).format(n / 100)
}
