import type { RateOrigin, VesAmount } from '~/types/api'

const twoDecimals = (locale: string) => new Intl.NumberFormat(locale, { minimumFractionDigits: 2, maximumFractionDigits: 2 })

const toNumber = (value: string | number | null | undefined): number | null => {
  if (value === null || value === undefined || value === '') return null
  const n = Number(value)
  return Number.isFinite(n) ? n : null
}

/** "875.65" → "875,65" (Bs per 1 USD). */
export function formatRate(value: string | number | null | undefined, locale: string): string {
  const n = toNumber(value)
  return n === null ? '—' : twoDecimals(locale).format(n)
}

/** "2101.56" → "Bs. 2.101,56". Intl's VES symbol varies by browser, so the prefix is fixed. */
export function formatVes(value: string | number | null | undefined, locale: string): string {
  const n = toNumber(value)
  return n === null ? '—' : `Bs. ${twoDecimals(locale).format(n)}`
}

export function hasVesAmount(amount: VesAmount | null | undefined): boolean {
  return !!amount && (amount.bcv !== null || amount.binance !== null)
}

export const rateOriginColor: Record<RateOrigin, 'neutral' | 'info'> = {
  auto: 'neutral',
  manual: 'info',
}

/** "2160" minutes → "36 h"; values that are not whole hours stay in minutes. */
export function formatMinutes(minutes: number | null | undefined): string {
  if (minutes === null || minutes === undefined || !Number.isFinite(minutes)) return '—'
  if (minutes >= 60 && minutes % 60 === 0) return `${minutes / 60} h`
  return `${minutes} min`
}

/** Age of a timestamp as "hace 5 min" / "5 minutes ago". */
export function formatAgo(value: string | null | undefined, locale: string, now: number = Date.now()): string {
  if (!value) return '—'
  const seconds = Math.round((new Date(value).getTime() - now) / 1000)
  const rtf = new Intl.RelativeTimeFormat(locale, { numeric: 'auto' })
  const abs = Math.abs(seconds)
  if (abs < 60) return rtf.format(seconds, 'second')
  if (abs < 3600) return rtf.format(Math.round(seconds / 60), 'minute')
  if (abs < 86_400) return rtf.format(Math.round(seconds / 3600), 'hour')
  return rtf.format(Math.round(seconds / 86_400), 'day')
}
