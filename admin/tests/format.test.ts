import { describe, expect, it } from 'vitest'
import { ageFrom, formatPercent } from '~/utils/format'
import { decodePolyline, decodeRoute } from '~/utils/geo'

describe('format', () => {
  it('computes age on and around the birthday', () => {
    const today = new Date(2026, 9, 9)
    expect(ageFrom('2005-10-09', today)).toBe(21)
    expect(ageFrom('2005-10-10', today)).toBe(20)
    expect(ageFrom(null, today)).toBeNull()
    expect(ageFrom('garbage', today)).toBeNull()
  })

  it('formats missing values as a dash', () => {
    expect(formatPercent(null, 'es')).toBe('—')
    expect(formatPercent(Number.NaN, 'es')).toBe('—')
  })
})

describe('geo', () => {
  it('decodes the reference polyline', () => {
    // Example from Google's encoded polyline documentation.
    expect(decodePolyline('_p~iF~ps|U_ulLnnqC_mqNvxq`@')).toEqual([
      [38.5, -120.2],
      [40.7, -120.95],
      [43.252, -126.453],
    ])
  })

  it('returns no points for an empty or broken route', () => {
    expect(decodeRoute(null)).toEqual([])
    expect(decodeRoute('')).toEqual([])
  })
})
