import * as FileSystem from 'expo-file-system/legacy';
import { AppState, Platform } from 'react-native';

import {
  batchOutcome,
  BATCH_SIZE,
  cellOf,
  enqueue,
  parseQueue,
  type AnalyticsEventName,
  type AnalyticsProps,
  type QueuedEvent,
} from './analyticsCore';
import { tokens } from './api';
import { appVersion } from './appVersion';
import { config } from './config';
import { randomId } from './deviceId';
import { secureStorage } from './storage';

export type { AnalyticsEventName, AnalyticsProps } from './analyticsCore';

/**
 * Anonymous product analytics (doc 19): `track()` adds an event to a queue kept in a file, sent to
 * POST /analytics/events in batches every 30 s and when the app goes to the background. No email, phone or
 * coordinates: a place travels only as its ~1 km cell. Profile → Settings → "Compartir datos de uso anónimos"
 * switches it off (consent "usage_data"); then nothing is queued and the queue is emptied. Best-effort: it never
 * throws and never blocks the app.
 */
const ANON_KEY = 'kuulis.analytics_anon_id';
const ENABLED_KEY = 'kuulis.analytics_enabled';
const QUEUE_FILE = 'kuulis-analytics-queue.json';
const FLUSH_EVERY_MS = 30_000;

let queue: QueuedEvent[] = [];
let enabled = true;
let anonId: string | null = null;
let started = false;
let flushing = false;
let loaded: Promise<void> | null = null;
let saveTimer: ReturnType<typeof setTimeout> | null = null;

function queuePath(): string | null {
  return FileSystem.documentDirectory ? `${FileSystem.documentDirectory}${QUEUE_FILE}` : null;
}

function load(): Promise<void> {
  loaded ??= (async () => {
    try {
      enabled = (await secureStorage.get(ENABLED_KEY)) !== '0';
      if (!enabled) queue = [];
      anonId = await secureStorage.get(ANON_KEY);
      if (!anonId) {
        anonId = `a-${randomId()}`;
        await secureStorage.set(ANON_KEY, anonId);
      }
      const path = queuePath();
      if (path && Platform.OS !== 'web') {
        const info = await FileSystem.getInfoAsync(path);
        if (info.exists) queue = [...parseQueue(await FileSystem.readAsStringAsync(path)), ...queue];
      }
    } catch {
      anonId ??= `a-${randomId()}`;
    }
  })();
  return loaded;
}

function save() {
  if (saveTimer) return;
  saveTimer = setTimeout(() => {
    saveTimer = null;
    const path = queuePath();
    if (!path || Platform.OS === 'web') return;
    void FileSystem.writeAsStringAsync(path, JSON.stringify(queue)).catch(() => undefined);
  }, 1000);
}

/** Queues one event. `at` adds the ~1 km cell of a place (never the place itself). */
export function track(event: AnalyticsEventName, props: AnalyticsProps = {}, at?: { lat: number; lng: number } | null) {
  if (!enabled) return;
  const item: QueuedEvent = { event, occurred_at: new Date().toISOString(), props };
  const cell = at ? cellOf(at.lat, at.lng) : undefined;
  if (cell) item.cell = cell;
  queue = enqueue(queue, item);
  save();
}

/** Sends what is queued (in batches of 100); keeps it for later when offline. */
export async function flush(): Promise<void> {
  await load();
  if (flushing || !enabled || !queue.length || !anonId) return;
  flushing = true;
  try {
    while (queue.length && enabled) {
      const batch = queue.slice(0, BATCH_SIZE);
      const headers: Record<string, string> = { 'Content-Type': 'application/json' };
      if (tokens.access) headers.Authorization = `Bearer ${tokens.access}`;
      let status: number | null = null;
      try {
        const response = await fetch(`${config.apiUrl}/analytics/events`, {
          method: 'POST',
          headers,
          body: JSON.stringify({
            anon_id: anonId,
            platform: appVersion.platform,
            app_version: `${appVersion.version || '?'} (${appVersion.build})`.slice(0, 40),
            events: batch,
          }),
        });
        status = response.status;
      } catch {
        status = null;
      }
      if (batchOutcome(status) === 'retry') break;
      queue = queue.slice(batch.length);
      save();
    }
  } finally {
    flushing = false;
  }
}

/** The answer in force for this phone: the signed-in user's consent, or the last one seen here. */
export async function setAnalyticsEnabled(value: boolean): Promise<void> {
  await load();
  if (enabled === value) return;
  enabled = value;
  if (!value) {
    queue = [];
    save();
  }
  await secureStorage.set(ENABLED_KEY, value ? '1' : '0').catch(() => undefined);
}

export function analyticsEnabled(): boolean {
  return enabled;
}

/** Starts the 30 s timer and the flush on going to the background; records the cold start. */
export function startAnalytics() {
  if (started) return;
  started = true;
  void load().then(() => {
    track('app_open', { cold: true });
    void flush();
  });
  setInterval(() => void flush(), FLUSH_EVERY_MS);
  let last = AppState.currentState;
  AppState.addEventListener('change', (state) => {
    if (state === 'background') void flush();
    // Back from the background (not from a system dialog, which only makes it "inactive").
    if (state === 'active' && last === 'background') track('app_open', { cold: false });
    last = state;
  });
}

const once = new Set<string>();

/** `track()` at most once per app run for `key` (a prompt shown on every render, for instance). */
export function trackOnce(key: string, event: AnalyticsEventName, props: AnalyticsProps = {}) {
  if (once.has(key)) return;
  once.add(key);
  track(event, props);
}
