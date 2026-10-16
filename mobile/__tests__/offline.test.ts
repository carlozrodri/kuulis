import { describe, expect, it, jest } from '@jest/globals';

import { ApiError } from '@/lib/api';
import { backoffMs, createOutbox, isRetryable, OUTBOX_MAX_AGE_MS, type OutboxItem } from '@/lib/outbox';
import {
  createFilePersister,
  isPersistedKey,
  shouldPersistQuery,
} from '@/lib/queryPersistence';
import { gpsLevel, signalLevel } from '@/lib/signal';

const network = () => new TypeError('Network request failed');

function memoryFile(initial: string | null = null) {
  let contents = initial;
  return {
    read: async () => contents,
    write: async (next: string) => {
      contents = next;
    },
    get: () => contents,
  };
}

const step = { kind: 'ride_step' as const, rideId: 'r1', path: '/rides/r1/complete' };

describe('outbox (doc 20)', () => {
  it('retries only when there was no real answer', () => {
    expect(isRetryable(network())).toBe(true);
    expect(isRetryable(new ApiError(503, 'service_unavailable', ''))).toBe(true);
    expect(isRetryable(new ApiError(429, 'rate_limited', ''))).toBe(true);
    expect(isRetryable(new ApiError(409, 'idempotency_in_progress', ''))).toBe(true);
    expect(isRetryable(new ApiError(400, 'pin_invalid', ''))).toBe(false);
    expect(isRetryable(new ApiError(409, 'ride_invalid_transition', ''))).toBe(false);
  });

  it('backs off up to 30 s', () => {
    expect([1, 2, 3, 6, 10].map(backoffMs)).toEqual([1000, 2000, 4000, 30_000, 30_000]);
  });

  it('keeps the same key on every try until the API answers', async () => {
    let now = 1_000_000;
    const keys: string[] = [];
    let online = false;
    const send = jest.fn(async (item: OutboxItem) => {
      keys.push(item.id);
      if (!online) throw network();
      return { id: 'r1', status: 'completed' };
    });
    const file = memoryFile();
    const outbox = createOutbox({ send, ...file, now: () => now });

    const result = outbox.enqueue(step, Infinity);
    await outbox.flush(); // the immediate try failed: waiting for the backoff
    expect(outbox.store.get()).toHaveLength(1);
    expect(JSON.parse(file.get() ?? '[]')).toHaveLength(1);

    now += 60_000; // a minute without signal
    online = true;
    await outbox.flush();
    await expect(result).resolves.toEqual({ status: 'sent', data: { id: 'r1', status: 'completed' } });
    expect(new Set(keys).size).toBe(1);
    expect(outbox.store.get()).toEqual([]);
  });

  it('answers "queued" after the wait and still sends it later', async () => {
    let online = false;
    const outbox = createOutbox({
      send: async () => {
        if (!online) throw network();
        return { ok: true };
      },
      ...memoryFile(),
    });
    const finished = jest.fn();
    outbox.onFinish(finished);
    await expect(outbox.enqueue({ kind: 'rating', rideId: 'r1', path: '/rides/r1/rating' }, 10)).resolves.toEqual({
      status: 'queued',
    });
    online = true;
    await outbox.flush(true);
    expect(finished).toHaveBeenCalledWith(expect.objectContaining({ kind: 'rating' }), { data: { ok: true }, waited: false });
  });

  it('ends an action the API refuses and goes on with the next one', async () => {
    const outbox = createOutbox({
      send: async (item) => {
        if (item.kind === 'ride_step') throw new ApiError(400, 'pin_invalid', 'Wrong PIN');
        return { id: 'm1' };
      },
      ...memoryFile(),
    });
    const refused = outbox.enqueue(step, Infinity);
    const message = outbox.enqueue({ kind: 'message', rideId: 'r1', path: '/rides/r1/messages', body: { text: 'Hola' } }, Infinity);
    await expect(refused).rejects.toMatchObject({ code: 'pin_invalid' });
    await expect(message).resolves.toEqual({ status: 'sent', data: { id: 'm1' } });
  });

  it('sends in order: nothing passes an action that is waiting', async () => {
    const sent: string[] = [];
    let online = false;
    const outbox = createOutbox({
      send: async (item) => {
        if (!online) throw network();
        sent.push(item.path);
        return {};
      },
      ...memoryFile(),
    });
    void outbox.enqueue({ ...step, path: '/rides/r1/arrive' }, 0);
    void outbox.enqueue({ ...step, path: '/rides/r1/start' }, 0);
    await outbox.flush();
    online = true;
    await outbox.flush(true);
    expect(sent).toEqual(['/rides/r1/arrive', '/rides/r1/start']);
  });

  it('picks up what was queued before the app closed, and drops what is too old', async () => {
    const now = 5_000_000_000;
    const saved: OutboxItem[] = [
      { ...step, id: 'old', createdAt: now - OUTBOX_MAX_AGE_MS - 1, attempts: 3, nextAt: 0 },
      { ...step, id: 'k1', createdAt: now - 60_000, attempts: 1, nextAt: 0 },
    ];
    const send = jest.fn(async (_item: OutboxItem) => ({}));
    const outbox = createOutbox({ send, ...memoryFile(JSON.stringify(saved)), now: () => now });
    await outbox.flush();
    expect(send).toHaveBeenCalledTimes(1);
    expect(send.mock.calls[0][0]).toMatchObject({ id: 'k1' });
  });

  it('forgets everything on sign out', async () => {
    const file = memoryFile();
    const outbox = createOutbox({ send: async () => Promise.reject(network()), ...file });
    void outbox.enqueue(step, 0);
    await outbox.flush();
    await outbox.clear();
    expect(outbox.store.get()).toEqual([]);
    expect(file.get()).toBe('[]');
  });
});

