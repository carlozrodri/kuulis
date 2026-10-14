import type { CancelSide, CancellationCount, QualityLevel, QualityPause } from '~/types/api'
import { CANCEL_SIDES } from '~/types/api'

type BadgeColor = 'neutral' | 'info' | 'success' | 'error' | 'warning' | 'primary'

/** Doc 15: from fine to worst. "Revisar" is the one that needs someone to look. */
export const qualityLevelBadge: Record<QualityLevel, { color: BadgeColor, variant: 'subtle' | 'solid' }> = {
  ok: { color: 'success', variant: 'subtle' },
  warn: { color: 'warning', variant: 'subtle' },
  low_priority: { color: 'error', variant: 'subtle' },
  review: { color: 'error', variant: 'solid' },
}

/** Unknown levels (a newer API) render as neutral badges instead of breaking the page. */
export function qualityBadge(level: string): { color: BadgeColor, variant: 'subtle' | 'solid' } {
  return qualityLevelBadge[level as QualityLevel] ?? { color: 'neutral', variant: 'subtle' }
}

/** i18n key of a cancellation reason; null (an old ride or no reason given) has its own label. */
export function cancelReasonKey(code: string | null | undefined): string {
  return `quality.reasonCodes.${code ?? 'none'}`
}

/** An automatic pause still running (not lifted by an admin and not over). */
export function isPauseActive(pause: Pick<QualityPause, 'until' | 'lifted_at'>, now: number = Date.now()): boolean {
  return !pause.lifted_at && Date.parse(pause.until) > now
}

export interface CancellationGroup {
  side: CancelSide
  /** Most frequent reason first. */
  rows: CancellationCount[]
  total: number
  counted: number
  reassigned: number
}

/** Cancellations by reason, per side (passenger first) with the side's totals; sides without any are left out. */
export function groupCancellations(rows: CancellationCount[]): CancellationGroup[] {
  return CANCEL_SIDES.flatMap((side) => {
    const own = rows.filter(r => r.side === side).sort((a, b) => b.total - a.total)
    if (!own.length) return []
    const sum = (key: 'total' | 'counted' | 'reassigned') => own.reduce((n, r) => n + r[key], 0)
    return [{ side, rows: own, total: sum('total'), counted: sum('counted'), reassigned: sum('reassigned') }]
  })
}

/** Share of the side's cancellations (0..1), for the bar behind each reason. */
export function shareOf(part: number, total: number): number {
  return total > 0 ? part / total : 0
}
