import type { ReportCategory, ReportPriority, ReportStatus, Suspension, SuspensionRecord } from '~/types/api'

type BadgeColor = 'neutral' | 'info' | 'success' | 'error' | 'warning' | 'primary'

export const reportStatusColor: Record<ReportStatus, BadgeColor> = {
  open: 'warning',
  in_review: 'info',
  resolved: 'success',
  dismissed: 'neutral',
}

export const reportPriorityColor: Record<ReportPriority, BadgeColor> = {
  urgent: 'error',
  normal: 'neutral',
}

export const reportCategoryIcon: Record<ReportCategory, string> = {
  safety: 'i-lucide-shield-alert',
  harassment: 'i-lucide-message-circle-warning',
  driving: 'i-lucide-bike',
  fare: 'i-lucide-banknote',
  vehicle_mismatch: 'i-lucide-scan-face',
  lost_item: 'i-lucide-package-search',
  no_show: 'i-lucide-user-x',
  app_issue: 'i-lucide-smartphone',
  other: 'i-lucide-circle-help',
}

export function isClosedReport(status: string): boolean {
  return status === 'resolved' || status === 'dismissed'
}

/** Limits from the contract (the API validates again). */
export const REPORT_NOTE_MAX = 2000
export const RESOLUTION_MIN = 3
export const RESOLUTION_MAX = 1000
export const SUSPENSION_REASON_MIN = 3
export const SUSPENSION_REASON_MAX = 500

// ---- Account suspensions --------------------------------------------------------------------

/** A suspension still applies while `until` is null (indefinite) or in the future; expired ones stop on their own. */
export function isSuspensionInForce(suspension: Pick<Suspension, 'until'> | null | undefined, now: number = Date.now()): boolean {
  if (!suspension) return false
  return suspension.until === null || new Date(suspension.until).getTime() > now
}

/** The suspension in force from the history (not lifted and not expired), if any. */
export function currentSuspension(history: SuspensionRecord[] | null | undefined, now: number = Date.now()): SuspensionRecord | null {
  return (history ?? []).find(s => !s.lifted_at && isSuspensionInForce(s, now)) ?? null
}

export type SuspensionPreset = '24h' | '3d' | '7d' | '30d' | 'indefinite' | 'custom'
export const SUSPENSION_PRESETS: SuspensionPreset[] = ['24h', '3d', '7d', '30d', 'indefinite', 'custom']

const PRESET_HOURS: Partial<Record<SuspensionPreset, number>> = { '24h': 24, '3d': 72, '7d': 168, '30d': 720 }

/**
 * `until` for a preset as an ISO datetime, null for indefinite. A custom date (YYYY-MM-DD) ends at the start of
 * the following day in Caracas (UTC−4), so the person can use the app again from that next morning.
 */
export function suspensionUntil(preset: SuspensionPreset, customDay: string | null, now: Date = new Date()): string | null {
  if (preset === 'indefinite') return null
  if (preset === 'custom') {
    if (!customDay || !/^\d{4}-\d{2}-\d{2}$/.test(customDay)) return null
    const end = new Date(`${customDay}T00:00:00-04:00`)
    end.setUTCDate(end.getUTCDate() + 1)
    return end.toISOString()
  }
  return new Date(now.getTime() + (PRESET_HOURS[preset] ?? 24) * 3_600_000).toISOString()
}
