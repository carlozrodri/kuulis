import { describe, expect, it } from 'vitest'
import type { ClosingDifferences } from '../app/types/api'
import { closableMonths, closingBadge, differenceCount, reconcileState, simulationRows, waiveFeeIssue, waivePayload } from '../app/utils/finance'

const differences = (overrides: Partial<ClosingDifferences> = {}): ClosingDifferences => ({
  statement_rows: 2,
  statement_total: '30.00',
  kuulis_rows: 2,
  kuulis_total: '30.00',
  matched: 2,
  missing_in_kuulis: [],
  missing_in_binance: [],
  amount_mismatch: [],
  ...overrides,
})

describe('closings', () => {
  it('offers the months after the latest closing, up to last month', () => {
    expect(closableMonths(['2026-07', '2026-08'], '2026-10')).toEqual(['2026-09'])
    expect(closableMonths(['2026-09'], '2026-10')).toEqual([])
    expect(closableMonths(['2026-06'], '2026-10')).toEqual(['2026-09', '2026-08', '2026-07'])
  })

  it('offers the last months when nothing is closed yet', () => {
    expect(closableMonths([], '2026-01', 3)).toEqual(['2025-12', '2025-11', '2025-10'])
  })

  it('counts the differences of the three lists', () => {
    expect(differenceCount(null)).toBe(0)
    expect(differenceCount(differences({
      missing_in_kuulis: [{ id: 'a', amount: '5.00', at: null }],
      amount_mismatch: [{ top_up_id: 't', id: 'b', amount: '5.00', status: 'completed', binance_amount: '4.00' }],
    }))).toBe(2)
  })

  it('needs the statement, and a note when there are differences', () => {
    const base = { reconciled_at: null, differences: null, has_differences: false }
    expect(reconcileState(base)).toBe('needsStatement')
    expect(reconcileState({ ...base, differences: differences() })).toBe('ready')
    const differing = { ...base, differences: differences({ missing_in_kuulis: [{ id: 'a', amount: '1.00', at: null }] }), has_differences: true }
    expect(reconcileState(differing)).toBe('needsNote')
    expect(reconcileState(differing, '  ')).toBe('needsNote')
    expect(reconcileState(differing, 'Pago duplicado devuelto')).toBe('ready')
    expect(reconcileState({ ...differing, reconciled_at: '2026-10-02T00:00:00Z' })).toBe('reconciled')
  })

  it('flags a tampered closing before anything else', () => {
    expect(closingBadge({ hash_ok: false, reconciled_at: '2026-10-02T00:00:00Z', differences: null, has_differences: false }).key).toBe('tampered')
    expect(closingBadge({ hash_ok: true, reconciled_at: null, differences: null, has_differences: false }).key).toBe('noStatement')
    expect(closingBadge({ hash_ok: true, reconciled_at: null, differences: differences(), has_differences: true }).key).toBe('differences')
    expect(closingBadge({ hash_ok: true, reconciled_at: null, differences: differences(), has_differences: false }).key).toBe('matched')
  })
})

describe('fee waivers', () => {
  it('accepts waiving (empty or 0) and lowering, not raising', () => {
    const charge = { fee: '10.00' }
    expect(waiveFeeIssue(null, charge)).toBeNull()
    expect(waiveFeeIssue(0, charge)).toBeNull()
    expect(waiveFeeIssue(5, charge)).toBeNull()
    expect(waiveFeeIssue(10, charge)).toBe('notLower')
    expect(waiveFeeIssue(12, charge)).toBe('notLower')
    expect(waiveFeeIssue(-1, charge)).toBe('fee')
  })

  it('sends the fee with two decimals and a trimmed reason', () => {
    expect(waivePayload('  ganancia mal contada ', null)).toEqual({ reason: 'ganancia mal contada', fee: '0.00' })
    expect(waivePayload('x', 7.5)).toEqual({ reason: 'x', fee: '7.50' })
  })
})

describe('tier simulator', () => {
  it('lines up current and proposed tiers by threshold', () => {
    const rows = simulationRows({
      current: [
        { above: '0.00', fee: '0.00', drivers: 3, total: '0.00' },
        { above: '100.00', fee: '5.00', drivers: 2, total: '10.00' },
      ],
      proposed: [
        { above: '0.00', fee: '0.00', drivers: 3, total: '0.00' },
        { above: '150.00', fee: '6.00', drivers: 1, total: '6.00' },
      ],
    })
    expect(rows.map(r => r.above)).toEqual([0, 100, 150])
    expect(rows[1]!.proposed).toBeNull()
    expect(rows[2]!.current).toBeNull()
    expect(rows[2]!.proposed?.total).toBe('6.00')
  })
})
