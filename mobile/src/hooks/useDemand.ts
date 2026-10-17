import { useQuery, useQueryClient } from '@tanstack/react-query';
import { useEffect, useRef } from 'react';

import { useRealtimeEvent } from '@/hooks/useRealtime';
import { api } from '@/lib/api';
import { secureStorage } from '@/lib/storage';
import { createStore, useStore } from '@/lib/store';
import type { LatLng } from '@/lib/types';
import type { DemandSnapshot } from '@/lib/zones';

/**
 * Doc 21: the driver's "Demanda" map layer. Its on/off is remembered on the device; while it is on the cells
 * are read again every minute and right away when the server says the map changed (`demand.updated`).
 */
// Own root (not under ['drivers', 'me']): the demand of a few minutes ago is not worth keeping offline (doc 20).
export const DEMAND_QUERY_KEY = ['driver-demand'] as const;
export const DEMAND_REFRESH_MS = 60_000;

const LAYER_KEY = 'kuulis.demand_layer';
/** null until the saved choice is read. */
export const demandLayer = createStore<boolean | null>(null);
let loading: Promise<void> | null = null;

export function loadDemandLayer(): Promise<void> {
  loading ??= secureStorage
    .get(LAYER_KEY)
    .catch(() => null)
    .then((saved) => {
      if (demandLayer.get() === null) demandLayer.set(saved === '1');
    });
  return loading;
}

export function setDemandLayer(on: boolean) {
  demandLayer.set(on);
  void secureStorage.set(LAYER_KEY, on ? '1' : '0').catch(() => undefined);
}

/** A point the map should show (a demand push was tapped); the dashboard consumes it. */
export const demandFocusRequest = createStore<(LatLng & { at: number }) | null>(null);

export function useDemandLayer(): [boolean, (on: boolean) => void] {
  const on = useStore(demandLayer);
  useEffect(() => {
    void loadDemandLayer();
  }, []);
  return [!!on, setDemandLayer];
}

/**
 * GET /drivers/me/demand around the driver. Read once even with the layer off (to know whether demand is
 * enabled at all and hide the switch otherwise); polled only while the layer is on.
 */
export function useDemand(position: LatLng | null | undefined, layerOn: boolean) {
  const queryClient = useQueryClient();
  // The position is read when fetching: a moving driver should not restart the query on every GPS update.
  const where = useRef(position);
  useEffect(() => {
    where.current = position;
  });
  const hasPosition = !!position;

  const query = useQuery({
    queryKey: DEMAND_QUERY_KEY,
    queryFn: ({ signal }) => {
      const point = where.current;
      return api<DemandSnapshot>('/drivers/me/demand', { query: { lat: point?.lat, lng: point?.lng }, signal });
    },
    enabled: hasPosition,
    staleTime: layerOn ? DEMAND_REFRESH_MS / 2 : 5 * 60_000,
    refetchInterval: layerOn ? DEMAND_REFRESH_MS : false,
    // A 403 (not approved) or 404 (older server) will not change by asking again.
    retry: (count, error) => count < 1 && !(error as { status?: number }).status,
  });

  useRealtimeEvent('demand.updated', () => {
    if (layerOn) void queryClient.invalidateQueries({ queryKey: DEMAND_QUERY_KEY });
  });

  // Turning the layer on shows fresh cells, not the ones read when it was off.
  const wasOn = useRef(layerOn);
  useEffect(() => {
    if (layerOn && !wasOn.current && hasPosition) void queryClient.invalidateQueries({ queryKey: DEMAND_QUERY_KEY });
    wasOn.current = layerOn;
  }, [layerOn, hasPosition, queryClient]);

  // true / false once known (false: switched off by the admin); null while loading or on an error (an older
  // server without the endpoint answers 404).
  const enabled = query.data ? query.data.enabled !== false : null;
  return { ...query, enabled };
}
