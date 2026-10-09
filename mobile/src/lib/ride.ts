/**
 * Pure ride logic (no React, no network) so it can be unit tested.
 * Contract: docs/api/phase-1b.md.
 */
import type { LatLng, PaymentMethod, Ride, RideStatus } from './types';

// ── Coordinates ──

export type Coordinate = { latitude: number; longitude: number };

/** Caracas (Plaza Venezuela): default map centre until we know where the user is. */
export const CARACAS: Coordinate = { latitude: 10.4996, longitude: -66.8826 };

export const toCoordinate = (point: LatLng): Coordinate => ({ latitude: point.lat, longitude: point.lng });

const decodeWith = (encoded: string, precision: number): Coordinate[] => {
  const factor = 10 ** precision;
  const points: Coordinate[] = [];
  let index = 0;
  let lat = 0;
  let lng = 0;
  while (index < encoded.length) {
    for (const axis of [0, 1]) {
      let result = 0;
      let shift = 0;
      let byte: number;
      do {
        if (index >= encoded.length) return points;
        byte = encoded.charCodeAt(index++) - 63;
        result |= (byte & 0x1f) << shift;
        shift += 5;
      } while (byte >= 0x20);
      const delta = result & 1 ? ~(result >> 1) : result >> 1;
      if (axis === 0) lat += delta;
      else lng += delta;
    }
    points.push({ latitude: lat / factor, longitude: lng / factor });
  }
  return points;
};

/**
 * Decodes a Google encoded polyline (OSRM's `polyline` geometry, precision 5). If the result is not a valid
 * coordinate list it retries with precision 6 (`polyline6`), so either OSRM setting works.
 */
export function decodePolyline(encoded: string | null | undefined, precision?: 5 | 6): Coordinate[] {
  if (!encoded) return [];
  if (precision) return decodeWith(encoded, precision);
  const five = decodeWith(encoded, 5);
  const valid = five.every((p) => Math.abs(p.latitude) <= 90 && Math.abs(p.longitude) <= 180);
  return valid ? five : decodeWith(encoded, 6);
}

/** Great-circle distance in metres. */
export function haversineMeters(a: LatLng, b: LatLng): number {
  const rad = (deg: number) => (deg * Math.PI) / 180;
  const dLat = rad(b.lat - a.lat);
  const dLng = rad(b.lng - a.lng);
  const h = Math.sin(dLat / 2) ** 2 + Math.cos(rad(a.lat)) * Math.cos(rad(b.lat)) * Math.sin(dLng / 2) ** 2;
  return 2 * 6_371_000 * Math.asin(Math.min(1, Math.sqrt(h)));
}

/** Same fallback the API uses without OSRM: straight line × 1.3 at 22 km/h. */
export function estimateEtaSeconds(from: LatLng, to: LatLng): number {
  const metres = haversineMeters(from, to) * 1.3;
  return Math.round(metres / (22_000 / 3600));
}

// ── Formatting ──

/** "2.4" | "2.40" -> "$2.40". Amounts are USD decimal strings. */
export function formatFare(amount: string | number | null | undefined): string {
  const value = typeof amount === 'number' ? amount : Number.parseFloat(amount ?? '');
  if (!Number.isFinite(value)) return '$—';
  return `$${value.toFixed(2)}`;
}

/** 850 -> "850 m", 3240 -> "3.2 km" (decimal separator by locale). */
export function formatDistance(metres: number, locale = 'es'): string {
  if (!Number.isFinite(metres) || metres < 0) return '—';
  if (metres < 1000) return `${Math.max(10, Math.round(metres / 10) * 10)} m`;
  const km = metres / 1000;
  return `${km.toLocaleString(locale, { maximumFractionDigits: km < 10 ? 1 : 0, minimumFractionDigits: km < 10 ? 1 : 0 })} km`;
}

/** 45 -> "1 min", 600 -> "10 min", 3900 -> "1 h 05 min". Never shows "0 min". */
export function formatDuration(seconds: number): string {
  if (!Number.isFinite(seconds) || seconds < 0) return '—';
  const minutes = Math.max(1, Math.round(seconds / 60));
  if (minutes < 60) return `${minutes} min`;
  const hours = Math.floor(minutes / 60);
  const rest = minutes % 60;
  return rest ? `${hours} h ${String(rest).padStart(2, '0')} min` : `${hours} h`;
}

