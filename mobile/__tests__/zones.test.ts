import { describe, expect, it } from '@jest/globals';

import { ApiError } from '@/lib/api';
import { demandPushPoint, hrefForNotification, notificationKind } from '@/lib/notificationRoutes';
import {
  demandAreas,
  demandColors,
  demandHotSpot,
  dropoffRestrictionFromError,
  isZoneSurge,
  localizedZoneMessage,
  parseSuggestion,
  pickupRestrictionFromError,
  restrictedMessage,
  surgePercent,
  type DemandSnapshot,
} from '@/lib/zones';

const hexagon: [number, number][] = [
  [10.49, -66.85],
  [10.495, -66.845],
  [10.5, -66.85],
  [10.5, -66.855],
  [10.495, -66.86],
  [10.49, -66.855],
];

const snapshot = (fields: Partial<DemandSnapshot> = {}): DemandSnapshot => ({
  enabled: true,
  updated_at: '2026-10-17T12:00:00Z',
  window_minutes: 15,
  cells: [
    { cell: 'a', boundary: hexagon, center: [10.495, -66.85], level: 3, requests: 6, unmatched: 2, name: 'Chacao' },
    { cell: 'b', boundary: hexagon, center: [10.495, -66.85], level: 1, requests: 1, unmatched: 0 },
  ],
  hot: { name: 'Chacao', level: 3, distance_m: 1200, center: [10.495, -66.85] },
  ...fields,
});

describe('zone surcharge on the quote', () => {
  it('turns the multiplier into a whole percent', () => {
    expect(surgePercent('1.20')).toBe(20);
    expect(surgePercent('1.05')).toBe(5);
    expect(surgePercent(1.255)).toBe(26);
    expect(surgePercent('2.00')).toBe(100);
    expect(surgePercent('1.00')).toBe(0);
    expect(surgePercent(null)).toBe(0);
    expect(surgePercent('nonsense')).toBe(0);
  });

  it('only a zone reason with a real surcharge counts as a zone surge', () => {
    expect(isZoneSurge({ surge_reason: 'zone', surge_multiplier: '1.20' })).toBe(true);
    expect(isZoneSurge({ surge_reason: 'time', surge_multiplier: '1.20' })).toBe(false);
    expect(isZoneSurge({ surge_reason: null, surge_multiplier: '1.00' })).toBe(false);
    expect(isZoneSurge({ surge_multiplier: '1.30' })).toBe(false);
    expect(isZoneSurge({ surge_reason: 'zone', surge_multiplier: '1.00' })).toBe(false);
  });
});

describe('restricted pickup', () => {
  const suggestion = { name: 'Entrada Norte', lat: 10.5, lng: -66.9, distance_m: 180, zone: 'Recogida CCCT' };

  it('reads the suggestion from the error details', () => {
    const error = new ApiError(422, 'pickup_restricted', 'x', {
      zone: 'Aeropuerto',
      message: { es: 'Aquí no', en: 'Not here' },
      suggestion,
    });
    expect(pickupRestrictionFromError(error)).toEqual({ zone: 'Aeropuerto', message: { es: 'Aquí no', en: 'Not here' }, suggestion });
    expect(dropoffRestrictionFromError(error)).toBeNull();
  });

  it('copes with missing or broken details', () => {
    expect(pickupRestrictionFromError(new ApiError(422, 'pickup_restricted', 'x'))).toEqual({
      zone: null,
      message: null,
      suggestion: null,
    });
    expect(pickupRestrictionFromError(new ApiError(400, 'outside_service_area', 'x'))).toBeNull();
    expect(pickupRestrictionFromError(new TypeError('Network request failed'))).toBeNull();
    expect(parseSuggestion({ name: 'X', lat: '10', lng: -66 })).toBeNull();
    expect(parseSuggestion({ name: ' ', lat: 10, lng: -66 })).toBeNull();
    expect(parseSuggestion({ name: 'X', lat: 10, lng: -66 })).toEqual({ name: 'X', lat: 10, lng: -66, distance_m: 0, zone: null });
  });

  it("uses the zone's message in the app language, Spanish when there is no English one", () => {
    const check = { restricted: { zone: 'Aeropuerto', message: { es: 'Recoge en la entrada', en: 'Pick up at the gate' } } };
    expect(restrictedMessage(check, 'en')).toBe('Pick up at the gate');
    expect(restrictedMessage(check, 'es')).toBe('Recoge en la entrada');
    expect(localizedZoneMessage({ es: 'Solo español', en: '' }, 'en')).toBe('Solo español');
    expect(restrictedMessage(null, 'es', { es: 'Del error' })).toBe('Del error');
    expect(restrictedMessage({ restricted: null }, 'es')).toBe('');
  });
});

describe('driver demand map', () => {
  it('turns the cells into polygons', () => {
    const areas = demandAreas(snapshot());
    expect(areas).toHaveLength(2);
    expect(areas[0]).toEqual({ id: 'a', level: 3, coordinates: hexagon.map(([lat, lng]) => ({ lat, lng })) });
  });

  it('draws nothing when demand is switched off, and skips broken cells', () => {
    expect(demandAreas({ enabled: false, cells: [] })).toEqual([]);
    expect(demandAreas(undefined)).toEqual([]);
    const broken = snapshot({
      cells: [
        { cell: 'x', boundary: [[10, -66]], center: [10, -66], level: 2, requests: 3, unmatched: 0 },
        { cell: 'y', boundary: hexagon, center: [10, -66], level: 7 as never, requests: 3, unmatched: 0 },
      ],
    });
    expect(demandAreas(broken)).toEqual([]);
  });

  it('gives the nearest hot spot with its centre as a point', () => {
    expect(demandHotSpot(snapshot())).toMatchObject({ name: 'Chacao', distance_m: 1200, point: { lat: 10.495, lng: -66.85 } });
    expect(demandHotSpot(snapshot({ hot: null }))).toBeNull();
    expect(demandHotSpot({ enabled: false, cells: [], hot: snapshot().hot })).toBeNull();
  });

  it('colours the levels from the theme, the hottest the strongest', () => {
    const colors = { accent: '#FFC83D', warning: '#B45309', danger: '#B42318' };
    expect(demandColors(3, colors)).toEqual({ fill: '#B4231866', stroke: '#B42318' });
    expect(demandColors(2, colors).stroke).toBe('#B45309');
    expect(demandColors(1, colors).fill).toBe('#FFC83D40');
  });
});

describe('demand push', () => {
  const push = { type: 'demand', name: 'Chacao', lat: 10.495, lng: -66.853 };

  it('opens the driver home (the drive map)', () => {
    expect(hrefForNotification(push, { role: 'passenger' })).toEqual({ kind: 'route', href: '/', mode: 'driver' });
    expect(notificationKind(push)).toBe('ride');
  });

  it('knows where the demand is', () => {
    expect(demandPushPoint(push)).toEqual({ lat: 10.495, lng: -66.853 });
    expect(demandPushPoint({ data: { ...push, lat: '10.5', lng: '-66.8' } })).toEqual({ lat: 10.5, lng: -66.8 });
    expect(demandPushPoint({ type: 'demand', name: 'Chacao' })).toBeNull();
    expect(demandPushPoint({ type: 'ride', lat: 1, lng: 2 })).toBeNull();
  });
});
