import { type Coordinate, haversineMeters } from '@/lib/ride';

/**
 * Math for the live moto on the map (docs/product/wow/01-mapa-vivo.md, part A): the marker glides between
 * two GPS updates instead of jumping, and turns the shortest way towards where it is going.
 */

const rad = (deg: number) => (deg * Math.PI) / 180;

export function distanceM(a: Coordinate, b: Coordinate): number {
  return haversineMeters({ lat: a.latitude, lng: a.longitude }, { lat: b.latitude, lng: b.longitude });
}

/** Compass bearing from `a` to `b`, 0‑360 (0 = north, 90 = east). */
export function bearing(a: Coordinate, b: Coordinate): number {
  const y = Math.sin(rad(b.longitude - a.longitude)) * Math.cos(rad(b.latitude));
  const x =
    Math.cos(rad(a.latitude)) * Math.sin(rad(b.latitude)) -
    Math.sin(rad(a.latitude)) * Math.cos(rad(b.latitude)) * Math.cos(rad(b.longitude - a.longitude));
  return ((Math.atan2(y, x) * 180) / Math.PI + 360) % 360;
}

/** Angle between `from` and `to` along the shortest turn, `t` in 0‑1. Result is 0‑360. */
export function lerpAngle(from: number, to: number, t: number): number {
  const delta = ((((to - from) % 360) + 540) % 360) - 180;
  return (from + delta * t + 360) % 360;
}

export function lerpCoordinate(a: Coordinate, b: Coordinate, t: number): Coordinate {
  return { latitude: a.latitude + (b.latitude - a.latitude) * t, longitude: a.longitude + (b.longitude - a.longitude) * t };
}

/** Below this the GPS is just jittering: keep the old rotation instead of spinning the moto in place. */
export const MIN_TURN_M = 8;
/** Above this it is a jump (lost signal, first fix): move at once instead of crossing the city. */
export const MAX_GLIDE_M = 600;

/**
 * Where the moto should face after moving from `from` to `to`: the GPS heading when the phone sends one,
 * else the direction of travel, else the previous rotation.
 */
export function nextRotation(from: Coordinate, to: Coordinate, heading: number | null | undefined, previous: number): number {
  if (heading != null && heading >= 0) return heading % 360;
  if (distanceM(from, to) >= MIN_TURN_M) return bearing(from, to);
  return previous;
}
