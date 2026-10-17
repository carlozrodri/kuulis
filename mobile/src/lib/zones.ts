/**
 * Doc 21 · Zonas y demanda (docs/api/zonas.md): the passenger's pickup check (restricted zones and suggested
 * pickup points), the zone surcharge text on the quote and the driver's demand map. Pure helpers, no React.
 */
import { ApiError } from './api';
import { localize, type Localized } from './bootstrap';
import { surgeMultiplier } from './ride';
import type { LatLng, Place } from './types';

// ── Passenger: GET /zones/check ──

/** The nearest suggested pickup point (≤ 1.5 km). */
export interface ZoneSuggestion {
  name: string;
  lat: number;
  lng: number;
  distance_m: number;
  zone?: string | null;
}

export interface ZoneCheck {
  /** null: outside the service area. */
  city: string | null;
  /** The pickup is inside a zone where drivers cannot pick up. */
  restricted: { zone: string; message?: Partial<Localized> | null } | null;
  suggestion: ZoneSuggestion | null;
  surge: { multiplier: string; zone: string } | null;
}

const isRecord = (value: unknown): value is Record<string, unknown> => !!value && typeof value === 'object' && !Array.isArray(value);

/** A suggestion from the API (check or error details), or null when it is not a usable point. */
export function parseSuggestion(value: unknown): ZoneSuggestion | null {
  if (!isRecord(value)) return null;
  const { name, lat, lng } = value;
  if (typeof name !== 'string' || !name.trim() || typeof lat !== 'number' || typeof lng !== 'number') return null;
  if (!Number.isFinite(lat) || !Number.isFinite(lng)) return null;
  const distance = Number(value.distance_m);
  return {
    name: name.trim(),
    lat,
    lng,
    distance_m: Number.isFinite(distance) ? distance : 0,
    zone: typeof value.zone === 'string' ? value.zone : null,
  };
}

export interface ZoneRestriction {
  zone: string | null;
  /** The zone's own explanation ({es, en}), when the admin wrote one. */
  message: Partial<Localized> | null;
  suggestion: ZoneSuggestion | null;
}

function restrictionFromError(error: unknown, code: string): ZoneRestriction | null {
  if (!(error instanceof ApiError) || error.code !== code) return null;
  const details = isRecord(error.details) ? error.details : {};
  return {
    zone: typeof details.zone === 'string' ? details.zone : null,
    message: isRecord(details.message) ? (details.message as Partial<Localized>) : null,
    suggestion: parseSuggestion(details.suggestion),
  };
}

/** 422 pickup_restricted on the quote or the request: the zone, its message and the nearest point to use instead. */
export const pickupRestrictionFromError = (error: unknown) => restrictionFromError(error, 'pickup_restricted');

/** 422 dropoff_restricted: the destination is in a zone where drivers cannot drop off. */
export const dropoffRestrictionFromError = (error: unknown) => restrictionFromError(error, 'dropoff_restricted');

/** A zone's own message in the app language (Spanish when there is no English one); '' when there is none. */
export function localizedZoneMessage(message: Partial<Localized> | null | undefined, language: string): string {
  if (!message) return '';
  return localize({ es: typeof message.es === 'string' ? message.es : '', en: typeof message.en === 'string' ? message.en : '' }, language);
}

/** The restricted zone's message from the check, else from the error details. */
export const restrictedMessage = (
  check: Pick<ZoneCheck, 'restricted'> | null | undefined,
  language: string,
  fallback?: Partial<Localized> | null,
) => localizedZoneMessage(check?.restricted?.message, language) || localizedZoneMessage(fallback, language);

/** The pickup moved to the suggested point: its name stands in for the address. */
export const suggestionPlace = (suggestion: ZoneSuggestion): Place => ({
  lat: suggestion.lat,
  lng: suggestion.lng,
  address: suggestion.name,
});

// ── Quote: zone surcharge ──

/** "1.20" → 20 (whole percent over the base fare); 0 without a surcharge. */
export function surgePercent(multiplier: string | number | null | undefined): number {
  // toFixed first: (1.255 - 1) * 100 is 25.4999… in floating point.
  return Math.max(0, Math.round(Number(((surgeMultiplier(multiplier) - 1) * 100).toFixed(6))));
}

/** The quote's surcharge comes from a surge zone at the pickup (doc 21), and there is one to show. */
export const isZoneSurge = (quote: { surge_reason?: string | null; surge_multiplier: string }) =>
  quote.surge_reason === 'zone' && surgePercent(quote.surge_multiplier) > 0;

// ── Driver: GET /drivers/me/demand ──

export type DemandLevel = 1 | 2 | 3;

export interface DemandCell {
  cell: string;
  /** Six [lat, lng] corners of the H3 hexagon. */
  boundary: [number, number][];
  center: [number, number];
  level: DemandLevel;
  requests: number;
  unmatched: number;
  name?: string | null;
}

export interface DemandHot {
  name: string;
  level: DemandLevel;
  distance_m: number;
  center: [number, number];
}

export interface DemandSnapshot {
  enabled: boolean;
  updated_at?: string | null;
  window_minutes?: number;
  cells: DemandCell[];
  hot?: DemandHot | null;
}

export const DEMAND_LEVELS: readonly DemandLevel[] = [1, 2, 3];

const toLatLng = (pair: unknown): LatLng | null =>
  Array.isArray(pair) && typeof pair[0] === 'number' && typeof pair[1] === 'number' && Number.isFinite(pair[0]) && Number.isFinite(pair[1])
    ? { lat: pair[0], lng: pair[1] }
    : null;

export interface DemandArea {
  id: string;
  level: DemandLevel;
  coordinates: LatLng[];
}

/** The cells as polygons to draw (cells with a broken boundary or an unknown level are skipped). */
export function demandAreas(snapshot: DemandSnapshot | null | undefined): DemandArea[] {
  if (!snapshot?.enabled || !Array.isArray(snapshot.cells)) return [];
  const areas: DemandArea[] = [];
  for (const cell of snapshot.cells) {
    if (!DEMAND_LEVELS.includes(cell.level)) continue;
    const coordinates = (Array.isArray(cell.boundary) ? cell.boundary : []).map(toLatLng).filter((p): p is LatLng => !!p);
    if (coordinates.length >= 3) areas.push({ id: cell.cell, level: cell.level, coordinates });
  }
  return areas;
}

/** The nearest hot cell, with its centre as a point, or null. */
export function demandHotSpot(snapshot: DemandSnapshot | null | undefined): (DemandHot & { point: LatLng }) | null {
  const hot = snapshot?.enabled ? snapshot.hot : null;
  if (!hot || typeof hot.name !== 'string' || !hot.name.trim()) return null;
  const point = toLatLng(hot.center);
  return point ? { ...hot, name: hot.name.trim(), point } : null;
}

/** The map colours of a level: a see-through fill over the streets and a solid edge. */
export function demandColors(level: DemandLevel, colors: { accent: string; warning: string; danger: string }) {
  const base = level === 3 ? colors.danger : level === 2 ? colors.warning : colors.accent;
  // #RRGGBB + alpha: 3 is the strongest so the hottest cells stand out.
  const alpha = level === 3 ? '66' : level === 2 ? '52' : '40';
  return { fill: `${base}${alpha}`, stroke: base };
}
