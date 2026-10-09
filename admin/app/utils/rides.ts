import type { Ride, RideStatus } from '~/types/api'
import { ACTIVE_RIDE_STATUSES } from '~/types/api'

type BadgeColor = 'neutral' | 'info' | 'success' | 'error' | 'warning' | 'primary'

const rideStatusColors: Record<RideStatus, BadgeColor> = {
  searching: 'warning',
  driver_assigned: 'info',
  driver_arrived: 'info',
  in_progress: 'primary',
  completed: 'success',
  cancelled_by_passenger: 'neutral',
  cancelled_by_driver: 'neutral',
  cancelled_by_admin: 'neutral',
  no_drivers: 'error',
}

/** Unknown statuses (a newer API) render as neutral badges instead of breaking the page. */
export function rideStatusColor(status: string): BadgeColor {
  return rideStatusColors[status as RideStatus] ?? 'neutral'
}

/** Hex colours for map markers (SVG attributes cannot use CSS variables). */
export const rideStatusHex: Record<string, string> = {
  searching: '#d97706',
  driver_assigned: '#2563eb',
  driver_arrived: '#7c3aed',
  in_progress: '#0e7c5a',
}

export const MAP_COLORS = {
  pickup: '#0e7c5a',
  dropoff: '#dc2626',
  route: '#2563eb',
  driverFree: '#16a34a',
  driverBusy: '#d97706',
  serviceArea: '#0e7c5a',
}

export function isActiveRide(status: string): boolean {
  return ACTIVE_RIDE_STATUSES.includes(status as RideStatus)
}

export function isCancelledRide(status: string): boolean {
  return status.startsWith('cancelled')
}

/**
 * Ride/offer/online-driver ids are the driver's *user* id; /drivers/{id} needs the profile id.
 * Link to the profile when the API includes it, otherwise to the user page.
 */
export function driverLink(userId: string, profileId?: string | null): string {
  return profileId ? `/drivers/${profileId}` : `/users/${userId}`
}

export function personName(person: { first_name?: string | null, full_name?: string | null } | null | undefined): string {
  return person?.full_name || person?.first_name || '—'
}

export function shortAddress(place: Ride['pickup'] | null | undefined): string {
  if (!place) return '—'
  return place.address || `${place.lat.toFixed(5)}, ${place.lng.toFixed(5)}`
}

/** "2.40" → "$2.40" (fares are always USD). */
export function formatMoney(value: string | number | null | undefined, locale: string): string {
  if (value === null || value === undefined || value === '') return '—'
  const amount = Number(value)
  if (!Number.isFinite(amount)) return String(value)
  return new Intl.NumberFormat(locale, { style: 'currency', currency: 'USD', currencyDisplay: 'narrowSymbol' }).format(amount)
}

export function formatMultiplier(value: string | number | null | undefined): string {
  if (value === null || value === undefined || value === '') return '—'
  const n = Number(value)
  return Number.isFinite(n) ? `×${n.toFixed(2)}` : String(value)
}

export function formatDistance(meters: number | null | undefined, locale: string): string {
  if (meters === null || meters === undefined) return '—'
  if (meters < 1000) return `${Math.round(meters)} m`
  return `${new Intl.NumberFormat(locale, { maximumFractionDigits: 1 }).format(meters / 1000)} km`
}

export function formatDuration(seconds: number | null | undefined): string {
  if (seconds === null || seconds === undefined) return '—'
  const minutes = Math.max(1, Math.round(seconds / 60))
  if (minutes < 60) return `${minutes} min`
  return `${Math.floor(minutes / 60)} h ${minutes % 60} min`
}

export function formatRating(value: number | string | null | undefined): string | null {
  if (value === null || value === undefined || value === '') return null
  const n = Number(value)
  return Number.isFinite(n) ? n.toFixed(1) : null
}

export function formatTime(value: string | null | undefined, locale: string): string {
  if (!value) return '—'
  return new Intl.DateTimeFormat(locale, { timeStyle: 'short' }).format(new Date(value))
}
