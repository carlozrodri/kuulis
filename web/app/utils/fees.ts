import type { FeeTier } from './types'

/** The highest monthly fee in the tiers (the cap quoted on the home page), or null without tiers. */
export function maxFee(tiers: FeeTier[] | undefined | null): number | null {
  if (!tiers?.length) return null
  return Math.max(...tiers.map(tier => Number(tier.fee)))
}

/** The monthly fee for some earnings, as the API charges it (api/apps/subscriptions/services.py `fee_for`): the
 * fee of the highest tier whose `above` the earnings exceed; nothing without earnings. */
export function feeFor(tiers: FeeTier[], earnings: number): number {
  if (earnings <= 0) return 0
  let fee = 0
  for (const tier of [...tiers].sort((a, b) => Number(a.above) - Number(b.above))) {
    if (earnings > Number(tier.above)) fee = Number(tier.fee)
  }
  return fee
}
