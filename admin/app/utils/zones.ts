import type { Coord, DemandLevel, Localized, Zone, ZoneCity, ZoneKind, ZonePoint, ZoneRules, ZoneWrite } from '~/types/api'
import { fromLocalInput, toLocalInput } from '~/utils/promotions'

// Doc 21 (docs/api/zonas.md): zones drawn on the map with rules per kind, city polygons and the demand cells.

export const ZONE_COLORS: Record<ZoneKind | 'city', string> = {
  city: '#0e7c5a',
  surge: '#d97706',
  restricted: '#dc2626',
  pickup: '#2563eb',
}

/** Demand cells: 1 = some demand, 2 = demand, 3 = high demand. */
export const DEMAND_COLORS: Record<DemandLevel, string> = {
  1: '#facc15',
  2: '#f97316',
  3: '#dc2626',
}

export const ZONE_VERTICES_MAX = 300
export const ZONE_POINTS_MAX = 20
export const ZONE_NAME_MAX = 80
export const SURGE_ZONE_MIN = 1
export const SURGE_ZONE_MAX = 3

export type ZoneStatus = 'inForce' | 'inactive' | 'scheduled' | 'expired'

/** Whether a zone counts now: active and inside its validity (null ends do not limit). */
export function zoneStatus(zone: Pick<Zone, 'active' | 'starts_at' | 'ends_at'>, now: number = Date.now()): ZoneStatus {
  if (!zone.active) return 'inactive'
  if (zone.starts_at && Date.parse(zone.starts_at) > now) return 'scheduled'
  if (zone.ends_at && Date.parse(zone.ends_at) <= now) return 'expired'
  return 'inForce'
}

/** The four corners of a city box, to start a polygon from it. */
export function boxPolygon(city: Pick<ZoneCity, 'min_lat' | 'max_lat' | 'min_lng' | 'max_lng'>): Coord[] {
  return [
    [city.max_lat, city.min_lng],
    [city.max_lat, city.max_lng],
    [city.min_lat, city.max_lng],
    [city.min_lat, city.min_lng],
  ]
}

const distance = (a: Coord, b: Coord) => Math.hypot(a[0] - b[0], a[1] - b[1])

/**
 * Adds a vertex where it bends the outline least: in the edge whose detour through the point is
 * shortest. Clicking near an edge of an existing polygon adds the vertex to that edge.
 */
export function insertVertex(points: Coord[], point: Coord): Coord[] {
  if (points.length < 3) return [...points, point]
  let best = points.length
  let bestCost = Infinity
  points.forEach((a, i) => {
    const b = points[(i + 1) % points.length]!
    const cost = distance(a, point) + distance(point, b) - distance(a, b)
    if (cost < bestCost) {
      bestCost = cost
      best = i + 1
    }
  })
  return [...points.slice(0, best), point, ...points.slice(best)]
}

function orientation(p: Coord, q: Coord, r: Coord): number {
  const value = (q[1] - p[1]) * (r[0] - q[0]) - (q[0] - p[0]) * (r[1] - q[1])
  return Math.abs(value) < 1e-15 ? 0 : value > 0 ? 1 : 2
}

const onSegment = (p: Coord, q: Coord, r: Coord) =>
  Math.min(p[0], r[0]) <= q[0] && q[0] <= Math.max(p[0], r[0]) && Math.min(p[1], r[1]) <= q[1] && q[1] <= Math.max(p[1], r[1])

function segmentsIntersect(p1: Coord, q1: Coord, p2: Coord, q2: Coord): boolean {
  const o1 = orientation(p1, q1, p2)
  const o2 = orientation(p1, q1, q2)
  const o3 = orientation(p2, q2, p1)
  const o4 = orientation(p2, q2, q1)
  if (o1 !== o2 && o3 !== o4) return true
  return (o1 === 0 && onSegment(p1, p2, q1)) || (o2 === 0 && onSegment(p1, q2, q1))
    || (o3 === 0 && onSegment(p2, p1, q2)) || (o4 === 0 && onSegment(p2, q1, q2))
}

/** A polygon whose edges cross (the API rejects it with zone_invalid). */
export function polygonSelfIntersects(points: Coord[]): boolean {
  const n = points.length
  if (n < 4) return false
  for (let i = 0; i < n; i++) {
    for (let j = i + 1; j < n; j++) {
      // Edges that share a vertex always touch.
      if (j === i + 1 || (i === 0 && j === n - 1)) continue
      if (segmentsIntersect(points[i]!, points[(i + 1) % n]!, points[j]!, points[(j + 1) % n]!)) return true
    }
  }
  return false
}

// ---- Form ---------------------------------------------------------------------------------------

export interface ZoneForm {
  name: string
  kind: ZoneKind
  city: string
  polygon: Coord[]
  active: boolean
  /** `datetime-local` values, browser time ("" = no limit). */
  starts_at: string
  ends_at: string
  multiplier: number
  days: number[]
  /** "HH:MM", "" = all day. */
  start: string
  end: string
  pickup: boolean
  dropoff: boolean
  message: Localized
  points: ZonePoint[]
}