/** Local clock time after `seconds` from `now` ("14:35"). */
export function formatArrival(seconds: number, now = new Date(), locale = 'es'): string {
  return new Date(now.getTime() + seconds * 1000).toLocaleTimeString(locale, { hour: '2-digit', minute: '2-digit' });
}

/** Rating as "4.9" (one decimal) or null when there is none yet. */
export function formatRating(rating: number | string | null | undefined): string | null {
  const value = typeof rating === 'number' ? rating : Number.parseFloat(rating ?? '');
  if (!Number.isFinite(value) || value <= 0) return null;
  return value.toFixed(1);
}

/** "1.20" -> 1.2. A surge badge is shown only when this is > 1. */
export function surgeMultiplier(value: string | number | null | undefined): number {
  const n = typeof value === 'number' ? value : Number.parseFloat(value ?? '1');
  return Number.isFinite(n) && n > 0 ? n : 1;
}

export const hasSurge = (value: string | number | null | undefined) => surgeMultiplier(value) > 1.001;

/** "1.20" -> "×1.2". */
export const formatSurge = (value: string | number | null | undefined) =>
  `×${Number(surgeMultiplier(value).toFixed(2))}`;

/** "AB2C34D" -> "AB2 C34D" style grouping for legibility; leaves odd input alone. */
export function formatPlate(plate: string | null | undefined): string {
  const clean = (plate ?? '').toUpperCase().replace(/[^A-Z0-9]/g, '');
  if (clean.length < 6) return clean;
  return `${clean.slice(0, 3)} ${clean.slice(3)}`;
}

// ── Time ──

/** Whole seconds left until `iso` (never negative). */
export function secondsUntil(iso: string | null | undefined, now = Date.now()): number {
  if (!iso) return 0;
  const target = Date.parse(iso);
  if (Number.isNaN(target)) return 0;
  return Math.max(0, Math.ceil((target - now) / 1000));
}

/** 0..1 of a countdown, for progress rings. */
export function countdownProgress(iso: string, totalSeconds: number, now = Date.now()): number {
  if (totalSeconds <= 0) return 0;
  return Math.min(1, Math.max(0, (Date.parse(iso) - now) / (totalSeconds * 1000)));
}

/** Seconds since `iso` (for "searching for 0:42"). */
export function secondsSince(iso: string | null | undefined, now = Date.now()): number {
  if (!iso) return 0;
  const start = Date.parse(iso);
  return Number.isNaN(start) ? 0 : Math.max(0, Math.floor((now - start) / 1000));
}

/** 75 -> "1:15". */
export const formatClock = (seconds: number) =>
  `${Math.floor(seconds / 60)}:${String(Math.max(0, Math.floor(seconds % 60))).padStart(2, '0')}`;

// ── Ride state ──

export const ACTIVE_STATUSES: readonly RideStatus[] = ['searching', 'driver_assigned', 'driver_arrived', 'in_progress'];
export const TERMINAL_STATUSES: readonly RideStatus[] = [
  'completed',
  'cancelled_by_passenger',
  'cancelled_by_driver',
  'cancelled_by_admin',
  'no_drivers',
];

export const isActiveStatus = (status: RideStatus | undefined | null) => !!status && ACTIVE_STATUSES.includes(status);
export const isTerminalStatus = (status: RideStatus | undefined | null) =>
  !!status && TERMINAL_STATUSES.includes(status);

/** Statuses where the chat is open (POST /rides/{id}/messages). */
export const isChatOpen = (status: RideStatus | undefined | null) =>
  status === 'driver_assigned' || status === 'driver_arrived' || status === 'in_progress';

export const canPassengerCancel = (status: RideStatus | undefined | null) =>
  status === 'searching' || status === 'driver_assigned' || status === 'driver_arrived';

export const canDriverCancel = (status: RideStatus | undefined | null) =>
  status === 'driver_assigned' || status === 'driver_arrived';

export type DriverAction = 'arrive' | 'start' | 'complete';

/** The single next step the driver can take, as POST /rides/{id}/{action}. */
export function nextDriverAction(status: RideStatus | undefined | null): DriverAction | null {
  switch (status) {
    case 'driver_assigned':
      return 'arrive';
    case 'driver_arrived':
      return 'start';
    case 'in_progress':
      return 'complete';
    default:
      return null;
  }
}

/** Status a driver action leads to (for optimistic UI). */
export const DRIVER_ACTION_RESULT: Record<DriverAction, RideStatus> = {
  arrive: 'driver_arrived',
  start: 'in_progress',
  complete: 'completed',
};

