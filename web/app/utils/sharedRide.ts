/**
 * The live ride page `/v/{token}` (doc 11): types of `GET /public/rides/shared/{token}` and the small helpers the
 * page needs (a static map from OpenStreetMap tiles, so no map library is shipped to cheap phones).
 */

export interface LatLng {
  lat: number
  lng: number
}

export interface SharedPerson {
  first_name: string
  photo_url: string | null
  rating: number | null
}

export type SharedRideStatus
  = | 'searching'
    | 'driver_assigned'
    | 'driver_arrived'
    | 'in_progress'
    | 'completed'
    | 'cancelled_by_passenger'
    | 'cancelled_by_driver'
    | 'cancelled_by_admin'
    | 'no_drivers'

export interface SharedRide {
  status: SharedRideStatus
  pickup: LatLng & { address: string }
  dropoff: LatLng & { address: string }
  polyline: string | null
  passenger: SharedPerson
  driver: SharedPerson | null
  vehicle: { brand: string, model: string, color: string, plate: string } | null
  driver_location: (LatLng & { heading: number | null }) | null
  started_at: string | null
  eta: string | null
  sos: boolean
  sos_location: LatLng | null
  updated_at: string
  /** Doc 23: the link was sent to the person riding (the ride was requested for them). */
  for_rider?: boolean
  /** Start PIN to tell the driver, until the ride starts (only on links for the person riding). */
  start_pin?: string | null
}

/** How often the page asks for the position again. */
export const SHARED_RIDE_POLL_MS = 5000

const ACTIVE: SharedRideStatus[] = ['searching', 'driver_assigned', 'driver_arrived', 'in_progress']

export const isActiveStatus = (status: SharedRideStatus) => ACTIVE.includes(status)

/** Where to centre the map: the SOS position, then the moto, then the leg the ride is on. */
export function focusPoint(ride: SharedRide): LatLng {
  if (ride.sos && ride.sos_location) return ride.sos_location
  if (ride.driver_location) return ride.driver_location
  return ride.status === 'in_progress' ? ride.dropoff : ride.pickup
}

/** "AB1 23CD", as on the app. */
export function formatPlate(plate: string | null | undefined): string {
  const clean = (plate ?? '').toUpperCase().replace(/[^A-Z0-9]/g, '')
  return clean.length < 6 ? clean : `${clean.slice(0, 3)} ${clean.slice(3)}`
}

/** "Sambil" from "Sambil, Chacao, Caracas". */
export const shortAddress = (address: string) => address.split(',')[0]?.trim() || address

/** "7:45 p. m." in Caracas time (where every ride happens). */
export function formatClock(iso: string, locale: string): string {
  return new Intl.DateTimeFormat(locale === 'en' ? 'en-US' : 'es-VE', {
    hour: 'numeric',
    minute: '2-digit',
    timeZone: 'America/Caracas',
  }).format(new Date(iso))
}

export const googleMapsUrl = (point: LatLng) => `https://www.google.com/maps/search/?api=1&query=${point.lat},${point.lng}`

// ── Static map ──

export const TILE_SIZE = 256
export const MAP_ZOOM = 16

/** Web-Mercator position in pixels at `zoom` (what OSM tiles use). */
export function toPixel(point: LatLng, zoom = MAP_ZOOM): { x: number, y: number } {
  const scale = TILE_SIZE * 2 ** zoom
  const sin = Math.sin((point.lat * Math.PI) / 180)
  return {
    x: ((point.lng + 180) / 360) * scale,
    y: (0.5 - Math.log((1 + sin) / (1 - sin)) / (4 * Math.PI)) * scale,
  }
}

export interface MapTile {
  url: string
  /** Offset from the map's centre, in pixels. */
  left: number
  top: number
}

export const OSM_TILES = 'https://tile.openstreetmap.org/{z}/{x}/{y}.png'

/**
 * The tiles around `center` (a `size`×`size` grid) positioned so `center` sits in the middle. OSM's servers
 * refuse tiles requested without a Referer, so the page sends its origin (never the path with the token).
 */
export function tilesAround(center: LatLng, template = OSM_TILES, size = 3, zoom = MAP_ZOOM): MapTile[] {
  const { x, y } = toPixel(center, zoom)
  const cx = Math.floor(x / TILE_SIZE)
  const cy = Math.floor(y / TILE_SIZE)
  const half = Math.floor(size / 2)
  const max = 2 ** zoom
  const tiles: MapTile[] = []
  for (let dy = -half; dy <= half; dy++) {
    for (let dx = -half; dx <= half; dx++) {
      const tx = (((cx + dx) % max) + max) % max
      const ty = cy + dy
      if (ty < 0 || ty >= max) continue
      tiles.push({
        url: template.replace('{z}', String(zoom)).replace('{x}', String(tx)).replace('{y}', String(ty)),
        left: (cx + dx) * TILE_SIZE - x,
        top: ty * TILE_SIZE - y,
      })
    }
  }
  return tiles
}

/** Where `point` falls relative to the map's centre, in pixels (for markers). */
export function offsetFrom(center: LatLng, point: LatLng, zoom = MAP_ZOOM): { left: number, top: number } {
  const a = toPixel(center, zoom)
  const b = toPixel(point, zoom)
  return { left: b.x - a.x, top: b.y - a.y }
}