export function defaultZoneForm(city = '', kind: ZoneKind = 'surge'): ZoneForm {
  return {
    name: '',
    kind,
    city,
    polygon: [],
    active: true,
    starts_at: '',
    ends_at: '',
    multiplier: 1.2,
    days: [],
    start: '',
    end: '',
    pickup: true,
    dropoff: true,
    message: { es: '', en: '' },
    points: [],
  }
}

export function zoneFormFrom(zone: Zone): ZoneForm {
  const rules: ZoneRules = zone.rules ?? {}
  const d = defaultZoneForm(zone.city, zone.kind)
  const multiplier = Number(rules.multiplier)
  return {
    ...d,
    name: zone.name,
    polygon: zone.polygon.map(([lat, lng]) => [lat, lng]),
    active: zone.active,
    starts_at: toLocalInput(zone.starts_at),
    ends_at: toLocalInput(zone.ends_at),
    multiplier: Number.isFinite(multiplier) && multiplier > 0 ? multiplier : d.multiplier,
    days: [...(rules.days ?? [])],
    start: rules.start ?? '',
    end: rules.end ?? '',
    pickup: rules.pickup ?? d.pickup,
    dropoff: rules.dropoff ?? d.dropoff,
    message: { es: rules.message?.es ?? '', en: rules.message?.en ?? '' },
    points: (rules.points ?? []).map(p => ({ ...p })),
  }
}

/** Only the rules of the zone's kind travel (the API ignores the rest). */
export function zonePayload(form: ZoneForm): ZoneWrite {
  const points = form.points.map(p => ({ name: p.name.trim(), lat: p.lat, lng: p.lng }))
  let rules: ZoneRules
  if (form.kind === 'surge') {
    rules = {
      multiplier: form.multiplier.toFixed(2),
      days: [...form.days].sort((a, b) => a - b),
      start: form.start || null,
      end: form.end || null,
    }
  }
  else if (form.kind === 'restricted') {
    rules = {
      pickup: form.pickup,
      dropoff: form.dropoff,
      message: { es: form.message.es.trim(), en: form.message.en.trim() },
      points,
    }
  }
  else {
    rules = { points }
  }
  return {
    kind: form.kind,
    name: form.name.trim(),
    city: form.city,
    polygon: form.polygon.map(([lat, lng]) => [lat, lng]),
    active: form.active,
    starts_at: fromLocalInput(form.starts_at),
    ends_at: fromLocalInput(form.ends_at),
    rules,
  }
}

const TIME = /^([01]\d|2[0-3]):[0-5]\d$/

/** Client-side checks mirroring the contract; the API validates again. i18n keys under zones.errors. */
export function validateZone(form: ZoneForm): string[] {
  const issues: string[] = []
  if (!form.name.trim()) issues.push('name')
  if (!form.city) issues.push('city')
  if (form.polygon.length < 3) issues.push('polygonShort')
  else if (form.polygon.length > ZONE_VERTICES_MAX) issues.push('polygonLong')
  else if (polygonSelfIntersects(form.polygon)) issues.push('polygonCrosses')
  const starts = fromLocalInput(form.starts_at)
  const ends = fromLocalInput(form.ends_at)
  if (starts && ends && ends <= starts) issues.push('dates')
  if (form.kind === 'surge') {
    if (!(form.multiplier >= SURGE_ZONE_MIN && form.multiplier <= SURGE_ZONE_MAX)) issues.push('multiplier')
    if (!!form.start !== !!form.end) issues.push('hoursBoth')
    else if (form.start && (!TIME.test(form.start) || !TIME.test(form.end))) issues.push('hours')
    else if (form.start && form.start === form.end) issues.push('hoursSame')
  }
  if (form.kind === 'restricted' && !form.pickup && !form.dropoff) issues.push('restrictNothing')
  if (form.kind === 'pickup' && !form.points.length) issues.push('pointsNone')
  if (form.kind !== 'surge') {
    if (form.points.length > ZONE_POINTS_MAX) issues.push('pointsMany')
    if (form.points.some(p => !p.name.trim())) issues.push('pointName')
  }
  return issues
}

// ---- Errors -------------------------------------------------------------------------------------

/**
 * Readable lines from the `details` of zone_invalid / geojson_invalid / a 422: a text, a list of texts or
 * of {loc, msg} / {index, reason} entries, or an object of field → problem.
 */
export function errorDetailLines(details: unknown): string[] {
  if (details === null || details === undefined || details === '') return []
  if (typeof details === 'string' || typeof details === 'number' || typeof details === 'boolean') return [String(details)]
  if (Array.isArray(details)) return details.flatMap(item => errorDetailLines(item))
  if (typeof details !== 'object') return []
  const entry = details as Record<string, unknown>
  const text = entry.msg ?? entry.message ?? entry.reason
  if (typeof text === 'string') {
    const where = Array.isArray(entry.loc)
      ? entry.loc.filter(part => part !== 'body').join('.')
      : entry.index !== undefined
        ? `#${String(entry.index)}`
        : typeof entry.field === 'string' ? entry.field : ''
    return [where ? `${where}: ${text}` : text]
  }
  return Object.entries(entry).flatMap(([key, value]) => errorDetailLines(value).map(line => `${key}: ${line}`))
}

/** File name of the GeoJSON export, with the day it was taken. */
export function exportFileName(now: Date = new Date()): string {
  return `kuulis-zonas-${toLocalInput(now).slice(0, 10)}.geojson`
}