/** Progress through the ride for the step indicator (1-based of 4). */
export function rideStep(status: RideStatus | undefined | null): number {
  switch (status) {
    case 'searching':
      return 1;
    case 'driver_assigned':
      return 2;
    case 'driver_arrived':
      return 3;
    case 'in_progress':
      return 4;
    case 'completed':
      return 5;
    default:
      return 0;
  }
}

/**
 * Which side of the ride the signed-in user is on, matching `passenger.id` / `driver.id` against the user id.
 * Returns null when neither matches (e.g. if the API sends profile ids instead of user ids).
 */
export function rideRoleStrict(
  ride: Pick<Ride, 'passenger' | 'driver'>,
  userId: string | undefined,
): 'passenger' | 'driver' | null {
  if (!userId) return null;
  if (ride.passenger?.id === userId) return 'passenger';
  if (ride.driver?.id === userId) return 'driver';
  return null;
}

/** Like `rideRoleStrict`, falling back to the app mode the user is in. */
export function rideRole(
  ride: Pick<Ride, 'passenger' | 'driver'>,
  userId: string | undefined,
  fallback: 'passenger' | 'driver' = 'passenger',
): 'passenger' | 'driver' {
  return rideRoleStrict(ride, userId) ?? fallback;
}

/**
 * Applies a newer server snapshot over a cached ride. Ignores snapshots that would move the ride backwards
 * (out-of-order WS vs. HTTP responses), except terminal statuses which always win.
 */
export function mergeRide(current: Ride | null | undefined, incoming: Ride): Ride {
  if (!current || current.id !== incoming.id) return incoming;
  if (isTerminalStatus(incoming.status)) return incoming;
  if (isTerminalStatus(current.status)) return current;
  if (rideStep(incoming.status) < rideStep(current.status)) {
    return { ...current, driver_location: incoming.driver_location ?? current.driver_location };
  }
  return { ...incoming, driver_location: incoming.driver_location ?? current.driver_location };
}

// ── Payment and ratings ──

export const DEFAULT_PAYMENT_METHODS: PaymentMethod[] = ['cash_usd', 'pago_movil', 'binance', 'zelle', 'cash_ves'];

/** Tags each side can give (contract): the passenger rates the driver and vice versa. */
export const RATING_TAGS = {
  passenger: ['safe_driving', 'on_time', 'friendly', 'clean_helmet'],
  driver: ['on_time', 'respectful', 'ready_at_pickup'],
} as const;

export const CANCEL_REASONS = {
  passenger: ['wait_too_long', 'driver_not_moving', 'changed_plans', 'wrong_pickup', 'other'],
  driver: ['passenger_no_show', 'wrong_pickup', 'unsafe_location', 'vehicle_problem', 'other'],
} as const;

// ── External navigation ──

export function googleMapsNavigationUrl(to: LatLng): string {
  return `https://www.google.com/maps/dir/?api=1&destination=${to.lat},${to.lng}&travelmode=driving`;
}

export function wazeNavigationUrl(to: LatLng): string {
  return `https://waze.com/ul?ll=${to.lat},${to.lng}&navigate=yes`;
}

/** Native scheme first (opens the app directly), web URL as fallback. */
export function googleMapsAppUrl(to: LatLng, platform: string): string {
  return platform === 'ios'
    ? `comgooglemaps://?daddr=${to.lat},${to.lng}&directionsmode=driving`
    : `google.navigation:q=${to.lat},${to.lng}&mode=d`;
}

// ── Search ──

/** True when `point` is inside the configured service area box (when known). */
export function inServiceArea(
  point: LatLng,
  area: { min_lat: number; max_lat: number; min_lng: number; max_lng: number } | undefined,
): boolean {
  if (!area) return true;
  return point.lat >= area.min_lat && point.lat <= area.max_lat && point.lng >= area.min_lng && point.lng <= area.max_lng;
}

/** Short label for a place: the first comma part of the address. */
export function shortAddress(address: string | null | undefined): string {
  const first = (address ?? '').split(',')[0]?.trim();
  return first || (address ?? '');
}

/** A /geo result as a ride Place: "Name, address" unless the address already starts with the name. */
export function placeFromGeo(result: { name?: string | null; address?: string | null; lat: number; lng: number }) {
  const name = (result.name ?? '').trim();
  const address = (result.address ?? '').trim();
  let label = address || name;
  if (name && address && !address.toLowerCase().startsWith(name.toLowerCase())) label = `${name}, ${address}`;
  return { lat: result.lat, lng: result.lng, address: label };
}