describe('offline cache (doc 20)', () => {
  it('keeps history, ride details, wallet and profile data, never the active ride', () => {
    expect(isPersistedKey(['rides', 'history', 'passenger'])).toBe(true);
    expect(isPersistedKey(['rides', 'detail', 'r1'])).toBe(true);
    expect(isPersistedKey(['wallet', 'me', 'entries'])).toBe(true);
    expect(isPersistedKey(['drivers', 'me'])).toBe(true);
    expect(isPersistedKey(['rides', 'active'])).toBe(false);
    expect(isPersistedKey(['notifications'])).toBe(false);
  });

  it('saves only answers that loaded', () => {
    const query = (status: 'success' | 'error' | 'pending') =>
      ({ queryKey: ['wallet', 'me'], state: { status } }) as unknown as Parameters<typeof shouldPersistQuery>[0];
    expect(shouldPersistQuery(query('success'))).toBe(true);
    expect(shouldPersistQuery(query('error'))).toBe(false);
    expect(shouldPersistQuery(query('pending'))).toBe(false);
  });

  it('writes the cache at most once per throttle window and reads it back', async () => {
    jest.useFakeTimers();
    const file = memoryFile();
    const write = jest.fn((_name: string, contents: string) => file.write(contents));
    const persister = createFilePersister({ read: file.read, write }, 1000);
    const client = (n: number) => ({ timestamp: n, buster: 'b', clientState: { queries: [], mutations: [] } });
    await persister.persistClient(client(1));
    await persister.persistClient(client(2));
    expect(write).not.toHaveBeenCalled();
    jest.advanceTimersByTime(1000);
    jest.useRealTimers();
    await persister.flush();
    expect(write).toHaveBeenCalledTimes(1);
    expect(await persister.restoreClient()).toEqual(client(2));
    await persister.removeClient();
    expect(await persister.restoreClient()).toBeUndefined();
  });
});

describe('signal and GPS chips (doc 20)', () => {
  const net = (connected: boolean | null, extra: object = {}) => ({ isConnected: connected, isInternetReachable: connected, ...extra });

  it('rates the data signal', () => {
    expect(signalLevel(net(false), 'closed')).toBe('none');
    expect(signalLevel(net(true), 'connecting')).toBe('weak');
    expect(signalLevel(net(true, { type: 'cellular', details: { cellularGeneration: '2g' } }), 'open')).toBe('weak');
    expect(signalLevel(net(true, { type: 'cellular', details: { cellularGeneration: '4g' } }), 'open')).toBe('good');
    expect(signalLevel(net(null), 'open')).toBe('good');
  });

  it('rates the GPS fix by accuracy and age', () => {
    const now = 100_000;
    expect(gpsLevel(null, now)).toBe('none');
    expect(gpsLevel({ accuracy: 8, timestamp: now - 2000 }, now)).toBe('good');
    expect(gpsLevel({ accuracy: 60, timestamp: now - 2000 }, now)).toBe('weak');
    expect(gpsLevel({ accuracy: 300, timestamp: now }, now)).toBe('none');
    expect(gpsLevel({ accuracy: 5, timestamp: now - 60_000 }, now)).toBe('none');
  });
});
