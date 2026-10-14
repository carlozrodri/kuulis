import { keepPreviousData, useQuery, useQueryClient } from '@tanstack/react-query';
import { useEffect, useRef } from 'react';
import { useTranslation } from 'react-i18next';
import { Alert, AppState } from 'react-native';

import { DRIVER_QUERY_KEY } from '@/hooks/useDriver';
import { useUserLocation, getLastPosition } from '@/hooks/useLocation';
import { useRealtimeEvent } from '@/hooks/useRealtime';
import { rideKeys } from '@/hooks/useRides';
import { noticeText } from '@/i18n';
import { api, setControlErrorHandler, tokens } from '@/lib/api';
import {
  type AppLinks,
  type Bootstrap,
  emergencyNumberFrom,
  type FlagKey,
  flagValue,
  type LocationIntervals,
  DEFAULT_LOCATION_INTERVALS,
  parseBootstrap,
  parseDismissed,
  parseNotice,
  randomClientId,
  refreshIntervalMs,
  rememberDismissed,
  withServiceNotice,
} from '@/lib/bootstrap';
import { localFile } from '@/lib/localFile';
import { mockLocationTookOffline } from '@/lib/location';
import { secureStorage } from '@/lib/storage';
import { createStore, useStore } from '@/lib/store';
import { useAuth } from '@/providers/AuthProvider';
import { useMode } from '@/providers/ModeProvider';

/**
 * Remote control (doc 10). <BootstrapSync /> reads GET /app/bootstrap at start, every `refresh_seconds`, when
 * the app comes back to the foreground and on the `config.updated` event; every screen reads the result from
 * a shared store. The last good answer is kept on the device, so the app keeps working offline, and a failed
 * read never blocks anything: features fall back to their defaults.
 */

type BootstrapState = {
  data: Bootstrap | null;
  /** Read from the server in this session (not only from the device cache). */
  fresh: boolean;
  /** The last read failed (offline, server error). */
  failed: boolean;
};

const CACHE_FILE = 'kuulis-bootstrap.json';
const DISMISSED_FILE = 'kuulis-dismissed-banners.json';
const CLIENT_ID_KEY = 'kuulis.client_id';
export const BOOTSTRAP_QUERY_KEY = ['app', 'bootstrap'] as const;

export const bootstrapStore = createStore<BootstrapState>({ data: null, fresh: false, failed: false });
/** Closed banners on this device (null until read from storage). */
const dismissedStore = createStore<string[] | null>(null);
/** Bumped to ask <BootstrapSync /> to read the bootstrap again now. */
const refreshRequests = createStore(0);

let cacheLoaded = false;
function loadLocalState() {
  if (cacheLoaded) return;
  cacheLoaded = true;
  void localFile.read(CACHE_FILE).then((raw) => {
    if (!raw || bootstrapStore.get().data) return;
    try {
      bootstrapStore.set((s) => (s.data ? s : { ...s, data: parseBootstrap(JSON.parse(raw)) }));
    } catch {
      // corrupt cache: wait for the server
    }
  });
  void localFile.read(DISMISSED_FILE).then((raw) => {
    const stored = parseDismissed(raw);
    // Keep anything closed while the file was being read.
    dismissedStore.set((current) => [...stored, ...(current ?? []).filter((id) => !stored.includes(id))]);
  });
}

let clientIdPromise: Promise<string> | null = null;
/** A random id kept on this install: identifies the device before login (closed banners, rollouts). */
export function getClientId(): Promise<string> {
  clientIdPromise ??= (async () => {
    const stored = await secureStorage.get(CLIENT_ID_KEY).catch(() => null);
    if (stored) return stored;
    const id = randomClientId();
    await secureStorage.set(CLIENT_ID_KEY, id).catch(() => undefined);
    return id;
  })();
  return clientIdPromise;
}

export function requestBootstrapRefresh() {
  refreshRequests.set((n) => n + 1);
}

function setData(data: Bootstrap) {
  bootstrapStore.set({ data, fresh: true, failed: false });
}

// 503 service_paused / 403 feature_disabled: apply what the error says right away, then read it all again.
setControlErrorHandler((code, details) => {
  const current = bootstrapStore.get().data;
  if (code === 'service_paused') {
    const notice = parseNotice(details);
    if (notice && current) setData(withServiceNotice(current, notice));
  } else if (current) {
    const feature = (details as { feature?: unknown } | null)?.feature;
    if (typeof feature === 'string' && feature in current.flags) {
      setData({ ...current, flags: { ...current.flags, [feature as FlagKey]: false } });
    }
  }
  requestBootstrapRefresh();
});

async function fetchBootstrap(mode: string | null): Promise<Bootstrap> {
  const position = getLastPosition();
  const clientId = await getClientId().catch(() => undefined);
  try {
    const raw = await api<unknown>('/app/bootstrap', {
      query: {
        mode: mode ?? undefined,
        lat: position ? Number(position.lat.toFixed(5)) : undefined,
        lng: position ? Number(position.lng.toFixed(5)) : undefined,
        client_id: clientId,
      },
    });
    const data = parseBootstrap(raw);
    setData(data);
    void localFile.write(CACHE_FILE, JSON.stringify(data));
    return data;
  } catch (error) {
    bootstrapStore.set((s) => ({ ...s, failed: true }));
    throw error;
  }
}

