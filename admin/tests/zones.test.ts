import { describe, expect, it } from 'vitest'
import type { Coord, Zone } from '../app/types/api'
import { boxPolygon, defaultZoneForm, errorDetailLines, insertVertex, polygonSelfIntersects, validateZone, zoneFormFrom, zonePayload, zoneStatus } from '../app/utils/zones'

const NOW = Date.parse('2026-10-17T12:00:00Z')
const SQUARE: Coord[] = [[10.5, -66.9], [10.5, -66.8], [10.4, -66.8], [10.4, -66.9]]

const zone = (over: Partial<Zone> = {}): Zone => ({
  id: 'z1',
  kind: 'surge',
  name: 'Altamira',
  city: 'Caracas',
  polygon: SQUARE,
  active: true,
  starts_at: null,
  ends_at: null,
  rules: { multiplier: '1.30', days: [4, 5], start: '18:00', end: '23:00' },
  created_at: '2026-10-01T00:00:00Z',
  updated_at: '2026-10-01T00:00:00Z',
  ...over,
})

describe('zones (doc 21)', () => {
  it('tells whether a zone is in force', () => {
    expect(zoneStatus(zone(), NOW)).toBe('inForce')
    expect(zoneStatus(zone({ active: false }), NOW)).toBe('inactive')
    expect(zoneStatus(zone({ starts_at: '2026-10-18T00:00:00Z' }), NOW)).toBe('scheduled')
    expect(zoneStatus(zone({ ends_at: '2026-10-17T12:00:00Z' }), NOW)).toBe('expired')
    expect(zoneStatus(zone({ starts_at: '2026-10-17T12:00:00Z', ends_at: '2026-10-18T00:00:00Z' }), NOW)).toBe('inForce')
  })

  it('turns a city box into four corners', () => {
    expect(boxPolygon({ min_lat: 10.4, max_lat: 10.5, min_lng: -66.9, max_lng: -66.8 })).toEqual(SQUARE)
  })

  it('adds a vertex on the nearest edge', () => {
    expect(insertVertex([[0, 0], [0, 1]], [1, 1])).toEqual([[0, 0], [0, 1], [1, 1]])
    // Just outside the right edge (between the 2nd and 3rd vertex).
    const next = insertVertex(SQUARE, [10.45, -66.79])
    expect(next[2]).toEqual([10.45, -66.79])
    expect(next).toHaveLength(5)
    expect(polygonSelfIntersects(next)).toBe(false)
  })

  it('detects crossing edges', () => {
    expect(polygonSelfIntersects(SQUARE)).toBe(false)
    expect(polygonSelfIntersects([[0, 0], [1, 1], [0, 1], [1, 0]])).toBe(true)
    expect(polygonSelfIntersects([[0, 0], [0, 1], [1, 1]])).toBe(false)
  })

  it('round-trips a zone through the form and sends only the rules of its kind', () => {
    const form = zoneFormFrom(zone())
    expect(form.multiplier).toBe(1.3)
    expect(validateZone(form)).toEqual([])
    const payload = zonePayload(form)
    expect(payload.rules).toEqual({ multiplier: '1.30', days: [4, 5], start: '18:00', end: '23:00' })
    expect(payload.starts_at).toBeNull()

    form.kind = 'pickup'
    form.points = [{ name: ' Metro Altamira ', lat: 10.49, lng: -66.85 }]
    expect(zonePayload(form).rules).toEqual({ points: [{ name: 'Metro Altamira', lat: 10.49, lng: -66.85 }] })

    form.kind = 'restricted'
    expect(Object.keys(zonePayload(form).rules).sort()).toEqual(['dropoff', 'message', 'pickup', 'points'])
  })

  it('validates the form', () => {
    const form = defaultZoneForm('', 'pickup')
    expect(validateZone(form)).toEqual(['name', 'city', 'polygonShort', 'pointsNone'])
    Object.assign(form, { kind: 'surge', name: 'X', city: 'Caracas', polygon: [[0, 0], [1, 1], [0, 1], [1, 0]], multiplier: 4, start: '10:00' })
    expect(validateZone(form)).toEqual(['polygonCrosses', 'multiplier', 'hoursBoth'])
    Object.assign(form, { kind: 'restricted', polygon: SQUARE, pickup: false, dropoff: false, points: [{ name: '', lat: 0, lng: 0 }] })
    expect(validateZone(form)).toEqual(['restrictNothing', 'pointName'])
  })

  it('reads error details', () => {
    expect(errorDetailLines(undefined)).toEqual([])
    expect(errorDetailLines('self-intersection')).toEqual(['self-intersection'])
    expect(errorDetailLines([{ loc: ['body', 'polygon'], msg: 'too short' }])).toEqual(['polygon: too short'])
    expect(errorDetailLines({ polygon: 'crosses itself', city: ['unknown'] })).toEqual(['polygon: crosses itself', 'city: unknown'])
    expect(errorDetailLines([{ index: 2, reason: 'no geometry' }])).toEqual(['#2: no geometry'])
  })
})
