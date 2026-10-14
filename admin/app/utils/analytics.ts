import type { FunnelStep, SupplyCell, ValueBucket } from '~/types/api'
import type { LatLng, MapRectangle } from '~/utils/geo'

/** Product analytics pages (doc 19). */
export const ANALYTICS_TABS = ['funnels', 'retention', 'supply', 'promotions', 'drivers'] as const
export type AnalyticsTab = typeof ANALYTICS_TABS[number]

/** CSV report behind each tab (GET /admin/analytics/{report}.csv). */
export const ANALYTICS_REPORT: Record<AnalyticsTab, string> = {
  funnels: 'funnels',
  retention: 'retention',
  supply: 'supply-demand',
  promotions: 'promotions',
  drivers: 'drivers',
}

export const RETENTION_WEEKS = ['1', '2', '4', '8'] as const

export interface FunnelRow extends FunnelStep {
  /** Share of the first step (0-1). */
  ofFirst: number | null
  /** Share of the previous step (0-1); null on the first one. */
  ofPrevious: number | null
  /** People lost since the previous step. */
  lost: number
}

export function funnelRows(steps: FunnelStep[]): FunnelRow[] {
  const first = steps[0]?.users ?? 0
  return steps.map((s, i) => {
    const previous = i > 0 ? steps[i - 1]!.users : null
    return {
      ...s,
      ofFirst: first ? s.users / first : null,
      // Nothing to compare with on the first step or after an empty one.
      ofPrevious: previous ? s.users / previous : null,
      lost: previous !== null ? Math.max(0, previous - s.users) : 0,
    }
  })
}

/** The step where most people drop (the one that loses the largest share), for the "biggest drop" note. */
export function biggestDrop(rows: FunnelRow[]): FunnelRow | null {
  let worst: FunnelRow | null = null
  for (const row of rows.slice(1)) {
    if (row.ofPrevious === null || row.lost === 0) continue
    if (!worst || row.ofPrevious < (worst.ofPrevious ?? 1)) worst = row
  }
  return worst
}

/** Returned / cohort as 0-1, null when the week is not over yet or the cohort is empty. */
export function retentionRate(users: number, returned: number | null | undefined): number | null {
  if (returned === null || returned === undefined || !users) return null
  return returned / users
}

/** Tailwind-free cell background for a 0-1 rate (the stronger the better), readable in both themes. */
export function rateShade(rate: number | null): string | undefined {
  if (rate === null) return undefined
  const alpha = 0.08 + Math.min(1, Math.max(0, rate)) * 0.5
  return `color-mix(in srgb, var(--ui-primary) ${Math.round(alpha * 100)}%, transparent)`
}

export type SupplyMetric = 'no_drivers' | 'requests' | 'quotes' | 'driver_hours'

/** Cells are 0.01° squares named "<floor(lat*100)>:<floor(lng*100)>" (as the API and the app). */
export function cellBounds(cell: string): [LatLng, LatLng] | null {
  const [i, j] = cell.split(':').map(Number)
  if (!Number.isInteger(i) || !Number.isInteger(j)) return null
  return [[i! / 100, j! / 100], [(i! + 1) / 100, (j! + 1) / 100]]
}

const METRIC_COLOR: Record<SupplyMetric, string> = {
  no_drivers: '#dc2626',
  requests: '#2563eb',
  quotes: '#7c3aed',
  driver_hours: '#16a34a',
}

/** Heat map squares for one metric: opacity grows with the value (cells at 0 are left out). */
export function heatRectangles(cells: SupplyCell[], metric: SupplyMetric, label: (cell: SupplyCell) => string): MapRectangle[] {
  const max = Math.max(0, ...cells.map(c => c[metric]))
  if (!max) return []
  return cells.flatMap((c) => {
    const bounds = cellBounds(c.cell)
    if (!bounds || !c[metric]) return []
    return [{
      id: c.cell,
      bounds,
      color: METRIC_COLOR[metric],
      solid: true,
      fillOpacity: 0.15 + 0.6 * (c[metric] / max),
      label: label(c),
    }]
  })
}

/** "0–10", "400+" (or with a unit after each number). */
export function bucketLabel(bucket: ValueBucket, format: (n: number) => string = String): string {
  return bucket.max === null ? `${format(bucket.min)}+` : `${format(bucket.min)}–${format(bucket.max)}`
}
