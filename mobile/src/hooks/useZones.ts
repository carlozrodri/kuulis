import { useQuery } from '@tanstack/react-query';

import { api } from '@/lib/api';
import type { LatLng } from '@/lib/types';
import type { ZoneCheck } from '@/lib/zones';

export const zoneCheckKey = (point: LatLng | null | undefined) => ['zones', 'check', point?.lat, point?.lng] as const;

/**
 * Doc 21: GET /zones/check for the chosen pickup (restricted zone, suggested pickup point, zone surcharge).
 * Only a hint: when it fails (no signal, older server) the quote still says what matters.
 */
export function useZoneCheck(point: LatLng | null | undefined, enabled = true) {
  return useQuery({
    queryKey: zoneCheckKey(point),
    queryFn: ({ signal }) => api<ZoneCheck>('/zones/check', { query: { lat: point!.lat, lng: point!.lng }, signal }),
    enabled: enabled && !!point,
    staleTime: 5 * 60_000,
    retry: false,
  });
}
