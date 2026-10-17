import type { FeeTier } from './types'

/** The highest monthly fee in the tiers (the cap quoted on the home page), or null without tiers. */
export function maxFee(tiers: FeeTier[] | undefined | null): number | null {
  if (!tiers?.length) return null
  return Math.max(...tiers.map(tier => Number(tier.fee)))
}
