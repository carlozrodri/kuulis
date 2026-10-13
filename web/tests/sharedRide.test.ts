import { describe, expect, it } from 'vitest'
import {
  focusPoint,
  formatPlate,
  isActiveStatus,
  offsetFrom,
  type SharedRide,
  shortAddress,
  TILE_SIZE,
  tilesAround,
  toPixel,
} from '../app/utils/sharedRide'

const ride = (overrides: Partial<SharedRide> = {}): SharedRide => ({
  status: 'in_progress',
  pickup: { lat: 10.5, lng: -66.9, address: 'Plaza Venezuela, Caracas' },
  dropoff: { lat: 10.49, lng: -66.85, address: 'Sambil, Chacao, Caracas' },
  polyline: null,
  passenger: { first_name: 'Ana', photo_url: null, rating: null },
  driver: null,
  vehicle: null,
  driver_location: null,
  started_at: null,
  eta: null,
  sos: false,
  sos_location: null,
  updated_at: '2026-10-13T12:00:00Z',
  ...overrides,
})

describe('shared ride', () => {
  it('centres on the SOS, then the moto, then the current leg', () => {
    expect(focusPoint(ride())).toEqual(ride().dropoff)
    expect(focusPoint(ride({ status: 'driver_assigned' }))).toEqual(ride().pickup)
    const moto = { lat: 10.495, lng: -66.87, heading: null }
    expect(focusPoint(ride({ driver_location: moto }))).toEqual(moto)
    const sos = { lat: 10.4, lng: -66.8 }
    expect(focusPoint(ride({ driver_location: moto, sos: true, sos_location: sos }))).toEqual(sos)
  })

  it('formats like the app', () => {
    expect(formatPlate('ab123cd')).toBe('AB1 23CD')
    expect(shortAddress('Sambil, Chacao, Caracas')).toBe('Sambil')
    expect(isActiveStatus('in_progress')).toBe(true)
    expect(isActiveStatus('completed')).toBe(false)
  })
})

describe('static map', () => {
  it('projects like OSM tiles', () => {
    expect(toPixel({ lat: 0, lng: 0 }, 0)).toEqual({ x: 128, y: 128 })
  })

  it('places a 3x3 grid around the centre', () => {
    const center = { lat: 10.4996, lng: -66.8826 }
    const tiles = tilesAround(center)
    expect(tiles).toHaveLength(9)
    expect(tiles.every(t => t.url.startsWith('https://tile.openstreetmap.org/16/'))).toBe(true)
    // The middle tile contains the centre (offset between -256 and 0 on both axes).
    const middle = tiles[4]!
    expect(middle.left).toBeLessThanOrEqual(0)
    expect(middle.left).toBeGreaterThan(-TILE_SIZE)
    expect(middle.top).toBeLessThanOrEqual(0)
    expect(middle.top).toBeGreaterThan(-TILE_SIZE)
  })

  it('offsets markers from the centre', () => {
    const center = { lat: 10.5, lng: -66.9 }
    expect(offsetFrom(center, center)).toEqual({ left: 0, top: 0 })
    const east = offsetFrom(center, { lat: 10.5, lng: -66.89 })
    expect(east.left).toBeGreaterThan(0)
    expect(Math.abs(east.top)).toBeLessThan(1e-6)
  })
})
