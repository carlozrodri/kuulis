import * as Location from 'expo-location';
import * as TaskManager from 'expo-task-manager';
import { AppState, Platform } from 'react-native';

import { api, tokens } from '@/lib/api';
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

type Copy = { title: string; body: string };

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
      body: {
        lat: latitude,
        lng: longitude,
        ...(heading != null && heading >= 0 ? { heading: Math.round(heading) } : {}),
        ...(speed != null && speed >= 0 ? { speed: Math.round(speed * 10) / 10 } : {}),
      },
    });
  } catch {
    // the next position retries
  }
});

const supported = () => Platform.OS === 'android';

let wanted: Copy | null = null;

async function start(copy: Copy) {
  if (await Location.hasStartedLocationUpdatesAsync(TASK).catch(() => false)) {
    backgroundLocationActive.set(true);
    return;
  }
  await Location.startLocationUpdatesAsync(TASK, {
    accuracy: Location.Accuracy.High,
    timeInterval: 5000,
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
