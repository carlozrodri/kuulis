import { ApiError } from './api';
import { randomId } from './deviceId';
import { createStore } from './store';

/**
 * Actions that must not be lost or done twice when the signal drops (doc 20): the driver's ride steps
 * (llegué / iniciar / terminar), chat messages and ratings. Each one gets an Idempotency-Key when it is
 * created and keeps it on every retry, so the API runs it once however many times it is sent.
 *
 * The queue is kept in a file (it survives closing the app) and sent in order: when the network comes back,
 * when the app returns to the foreground and on a timer with backoff. A refusal from the API (4xx: wrong PIN,
 * the chat closed...) ends the action with that error; no answer or a 5xx keeps it for the next try.
 */
export type OutboxKind = 'ride_step' | 'message' | 'rating';

export type OutboxItem = {
  /** Also the Idempotency-Key. */
  id: string;
  kind: OutboxKind;
  rideId: string;
  path: string;
  body?: unknown;
  createdAt: number;
  attempts: number;
  nextAt: number;
};

export type OutboxResult = { status: 'sent'; data: unknown } | { status: 'queued' };

type Deps = {
  send: (item: OutboxItem) => Promise<unknown>;
  read: () => Promise<string | null>;
  write: (contents: string) => Promise<void>;
  now?: () => number;
};

/** The API keeps idempotency keys for 24 h; older actions are dropped instead of risking a repeat. */
export const OUTBOX_MAX_AGE_MS = 23 * 3600 * 1000;
const MAX_BACKOFF_MS = 30_000;

/** Statuses worth trying again: no answer, timeouts, "still running", rate limits and server errors. */
export function isRetryable(error: unknown): boolean {
  if (!(error instanceof ApiError)) return true; // network failure
  if (error.code === 'idempotency_in_progress') return true;
  return error.status === 408 || error.status === 429 || error.status >= 500;
}

export function backoffMs(attempts: number): number {
  return Math.min(MAX_BACKOFF_MS, 1000 * 2 ** Math.max(0, attempts - 1));
}

type Waiter = { resolve: (result: OutboxResult) => void; reject: (error: unknown) => void };
/** `waited`: a screen was waiting for this answer (it shows the error itself). */
type Listener = (item: OutboxItem, outcome: { data?: unknown; error?: unknown; waited: boolean }) => void;

export function createOutbox(deps: Deps) {
  const now = deps.now ?? Date.now;
  const store = createStore<OutboxItem[]>([]);
  const waiters = new Map<string, Waiter>();
  const listeners = new Set<Listener>();
  let loaded: Promise<void> | null = null;
  let flushing: Promise<void> | null = null;
  let flushAgain = false;

  const persist = () => deps.write(JSON.stringify(store.get())).catch(() => undefined);

  const load = () => {
    loaded ??= (async () => {
      try {
        const raw = await deps.read();
        const saved = raw ? (JSON.parse(raw) as OutboxItem[]) : [];
        const fresh = Array.isArray(saved) ? saved.filter((item) => item?.id && now() - item.createdAt < OUTBOX_MAX_AGE_MS) : [];
        // Items added before the file was read go after the saved ones.
        store.set((current) => [...fresh.filter((s) => !current.some((c) => c.id === s.id)), ...current]);
      } catch {
        // a broken file starts an empty queue
      }
    })();
    return loaded;
  };

  const finish = (item: OutboxItem, outcome: { data?: unknown; error?: unknown }) => {
    store.set((items) => items.filter((i) => i.id !== item.id));
    void persist();
    const waiter = waiters.get(item.id);
    waiters.delete(item.id);
    listeners.forEach((listener) => listener(item, { ...outcome, waited: !!waiter }));
    if (!waiter) return;
    if ('error' in outcome) waiter.reject(outcome.error);
    else waiter.resolve({ status: 'sent', data: outcome.data });
  };

  /** Sends what is due, oldest first; stops at the first action that has to wait (order matters). */
  const flush = (force = false): Promise<void> => {
    if (flushing) {
      // A new action while sending: one more forced round once this one ends.
      if (force) flushAgain = true;
      return flushing;
    }
    flushing = (async () => {
      await load();
      for (;;) {
        const [item] = store.get();
        if (!item) return;
        if (now() - item.createdAt >= OUTBOX_MAX_AGE_MS) {
          finish(item, { error: new ApiError(410, 'outbox_expired', 'Expired') });
          continue;
        }
        if (!force && item.nextAt > now()) return;
        try {
          const data = await deps.send(item);
          finish(item, { data });
        } catch (error) {
          if (!isRetryable(error)) {
            finish(item, { error });
            continue;
          }
          const attempts = item.attempts + 1;
          store.set((items) =>
            items.map((i) => (i.id === item.id ? { ...i, attempts, nextAt: now() + backoffMs(attempts) } : i)),
          );
          void persist();
          return;
        }
      }
    })().finally(() => {
      flushing = null;
      if (flushAgain) {
        flushAgain = false;
        void flush(true);
      }
    });
    return flushing;
  };

  return {
    store,
    load,
    flush,
    /**
     * Queues an action and tries it at once. Resolves `sent` with the API answer, or `queued` after
     * `waitMs` without an answer (it keeps trying); rejects when the API refuses it. `waitMs: Infinity`
     * waits until it is sent or refused.
     */
    async enqueue(
      input: Pick<OutboxItem, 'kind' | 'rideId' | 'path' | 'body'>,
      waitMs = 0,
    ): Promise<OutboxResult> {
      await load();
      const item: OutboxItem = { ...input, id: randomId(), createdAt: now(), attempts: 0, nextAt: now() };
      store.set((items) => [...items, item]);
      await persist();
      const done = new Promise<OutboxResult>((resolve, reject) => waiters.set(item.id, { resolve, reject }));
      void flush(true);
      if (waitMs === Infinity) return done;
      let timer: ReturnType<typeof setTimeout> | undefined;
      const queued = new Promise<OutboxResult>((resolve) => {
        timer = setTimeout(() => {
          // Nobody waits any more: a later answer or refusal goes to `onFinish` only.
          waiters.delete(item.id);
          resolve({ status: 'queued' });
        }, waitMs);
      });
      return Promise.race([done, queued]).finally(() => clearTimeout(timer));
    },
    /** Called for every action that ends (sent or refused), also ones queued before the app restarted. */
    onFinish(listener: Listener) {
      listeners.add(listener);
      return () => {
        listeners.delete(listener);
      };
    },
    /** Signed out: nothing queued may be sent with the next account. */
    async clear() {
      store.set([]);
      waiters.clear();
      await persist();
    },
    /** Time until the next try, for the timer (null when nothing waits). */
    nextDelay(): number | null {
      const [item] = store.get();
      return item ? Math.max(0, item.nextAt - now()) : null;
    },
  };
}

export type Outbox = ReturnType<typeof createOutbox>;
