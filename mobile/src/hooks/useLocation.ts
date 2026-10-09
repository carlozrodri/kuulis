import * as Location from 'expo-location';
import { useCallback, useEffect } from 'react';
import { AppState, Linking } from 'react-native';

import { createStore, useStore } from '@/lib/store';

export type PermissionState = 'unknown' | 'granted' | 'denied' | 'blocked';

export type UserPosition = {
  lat: number;
  lng: number;
  heading: number | null;
  speed: number | null;
  accuracy: number | null;
  timestamp: number;
};

type LocationState = { permission: PermissionState; position: UserPosition | null };

/** Device location shared by every screen: one GPS watch while any screen needs it. */
const locationStore = createStore<LocationState>({ permission: 'unknown', position: null });

let watchers = 0;
let subscription: Location.LocationSubscription | null = null;
let starting = false;

function toPosition(location: Location.LocationObject): UserPosition {
  const { latitude, longitude, heading, speed, accuracy } = location.coords;
  return {
    lat: latitude,
    lng: longitude,
    // iOS reports -1 when the heading is unknown.
    heading: heading != null && heading >= 0 ? heading : null,
    speed: speed != null && speed >= 0 ? speed : null,
    accuracy: accuracy ?? null,
    timestamp: location.timestamp,
  };
}

function permissionFrom(response: Location.LocationPermissionResponse): PermissionState {
  if (response.granted) return 'granted';
  if (response.status === 'undetermined') return 'unknown';
  return response.canAskAgain ? 'denied' : 'blocked';
}

async function refreshPermission() {
  try {
    const response = await Location.getForegroundPermissionsAsync();
    locationStore.set((s) => ({ ...s, permission: permissionFrom(response) }));
    return response.granted;
  } catch {
    return false;
  }
}

async function startWatch() {
  if (subscription || starting) return;
  starting = true;
  try {
    if (!(await refreshPermission())) return;
    const last = await Location.getLastKnownPositionAsync({ maxAge: 5 * 60_000 }).catch(() => null);
    if (last && !locationStore.get().position) locationStore.set((s) => ({ ...s, position: toPosition(last) }));
    const sub = await Location.watchPositionAsync(
      { accuracy: Location.Accuracy.High, timeInterval: 3000, distanceInterval: 5 },
      (location) => locationStore.set((s) => ({ ...s, position: toPosition(location) })),
    );
    if (watchers > 0) subscription = sub;
    else sub.remove();
  } catch (error) {
    console.warn('Location watch failed', error);
  } finally {
    starting = false;
  }
}

function stopWatch() {
  subscription?.remove();
  subscription = null;
}

/** Asks for foreground location permission (only "while using the app"). */
export async function requestLocationPermission(): Promise<boolean> {
  try {
    const response = await Location.requestForegroundPermissionsAsync();
    locationStore.set((s) => ({ ...s, permission: permissionFrom(response) }));
    if (response.granted && watchers > 0) void startWatch();
    return response.granted;
  } catch {
    return false;
  }
}

/** A fresh fix for actions that need one now (going online). Falls back to the last known position. */
export async function getFreshPosition(): Promise<UserPosition | null> {
  const current = locationStore.get().position;
  if (current && Date.now() - current.timestamp < 15_000) return current;
  try {
    const location = await Promise.race([
      Location.getCurrentPositionAsync({ accuracy: Location.Accuracy.High }),
      new Promise<null>((resolve) => setTimeout(() => resolve(null), 8000)),
    ]);
    if (location) {
      const position = toPosition(location);
      locationStore.set((s) => ({ ...s, position }));
      return position;
    }
  } catch {
    // fall through to the last known fix
  }
  const last = await Location.getLastKnownPositionAsync().catch(() => null);
  return last ? toPosition(last) : current;
}

export const getLastPosition = () => locationStore.get().position;

/**
 * Current position and permission. With `watch`, keeps a GPS subscription alive while mounted
 * (shared and ref-counted), and re-checks permission when the app comes back from settings.
 */
export function useUserLocation({ watch = true }: { watch?: boolean } = {}) {
  const state = useStore(locationStore);

  useEffect(() => {
    void refreshPermission();
    const sub = AppState.addEventListener('change', (next) => {
      if (next !== 'active') return;
      void refreshPermission().then((granted) => {
        if (granted && watchers > 0) void startWatch();
      });
    });
    return () => sub.remove();
  }, []);

  useEffect(() => {
    if (!watch) return;
    watchers += 1;
    void startWatch();
    return () => {
      watchers -= 1;
      if (watchers === 0) stopWatch();
    };
  }, [watch]);

  useEffect(() => {
    if (watch && state.permission === 'granted' && !subscription) void startWatch();
  }, [watch, state.permission]);

  const request = useCallback(async () => {
    if (state.permission === 'blocked') {
      await Linking.openSettings().catch(() => undefined);
      return false;
    }
    return requestLocationPermission();
  }, [state.permission]);

  return { ...state, request };
}
