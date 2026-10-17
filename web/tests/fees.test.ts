import { describe, expect, it } from 'vitest'
import { maxFee } from '../app/utils/fees'

describe('maxFee', () => {
  it('is the highest tier fee', () => {
    expect(maxFee([{ above: '0.00', fee: '0.00' }, { above: '600.00', fee: '30.00' }, { above: '100.00', fee: '5.00' }])).toBe(30)
  })

  it('is null without tiers, so the text leaves the figure out', () => {
    expect(maxFee([])).toBeNull()
    expect(maxFee(null)).toBeNull()
  })
})
