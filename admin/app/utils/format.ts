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
