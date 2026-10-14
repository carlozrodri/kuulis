import * as Location from 'expo-location';
import * as TaskManager from 'expo-task-manager';
import { AppState, Platform } from 'react-native';

import { api, tokens } from '@/lib/api';
import { isMockedLocation, positionBody } from '@/lib/location';
import { createStore } from '@/lib/store';

/**
 * Keeps sending an online driver's position while the app is minimized or the screen is off (Android).
 *
 * expo-location runs a foreground service with a fixed notification ("Kuulis está compartiendo tu
 * ubicación"); that does not need the "allow all the time" permission. Each position goes to
 * POST /drivers/me/location because the socket may be asleep in the background. Swiping the app away stops
 * the service, and the API takes the driver offline after a minute without positions.
 * Not available in Expo Go or on iOS yet: there the app asks to stay open (see `backgroundLocationActive`).
 */
const TASK = 'kuulis-driver-location';

/** Notification texts and how often to send the position (remote setting, doc 10). */
type Copy = { title: string; body: string; intervalMs?: number };

const DEFAULT_INTERVAL_MS = 5000;

/** True while the background service is running (the "keep the app open" notice is then hidden). */
export const backgroundLocationActive = createStore(false);

type TaskData = { locations?: Location.LocationObject[] };

TaskManager.defineTask<TaskData>(TASK, async ({ data, error }) => {
  if (error || !data?.locations?.length) return;
  const last = data.locations[data.locations.length - 1];
  try {
    // A task started after the app was killed runs without the session in memory.
    if (!tokens.access) await tokens.load();
    if (!tokens.access) return;
    const { latitude, longitude, heading, speed } = last.coords;
    await api('/drivers/me/location', {
      method: 'POST',
      body: positionBody({ lat: latitude, lng: longitude, heading, speed, mocked: isMockedLocation(last) }),
    });
  } catch {
    // the next position retries
  }
});

const supported = () => Platform.OS === 'android';

let wanted: Copy | null = null;
/** Interval the running service was started with (a new one restarts it while the app is on screen). */
let startedInterval: number | null = null;

async function start(copy: Copy) {
  const interval = copy.intervalMs ?? DEFAULT_INTERVAL_MS;
  if (await Location.hasStartedLocationUpdatesAsync(TASK).catch(() => false)) {
    backgroundLocationActive.set(true);
    // A foreground service can only be (re)started with the app on screen.
    if (startedInterval === null || startedInterval === interval || AppState.currentState !== 'active') return;
  }
  startedInterval = interval;
  await Location.startLocationUpdatesAsync(TASK, {
    accuracy: Location.Accuracy.High,
    timeInterval: interval,
    distanceInterval: 10,
    pausesUpdatesAutomatically: false,
    foregroundService: {
      notificationTitle: copy.title,
      notificationBody: copy.body,
      notificationColor: '#0E7C5A',
      killServiceOnDestroy: true,
    },
  });
  backgroundLocationActive.set(true);
}

/**
 * Starts the service while the driver is online (it can only start with the app on screen, so a failed start
 * is retried when the app comes back) and stops it when they go offline.
 */
export async function setBackgroundLocation(copy: Copy | null) {
  wanted = copy;
  if (!supported()) return;
  try {
    if (copy) await start(copy);
    else {
      backgroundLocationActive.set(false);
      startedInterval = null;
      if (await Location.hasStartedLocationUpdatesAsync(TASK).catch(() => false)) {
        await Location.stopLocationUpdatesAsync(TASK);
      }
    }
  } catch (error) {
    backgroundLocationActive.set(false);
    console.warn('Background location unavailable', error);
  }
}

if (supported()) {
  AppState.addEventListener('change', (state) => {
    if (state === 'active' && wanted && !backgroundLocationActive.get()) void setBackgroundLocation(wanted);
  });
}
