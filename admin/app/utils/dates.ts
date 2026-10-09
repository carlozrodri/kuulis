import type { Day } from '~/types/api'

// Calendar days in Caracas time ("2026-10-09"). The API reads `from`/`to` filters as Caracas days, both
// inclusive, so ranges are built from Caracas' "today" and plain UTC date arithmetic (no DST in Venezuela).

const DAY = /^\d{4}-\d{2}-\d{2}$/

export function isDay(value: string | null | undefined): value is Day {
  return !!value && DAY.test(value) && !Number.isNaN(Date.parse(`${value}T00:00:00Z`))
}

/** Today in Caracas. */
export function caracasToday(now: Date = new Date()): Day {
  return new Intl.DateTimeFormat('en-CA', { timeZone: 'America/Caracas', year: 'numeric', month: '2-digit', day: '2-digit' }).format(now)
}

const toUtc = (day: Day) => new Date(`${day}T00:00:00Z`)
const fromUtc = (date: Date): Day => date.toISOString().slice(0, 10)

export function addDays(day: Day, n: number): Day {
  const date = toUtc(day)
  date.setUTCDate(date.getUTCDate() + n)
  return fromUtc(date)
}

/** Number of days in the range, both ends included (0 when `to` is before `from`). */
export function daysInRange(from: Day, to: Day): number {
  return Math.max(0, Math.round((toUtc(to).getTime() - toUtc(from).getTime()) / 86_400_000) + 1)
}

/** Every day from `from` to `to`, inclusive (charts fill the days the API leaves out with zeros). */
export function listDays(from: Day, to: Day): Day[] {
  return Array.from({ length: Math.min(daysInRange(from, to), 400) }, (_, i) => addDays(from, i))
}

export function startOfMonth(day: Day): Day {
  return `${day.slice(0, 7)}-01`
}

export function endOfMonth(day: Day): Day {
  const date = toUtc(startOfMonth(day))
  date.setUTCMonth(date.getUTCMonth() + 1, 0)
  return fromUtc(date)
}

/** The API rejects longer ranges with 422. */
export const MAX_RANGE_DAYS = 366

export type RangePreset = 'today' | 'last7' | 'last30' | 'thisMonth' | 'lastMonth' | 'custom'

export interface DayRange { from: Day, to: Day }

export function presetRange(preset: Exclude<RangePreset, 'custom'>, today: Day = caracasToday()): DayRange {
  switch (preset) {
    case 'today':
      return { from: today, to: today }
    case 'last7':
      return { from: addDays(today, -6), to: today }
    case 'last30':
      return { from: addDays(today, -29), to: today }
    case 'thisMonth':
      return { from: startOfMonth(today), to: endOfMonth(today) }
    case 'lastMonth': {
      const previous = addDays(startOfMonth(today), -1)
      return { from: startOfMonth(previous), to: previous }
    }
  }
}

/** Problem with a custom range, as an i18n key under `range.errors`, or null when it is valid. */
export function rangeIssue(range: DayRange): 'invalid' | 'order' | 'tooLong' | null {
  if (!isDay(range.from) || !isDay(range.to)) return 'invalid'
  if (range.from > range.to) return 'order'
  if (daysInRange(range.from, range.to) > MAX_RANGE_DAYS) return 'tooLong'
  return null
}

/** "2026-10-09" → "9 oct" (short axis label). */
export function formatShortDay(day: Day, locale: string): string {
  if (!isDay(day)) return day
  return new Intl.DateTimeFormat(locale, { day: 'numeric', month: 'short', timeZone: 'UTC' }).format(toUtc(day))
}