/**
 * Keeps the bootstrap fresh. Mounted once in the signed-in layout (it needs the realtime socket). The query key
 * changes with the mode, the account and the rough position (~10 km), so moving to another city re-reads it.
 */
export function BootstrapSync() {
  const { t, i18n } = useTranslation();
  const queryClient = useQueryClient();
  const { user } = useAuth();
  const { mode } = useMode();
  // Never asks for permission: uses the position other screens already have.
  const { position } = useUserLocation({ watch: false });
  const bucket = position ? `${position.lat.toFixed(1)},${position.lng.toFixed(1)}` : '';
  const state = useStore(bootstrapStore);

  useEffect(loadLocalState, []);

  const query = useQuery({
    queryKey: [...BOOTSTRAP_QUERY_KEY, mode ?? '', user?.id ?? '', bucket],
    queryFn: () => fetchBootstrap(mode),
    refetchInterval: refreshIntervalMs(state.data),
    staleTime: 15_000,
    retry: 1,
    placeholderData: keepPreviousData,
  });
  const refetchRef = useRef(query.refetch);
  useEffect(() => {
    refetchRef.current = query.refetch;
  });

  const requests = useStore(refreshRequests);
  useEffect(() => {
    if (requests) void refetchRef.current();
  }, [requests]);

  useEffect(() => {
    const sub = AppState.addEventListener('change', (next) => {
      if (next === 'active') void refetchRef.current();
    });
    return () => sub.remove();
  }, []);

  useRealtimeEvent('config.updated', () => {
    void refetchRef.current();
  });

  // The server took this driver offline: maintenance or a pause in their city.
  useRealtimeEvent<unknown>('driver.paused', (data) => {
    const notice = parseNotice(data);
    const current = bootstrapStore.get().data;
    if (notice && current) setData(withServiceNotice(current, notice));
    void queryClient.invalidateQueries({ queryKey: rideKeys.driverState });
    void queryClient.invalidateQueries({ queryKey: DRIVER_QUERY_KEY });
    void refetchRef.current();
    Alert.alert(
      t(notice?.kind === 'maintenance' ? 'control.driverPaused.maintenanceTitle' : 'control.driverPaused.title'),
      [notice ? noticeText(notice, i18n.language) : t('control.pause.defaultBody'), t('control.driverPaused.body')].join('\n\n'),
    );
  });

  // Doc 16: positions from a mock location app. Off a ride the server takes the driver offline at once.
  useRealtimeEvent<unknown>('driver.mock_location', (data) => {
    if (!mockLocationTookOffline(data)) return;
    void queryClient.invalidateQueries({ queryKey: rideKeys.driverState });
    void queryClient.invalidateQueries({ queryKey: DRIVER_QUERY_KEY });
    Alert.alert(t('risk.mockLocation.title'), t('risk.mockLocation.body'));
  });

  return null;
}

/** The last known bootstrap (cache or server) and whether it is from this session. */
export function useBootstrap() {
  return useStore(bootstrapStore);
}

/** Is this feature on? Defaults while unknown: every feature on (doc 11 turned share_live_link on). */
export function useFlag(key: FlagKey): boolean {
  return flagValue(useStore(bootstrapStore).data, key);
}

/** Support, emergency and legal links; the emergency number falls back to 911. */
export function useAppLinks(): AppLinks & { emergency: string } {
  const links = useStore(bootstrapStore).data?.links;
  return {
    support_whatsapp: links?.support_whatsapp ?? '',
    support_email: links?.support_email ?? '',
    emergency_number: links?.emergency_number ?? '',
    terms_url: links?.terms_url ?? '',
    privacy_url: links?.privacy_url ?? '',
    emergency: emergencyNumberFrom(links),
  };
}

/** For callbacks outside React. */
export const currentEmergencyNumber = () => emergencyNumberFrom(bootstrapStore.get().data?.links);

export function useLocationIntervals(): LocationIntervals {
  return useStore(bootstrapStore).data?.location_intervals ?? DEFAULT_LOCATION_INTERVALS;
}

export function useDismissedAnnouncements(): string[] | null {
  useEffect(loadLocalState, []);
  return useStore(dismissedStore);
}

/** Closes a banner for good: remembered on the device (works offline) and told to the server. */
export async function dismissAnnouncement(id: string) {
  const next = rememberDismissed(dismissedStore.get() ?? [], id);
  dismissedStore.set(next);
  void localFile.write(DISMISSED_FILE, JSON.stringify(next));
  try {
    const clientId = tokens.access ? undefined : await getClientId();
    await api(`/app/announcements/${encodeURIComponent(id)}/dismiss`, {
      method: 'POST',
      query: { client_id: clientId },
    });
  } catch {
    // remembered locally anyway
  }
}
