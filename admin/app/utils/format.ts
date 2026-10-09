export function formatDate(value: string | null | undefined, locale: string): string {
  if (!value) return '—'
  return new Intl.DateTimeFormat(locale, { dateStyle: 'medium', timeStyle: 'short' }).format(new Date(value))
}

export function formatDay(value: string | null | undefined, locale: string): string {
  if (!value) return '—'
  // Plain dates (YYYY-MM-DD) are calendar days: format them in UTC so they never shift by a day.
  return new Intl.DateTimeFormat(locale, { dateStyle: 'medium', timeZone: 'UTC' }).format(new Date(value))
}

/** Whole years between a YYYY-MM-DD birth date and today. */
export function ageFrom(birthDate: string | null | undefined, today: Date = new Date()): number | null {
  if (!birthDate) return null
  const [y, m, d] = birthDate.slice(0, 10).split('-').map(Number)
  if (!y || !m || !d) return null
  let age = today.getFullYear() - y
  if (today.getMonth() + 1 < m || (today.getMonth() + 1 === m && today.getDate() < d)) age--
  return age
}

export function formatNumber(value: number | null | undefined, locale: string, maximumFractionDigits = 0): string {
  if (value === null || value === undefined || !Number.isFinite(value)) return '—'
  return new Intl.NumberFormat(locale, { maximumFractionDigits }).format(value)
}

/** 0.8 → "80 %" (locale-dependent spacing). */
export function formatPercent(rate: number | null | undefined, locale: string): string {
  if (rate === null || rate === undefined || !Number.isFinite(rate)) return '—'
  return new Intl.NumberFormat(locale, { style: 'percent', maximumFractionDigits: 1 }).format(rate)
}

/** Seconds as minutes for KPI tiles: 35 → "0,6 min", 290 → "4,8 min", 4000 → "1 h 7 min". */
export function formatSecondsAsMinutes(seconds: number | null | undefined, locale: string): string {
  if (seconds === null || seconds === undefined || !Number.isFinite(seconds)) return '—'
  const minutes = seconds / 60
  if (minutes >= 60) return `${Math.floor(minutes / 60)} h ${Math.round(minutes % 60)} min`
  return `${new Intl.NumberFormat(locale, { maximumFractionDigits: minutes < 10 ? 1 : 0 }).format(minutes)} min`
}
