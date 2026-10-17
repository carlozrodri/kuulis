import { describe, expect, it } from 'vitest'
import { feeFor, maxFee } from '../app/utils/fees'

const TIERS = [
  { above: '0.00', fee: '0.00' },
  { above: '600.00', fee: '30.00' },
  { above: '100.00', fee: '5.00' },
  { above: '200.00', fee: '10.00' },
]

describe('maxFee', () => {
  it('is the highest tier fee', () => {
    expect(maxFee(TIERS)).toBe(30)
  })

  it('is null without tiers, so the text leaves the figure out', () => {
    expect(maxFee([])).toBeNull()
    expect(maxFee(null)).toBeNull()
  })
})

describe('feeFor', () => {
  it('charges the highest tier the earnings exceed, like the API', () => {
    expect(feeFor(TIERS, 250)).toBe(10)
    expect(feeFor(TIERS, 1000)).toBe(30)
    expect(feeFor(TIERS, 100.01)).toBe(5)
  })

  it('charges the lower tier at the exact boundary ("above", not "from")', () => {
    expect(feeFor(TIERS, 100)).toBe(0)
    expect(feeFor(TIERS, 200)).toBe(5)
  })

  it('charges nothing without earnings', () => {
    expect(feeFor(TIERS, 0)).toBe(0)
    expect(feeFor([], 500)).toBe(0)
  })
})
