export type LatLng = [number, number]

export interface MapMarker {
  id: string
  lat: number
  lng: number
  color: string
  /** Plain text, rendered with textContent (never as HTML). */
  label?: string
  radius?: number
  /** Hollow circles for secondary points (e.g. the drop-off of a live ride). */
  hollow?: boolean
}

export interface MapLine {
  id: string
  points: LatLng[]
  color: string
  dashed?: boolean
}

export interface MapRectangle {
  id: string
  bounds: [LatLng, LatLng]
  color: string
}

/** Caracas centre, used when there is nothing to fit the map to. */
export const CARACAS_CENTER: LatLng = [10.4806, -66.9036]

/** Decodes an encoded polyline (Google/OSRM format). OSRM uses precision 5 by default. */
export function decodePolyline(encoded: string, precision = 5): LatLng[] {
  const factor = 10 ** precision
  const points: LatLng[] = []
  let index = 0
  let lat = 0
  let lng = 0
  while (index < encoded.length) {
    for (const axis of [0, 1]) {
      let result = 0
      let shift = 0
      let byte: number
      do {
        byte = encoded.charCodeAt(index++) - 63
        result |= (byte & 0x1f) << shift
        shift += 5
      } while (byte >= 0x20 && index < encoded.length)
      const delta = result & 1 ? ~(result >> 1) : result >> 1
      if (axis === 0) lat += delta
      else lng += delta
    }
    points.push([lat / factor, lng / factor])
  }
  return points
}

/**
 * Decodes a route polyline, trying precision 6 when precision 5 lands outside valid coordinates
 * (polyline6 decoded as polyline5 yields values ten times too large).
 */
export function decodeRoute(encoded: string | null | undefined): LatLng[] {
  if (!encoded) return []
  try {
    const p5 = decodePolyline(encoded, 5)
    if (p5.every(([a, b]) => Math.abs(a) <= 90 && Math.abs(b) <= 180)) return p5
    return decodePolyline(encoded, 6)
  }
  catch {
    return []
  }
}
