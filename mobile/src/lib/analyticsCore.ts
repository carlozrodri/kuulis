/**
 * Pure helpers of the product analytics (doc 19), kept apart from the module that stores and sends the events
 * so they can be tested without native modules.
 */

/** The events the API accepts (apps/analytics/events.py); anything else is dropped there. */
export type AnalyticsEventName =
  | 'app_open'
  | 'screen_view'
  | 'signup_started'
  | 'signup_completed'
  | 'driver_onboarding_step'
  | 'search_opened'
  | 'quote_shown'
  | 'ride_requested'
  | 'ride_matched'
  | 'ride_completed'
  | 'rating_submitted'
  | 'topup_started'
  | 'topup_completed'
  | 'report_created'
  | 'help_article_viewed'
  | 'update_prompt_shown';

export type AnalyticsProps = Record<string, string | number | boolean>;

export interface QueuedEvent {
  event: AnalyticsEventName;
  occurred_at: string;
  props: AnalyticsProps;
  cell?: string;
}

/** Events kept on the phone while offline; the oldest go first. */
export const MAX_QUEUE = 500;
/** Events per request (the API takes up to 100). */
export const BATCH_SIZE = 100;
/** The API drops events older than a week. */
export const MAX_AGE_MS = 7 * 24 * 3600 * 1000;

/**
 * ~1 km square of a point, never the point itself: "<floor(lat*100)>:<floor(lng*100)>". Same arithmetic as the
 * API (multiplying, not dividing by 0.01, so both sides agree on the border).
 */
export function cellOf(lat: number, lng: number): string | undefined {
  if (!Number.isFinite(lat) || !Number.isFinite(lng)) return undefined;
  return `${Math.floor(lat * 100)}:${Math.floor(lng * 100)}`;
}

const UUID = /[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}/gi;

/** A route without the ids in it ("/reports/3f…" -> "/reports/:id"), at most 64 characters. */
export function screenName(pathname: string): string {
  return (pathname || '/').replace(UUID, ':id').replace(/\d{4,}/g, ':n').slice(0, 64);
}

/** Adds an event, dropping the oldest beyond MAX_QUEUE and anything older than the API keeps. */
export function enqueue(queue: QueuedEvent[], item: QueuedEvent, now = Date.now()): QueuedEvent[] {
  const fresh = queue.filter((e) => now - Date.parse(e.occurred_at) < MAX_AGE_MS);
  fresh.push(item);
  return fresh.length > MAX_QUEUE ? fresh.slice(fresh.length - MAX_QUEUE) : fresh;
}

/** Parses the stored queue, ignoring anything that is not a list of events. */
export function parseQueue(raw: string | null | undefined): QueuedEvent[] {
  if (!raw) return [];
  try {
    const value: unknown = JSON.parse(raw);
    if (!Array.isArray(value)) return [];
    return value.filter(
      (e): e is QueuedEvent => !!e && typeof e === 'object' && typeof e.event === 'string' && typeof e.occurred_at === 'string',
    );
  } catch {
    return [];
  }
}

/**
 * What to do with a batch after posting it: 'sent' (or refused for good: a 4xx other than 429 would fail again),
 * 'retry' (offline, 429 or a server error).
 */
export function batchOutcome(status: number | null): 'sent' | 'retry' {
  if (status === null || status === 429 || status >= 500) return 'retry';
  return 'sent';
}

/** Usage data is on unless the signed-in user switched it off (consent "usage_data", on by default). */
export function usageAllowed(consents: string[] | null | undefined, signedIn: boolean): boolean {
  if (!signedIn || !consents) return true;
  return consents.includes('usage_data');
}
