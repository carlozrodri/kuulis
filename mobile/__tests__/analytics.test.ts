import { describe, expect, it } from '@jest/globals';

import {
  batchOutcome,
  cellOf,
  enqueue,
  MAX_AGE_MS,
  MAX_QUEUE,
  parseQueue,
  screenName,
  usageAllowed,
  type QueuedEvent,
} from '@/lib/analyticsCore';

const event = (at: number, name: QueuedEvent['event'] = 'app_open'): QueuedEvent => ({
  event: name,
  occurred_at: new Date(at).toISOString(),
  props: {},
});

describe('product analytics', () => {
  it('turns a place into its ~1 km cell, as the API does', () => {
    expect(cellOf(10.49, -66.88)).toBe('1049:-6688');
    expect(cellOf(10.4999, -66.8801)).toBe('1049:-6689');
    expect(cellOf(Number.NaN, 1)).toBeUndefined();
  });

  it('strips ids from screen names', () => {
    expect(screenName('/reports/0b5f7c3e-6a0f-4e8e-9d2a-1c3b4d5e6f70')).toBe('/reports/:id');
    expect(screenName('/help/article/12345')).toBe('/help/article/:n');
    expect(screenName('')).toBe('/');
  });

  it('keeps a bounded queue without stale events', () => {
    const now = Date.now();
    const old = event(now - MAX_AGE_MS - 1);
    expect(enqueue([old], event(now), now)).toHaveLength(1);
    const full = Array.from({ length: MAX_QUEUE }, (_, i) => event(now - i));
    const next = enqueue(full, event(now, 'search_opened'), now);
    expect(next).toHaveLength(MAX_QUEUE);
    expect(next[next.length - 1].event).toBe('search_opened');
  });

  it('reads a stored queue defensively', () => {
    expect(parseQueue(null)).toEqual([]);
    expect(parseQueue('not json')).toEqual([]);
    expect(parseQueue('{"a":1}')).toEqual([]);
    expect(parseQueue(JSON.stringify([event(0), { nope: true }]))).toHaveLength(1);
  });

  it('retries only what can succeed later', () => {
    expect(batchOutcome(202)).toBe('sent');
    expect(batchOutcome(422)).toBe('sent');
    expect(batchOutcome(429)).toBe('retry');
    expect(batchOutcome(503)).toBe('retry');
    expect(batchOutcome(null)).toBe('retry');
  });

  it('follows the usage_data consent, on by default', () => {
    expect(usageAllowed(['usage_data'], true)).toBe(true);
    expect(usageAllowed([], true)).toBe(false);
    expect(usageAllowed(undefined, true)).toBe(true);
    expect(usageAllowed([], false)).toBe(true);
  });
});
