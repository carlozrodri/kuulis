import type { Query, QueryClient, QueryKey } from '@tanstack/react-query';
import type { PersistedClient, Persister } from '@tanstack/react-query-persist-client';

import { localFile } from './localFile';

/**
 * Offline cache (doc 20): what the app showed last (ride history and details, wallet, profile data) is
 * saved to a file and shown again when the app opens without signal, until the network answers.
 * The active ride is left out on purpose: an old copy could open a ride that already ended.
 */
const FILE = 'query-cache.json';
/** Saved data older than this is thrown away. */
export const PERSIST_MAX_AGE = 7 * 24 * 3600 * 1000;
/** Bumped when the shape of the saved data changes, so old files are ignored. */
export const PERSIST_BUSTER = 'doc20-v1';
const WRITE_THROTTLE_MS = 1000;

/** Query key prefixes saved to the phone. */
export const PERSISTED_KEYS: readonly (readonly string[])[] = [
  ['rides', 'history'],
  ['rides', 'detail'],
  ['rides', 'passenger-stats'],
  ['rides', 'driver-stats'],
  ['wallet'],
  ['drivers', 'me'],
  ['users', 'me', 'places'],
  ['referrals', 'me'],
  ['config', 'public'],
];

function startsWith(key: QueryKey, prefix: readonly string[]): boolean {
  return prefix.every((part, index) => key[index] === part);
}

export function isPersistedKey(key: QueryKey): boolean {
  return PERSISTED_KEYS.some((prefix) => startsWith(key, prefix));
}

/** Only good answers of the listed queries; an error or a half-loaded query is not worth keeping. */
export function shouldPersistQuery(query: Pick<Query, 'queryKey' | 'state'>): boolean {
  return query.state.status === 'success' && isPersistedKey(query.queryKey);
}

/** Saved queries must outlive the default 5 minutes in memory, or they would vanish from the file too. */
export function keepPersistedQueries(queryClient: QueryClient) {
  for (const prefix of PERSISTED_KEYS) queryClient.setQueryDefaults(prefix, { gcTime: PERSIST_MAX_AGE });
}

type FileStore = Pick<typeof localFile, 'read' | 'write'>;

/** A persister on the app's document folder (no native module needed: expo-file-system is in the build). */
export function createFilePersister(store: FileStore = localFile, throttleMs = WRITE_THROTTLE_MS): Persister & {
  flush: () => Promise<void>;
} {
  let pending: PersistedClient | null = null;
  let timer: ReturnType<typeof setTimeout> | null = null;

  const flush = async () => {
    if (timer) clearTimeout(timer);
    timer = null;
    const next = pending;
    pending = null;
    if (next) await store.write(FILE, JSON.stringify(next));
  };

  return {
    persistClient(client) {
      pending = client;
      timer ??= setTimeout(() => void flush(), throttleMs);
    },
    async restoreClient() {
      const raw = await store.read(FILE);
      if (!raw) return undefined;
      try {
        return JSON.parse(raw) as PersistedClient;
      } catch {
        return undefined;
      }
    },
    async removeClient() {
      if (timer) clearTimeout(timer);
      timer = null;
      pending = null;
      await store.write(FILE, '');
    },
    flush,
  };
}

export const queryPersister = createFilePersister();
