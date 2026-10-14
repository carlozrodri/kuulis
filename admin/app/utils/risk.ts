import type { HoldRead, HoldStatus, RiskKind, RiskSummary, RiskUser, SignalRead, SignalStatus } from '~/types/api'
import { formatNumber } from '~/utils/format'
import { driverLink, formatDistance, formatDuration } from '~/utils/rides'
import { formatUsdt } from '~/utils/wallet'

type BadgeColor = 'neutral' | 'info' | 'success' | 'error' | 'warning' | 'primary'

/** Doc 16: the API's default freeze score, used when the settings are not at hand. */
export const RISK_FREEZE_DEFAULT = 60
/** Ban reason length (same as the API). */
export const RISK_BAN_REASON_MIN = 3
export const RISK_BAN_REASON_MAX = 500
export const RISK_NOTE_MAX = 500

/** Colour of a 0–100 risk score: red from the freeze score, amber from half of it, grey above 0. */
export function riskScoreColor(score: number, freezeScore: number = RISK_FREEZE_DEFAULT): BadgeColor {
  if (score >= freezeScore) return 'error'
  if (score >= freezeScore / 2) return 'warning'
  return score > 0 ? 'neutral' : 'success'
}

export function signalStatusColor(status: SignalStatus | string): BadgeColor {
  return ({ open: 'warning', confirmed: 'error', dismissed: 'neutral' } as Record<string, BadgeColor>)[status] ?? 'neutral'
}

export function holdStatusColor(status: HoldStatus | string): BadgeColor {
  return ({ held: 'warning', released: 'success', voided: 'error' } as Record<string, BadgeColor>)[status] ?? 'neutral'
}

export const RISK_KIND_ICONS: Record<RiskKind, string> = {
  shared_device: 'i-lucide-smartphone',
  fake_gps: 'i-lucide-map-pin-off',
  suspicious_ride: 'i-lucide-route-off',
  frequent_pair: 'i-lucide-users-round',
  transfers: 'i-lucide-arrow-left-right',
  rating_ring: 'i-lucide-star',
}

export const riskKindIcon = (kind: string) => RISK_KIND_ICONS[kind as RiskKind] ?? 'i-lucide-shield-alert'

/** i18n keys; unknown codes (a newer API) fall back to the code itself in the page. */
export const riskKindKey = (kind: string) => `risk.kinds.${kind}`
export const riskReasonKey = (reason: string) => `risk.reasons.${reason}`
export const holdKindKey = (kind: string) => `risk.holdKinds.${kind}`
export const blockedKindKey = (kind: string) => `risk.blockedKinds.${kind}`

/** Page of a risk person: their driver profile when they drive, else the user page. */
export const riskUserLink = (user: Pick<RiskUser, 'id' | 'driver_profile_id'>) => driverLink(user.id, user.driver_profile_id)

/** Open alerts of one kind (0 when the summary does not list it). */
export function riskOpenCount(summary: RiskSummary | null | undefined, kind?: RiskKind): number {
  const rows = summary?.open ?? []
  return rows.filter(r => !kind || r.kind === kind).reduce((n, r) => n + r.open, 0)
}

/** Menu badge: open alerts plus held payments. */
export function riskBadgeTotal(summary: RiskSummary | null | undefined): number {
  return riskOpenCount(summary) + (summary?.holds ?? 0)
}

/** A hold that someone can still release or void. */
export const isHoldOpen = (hold: Pick<HoldRead, 'status'>) => hold.status === 'held'

export interface EvidenceLine {
  /** Under risk.evidence. */
  key: string
  params: Record<string, string | number>
}

const num = (value: unknown): number | null => (typeof value === 'number' && Number.isFinite(value) ? value : null)

/**
 * The numbers behind an alert in plain words ("Recorrido real 120 m de 3,4 km estimados"), as i18n keys
 * under risk.evidence with their parameters already formatted.
 */
export function riskEvidenceLines(signal: Pick<SignalRead, 'kind' | 'reasons' | 'evidence'>, locale: string): EvidenceLine[] {
  const e = signal.evidence ?? {}
  const lines: EvidenceLine[] = []
  const add = (key: string, params: Record<string, string | number> = {}) => lines.push({ key: `risk.evidence.${key}`, params })

  switch (signal.kind) {
    case 'suspicious_ride':
    case 'frequent_pair': {
      if (signal.reasons.includes('same_device')) add('sameDevice')
      const points = num(e.points)
      const distance = num(e.distance_m)
      const path = num(e.path_m)
      if (points !== null && points < 2) {
        if (signal.reasons.includes('no_track')) add('noTrack')
      }
      else if (path !== null && distance !== null) {
        add('path', { real: formatDistance(path, locale), estimated: formatDistance(distance, locale) })
      }
      if (signal.reasons.includes('same_place')) add('samePlace')
      const real = num(e.real_s)
      const estimate = num(e.estimate_s)
      if (real !== null && estimate !== null && real > 0) {
        add('duration', { real: formatDuration(real), estimated: formatDuration(estimate) })
      }
      const pair = num(e.pair_rides)
      const days = num(e.days)
      if (pair !== null && pair >= 2) {
        if (days !== null) add('pairDays', { n: pair, days })
        else add('pair', { n: pair })
      }
      if (e.promotion === true) add('promotion')
      break
    }
    case 'shared_device': {
      const count = num(e.count) ?? (Array.isArray(e.accounts) ? e.accounts.length : null)
      if (count !== null) add('sharedDevice', { n: count })
      const phone = [e.model, e.platform].filter(v => typeof v === 'string' && v).join(' · ')
      if (phone) add('phone', { phone })
      break
    }
    case 'fake_gps': {
      const lat = num(e.lat)
      const lng = num(e.lng)
      if (lat !== null && lng !== null) add(e.ride === true ? 'mockedOnRide' : 'mocked', { lat: lat.toFixed(5), lng: lng.toFixed(5) })
      const jumps = num(e.jumps)
      if (jumps !== null) {
        add('jumps', { n: jumps })
        const lastM = num(e.last_m)
        const lastS = num(e.last_s)
        if (lastM !== null && lastS !== null) {
          add('lastJump', { distance: formatDistance(lastM, locale), seconds: formatNumber(lastS, locale, 1) })
        }
      }
      break
    }
    case 'transfers': {
      if (e.amount !== undefined && e.amount !== null) add('transfer', { amount: formatUsdt(e.amount as string, locale) })
      break
    }
    case 'rating_ring': {
      const rides = num(e.rides)
      if (rides !== null) add('ratingRing', { n: rides, days: num(e.days) ?? 30 })
      break
    }
  }
  return lines
}

/** Query of the signals list: `status=` empty asks for every status (the API defaults to open). */
export function signalsQuery(filters: { kind: RiskKind | 'all', status: SignalStatus | 'all', limit: number, offset: number, userId?: string }) {
  return {
    status: filters.status === 'all' ? '' : filters.status,
    limit: filters.limit,
    offset: filters.offset,
    ...(filters.kind !== 'all' ? { kind: filters.kind } : {}),
    ...(filters.userId ? { user_id: filters.userId } : {}),
  }
}
