import type { Charge, Closing, ClosingDifferences, Month, Simulation, TierCount } from '~/types/api'
import { addMonths, monthsBack } from '~/utils/wallet'

/** Limits from the contract (the API validates again). */
export const RECONCILE_NOTE_MAX = 500
export const STATEMENT_MAX_CHARS = 3_000_000
export const WAIVE_REASON_MAX = 500

/**
 * Months that may be closed now, newest first. Closings go in order: after the latest one only the months up to
 * last month (closing a later month first would leave a gap). With no closing yet, the last `count` months.
 */
export function closableMonths(closed: Month[], current: Month, count = 12): Month[] {
  const lastMonth = addMonths(current, -1)
  const latest = [...closed].sort().at(-1)
  if (!latest) return monthsBack(lastMonth, count)
  const months: Month[] = []
  for (let m = addMonths(latest, 1); m < current && months.length < count; m = addMonths(m, 1)) months.unshift(m)
  return months
}

/** How many rows differ between the Binance statement and Kuulis. */
export function differenceCount(differences: ClosingDifferences | null | undefined): number {
  if (!differences) return 0
  return (differences.missing_in_kuulis?.length ?? 0)
    + (differences.missing_in_binance?.length ?? 0)
    + (differences.amount_mismatch?.length ?? 0)
}

export type ReconcileState = 'reconciled' | 'needsStatement' | 'needsNote' | 'ready'

/**
 * What marking a closing as reconciled still needs: the Binance statement first, and a note explaining the
 * differences when there are any.
 */
export function reconcileState(closing: Pick<Closing, 'reconciled_at' | 'differences' | 'has_differences'>, note = ''): ReconcileState {
  if (closing.reconciled_at) return 'reconciled'
  if (!closing.differences) return 'needsStatement'
  const differs = closing.has_differences || differenceCount(closing.differences) > 0
  if (differs && !note.trim()) return 'needsNote'
  return 'ready'
}

type BadgeColor = 'neutral' | 'info' | 'success' | 'error' | 'warning' | 'primary'

/** Badge for the closing's state in the list: tampered, reconciled, with differences, waiting for the statement. */
export function closingBadge(closing: Pick<Closing, 'hash_ok' | 'reconciled_at' | 'differences' | 'has_differences'>): { key: string, color: BadgeColor } {
  if (!closing.hash_ok) return { key: 'tampered', color: 'error' }
  if (closing.reconciled_at) return { key: 'reconciled', color: 'success' }
  if (!closing.differences) return { key: 'noStatement', color: 'neutral' }
  if (closing.has_differences || differenceCount(closing.differences) > 0) return { key: 'differences', color: 'warning' }
  return { key: 'matched', color: 'info' }
}

// ---- Waive or lower a fee ----------------------------------------------------------------------

/**
 * Checks the new fee of a waiver: empty or 0 waives it, otherwise it must be lower than the current fee.
 * Returns an i18n key under subscriptions.waive.errors, or null.
 */
export function waiveFeeIssue(newFee: number | null | undefined, charge: Pick<Charge, 'fee'>): 'fee' | 'notLower' | null {
  if (newFee === null || newFee === undefined) return null
  if (!Number.isFinite(newFee) || newFee < 0) return 'fee'
  const current = Number(charge.fee)
  if (newFee > 0 && Number.isFinite(current) && Math.round(newFee * 100) >= Math.round(current * 100)) return 'notLower'
  return null
}

export function waivePayload(reason: string, newFee: number | null | undefined): { reason: string, fee: string } {
  const fee = newFee !== null && newFee !== undefined && Number.isFinite(newFee) && newFee > 0 ? newFee : 0
  return { reason: reason.trim(), fee: fee.toFixed(2) }
}

// ---- Tier simulator ----------------------------------------------------------------------------

export interface SimulationRow {
  above: number
  current: TierCount | null
  proposed: TierCount | null
}

/**
 * Current and proposed tiers side by side, one row per "above" threshold found in either (sorted). A threshold
 * that only one side has shows an empty cell on the other.
 */
export function simulationRows(sim: Pick<Simulation, 'current' | 'proposed'>): SimulationRow[] {
  const rows = new Map<number, SimulationRow>()
  const row = (above: number) => {
    if (!rows.has(above)) rows.set(above, { above, current: null, proposed: null })
    return rows.get(above)!
  }
  for (const tier of sim.current) row(Math.round(Number(tier.above) * 100) / 100).current = tier
  for (const tier of sim.proposed) row(Math.round(Number(tier.above) * 100) / 100).proposed = tier
  return [...rows.values()].sort((a, b) => a.above - b.above)
}
