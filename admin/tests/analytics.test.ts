import { describe, expect, it } from 'vitest'
import { biggestDrop, bucketLabel, cellBounds, funnelRows, heatRectangles, retentionRate } from '../app/utils/analytics'

describe('product analytics', () => {
  it('computes funnel shares and the biggest drop', () => {
    const rows = funnelRows([
      { step: 'signup', users: 100 },
      { step: 'first_request', users: 60 },
      { step: 'first_ride', users: 15 },
    ])
    expect(rows.map(r => r.ofFirst)).toEqual([1, 0.6, 0.15])
    expect(rows[1]!.ofPrevious).toBe(0.6)
    expect(rows[2]!.lost).toBe(45)
    expect(biggestDrop(rows)?.step).toBe('first_ride')
    expect(funnelRows([{ step: 'a', users: 0 }, { step: 'b', users: 0 }])[1]).toMatchObject({ ofFirst: null, ofPrevious: null, lost: 0 })
    expect(biggestDrop(funnelRows([{ step: 'a', users: 5 }, { step: 'b', users: 5 }]))).toBeNull()
  })

  it('leaves weeks that are not over without a rate', () => {
    expect(retentionRate(10, 4)).toBe(0.4)
    expect(retentionRate(10, null)).toBeNull()
    expect(retentionRate(0, 0)).toBeNull()
  })

  it('draws cells as heat map squares', () => {
    expect(cellBounds('1049:-6688')).toEqual([[10.49, -66.88], [10.5, -66.87]])
    expect(cellBounds('x')).toBeNull()
    const cells = [
      { cell: '1049:-6688', lat: 10.495, lng: -66.875, requests: 4, no_drivers: 2, quotes: 0, driver_hours: 0 },
      { cell: '1050:-6688', lat: 10.505, lng: -66.875, requests: 1, no_drivers: 0, quotes: 3, driver_hours: 1 },
    ]
    const squares = heatRectangles(cells, 'no_drivers', c => c.cell)
    expect(squares).toHaveLength(1)
    expect(squares[0]).toMatchObject({ id: '1049:-6688', solid: true, label: '1049:-6688' })
    expect(heatRectangles(cells, 'requests', c => c.cell).map(r => r.fillOpacity)).toEqual([0.75, 0.3])
    expect(heatRectangles([], 'quotes', c => c.cell)).toEqual([])
  })

  it('labels buckets', () => {
    expect(bucketLabel({ min: 0, max: 10, count: 1 })).toBe('0–10')
    expect(bucketLabel({ min: 400, max: null, count: 1 }, n => `$${n}`)).toBe('$400+')
  })
})
