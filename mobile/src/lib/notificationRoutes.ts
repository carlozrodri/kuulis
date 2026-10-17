/**
 * Doc 14: where tapping a notification goes, for every push type and for the inbox. Pure (no navigation here):
 * the opener in features/notifications does the side effects.
 */
import type { Href } from 'expo-router';

import { supportHrefOf } from './support';
import { verificationHrefOf } from './verification';

export type NotificationRole = 'passenger' | 'driver';

export interface NotificationContext {
  /** The mode the app is in (decides between the passenger and the driver screen when the push does not say). */
  role: NotificationRole | null | undefined;
  /** The ride waiting for this user's rating, if any (GET /rides/pending-rating). */
  pendingRatingRideId?: string | null;
}

export type NotificationTarget =
  /** `mode`: the screen only exists in that mode (driver home, wallet), so the app switches to it first. */
  | { kind: 'route'; href: Href; mode?: NotificationRole }
  | { kind: 'url'; url: string };

export const INBOX_HREF = '/notifications';
const INBOX: NotificationTarget = { kind: 'route', href: INBOX_HREF };

type Fields = Record<string, unknown>;

/** Push data is flat ({type, event, ...}); realtime events and inbox items may wrap it in `data`. */
function fieldsOf(payload: unknown): Fields {
  if (!payload || typeof payload !== 'object') return {};
  const record = payload as Fields;
  if (typeof record.type === 'string' || typeof record.kind === 'string') return record;
  const inner = record.data;
  return inner && typeof inner === 'object' ? { ...(inner as Fields), deep_link: record.deep_link ?? (inner as Fields).deep_link } : record;
}

const str = (fields: Fields, key: string) => {
  const value = fields[key];
  return typeof value === 'string' && value ? value : null;
};

/** The push type ("ride", "wallet", "campaign", ...), or null. */
export function notificationType(payload: unknown): string | null {
  const fields = fieldsOf(payload);
  return str(fields, 'type') ?? str(fields, 'kind');
}

export const notificationEvent = (payload: unknown) => str(fieldsOf(payload), 'event');

/**
 * A campaign or admin deep link: an app path ("/wallet") opens in the app, an https link in the browser.
 * Anything else (other schemes, "//host", plain http) is ignored.
 */
export function deepLinkTarget(link: unknown): NotificationTarget | null {
  if (typeof link !== 'string') return null;
  const value = link.trim();
  if (!value) return null;
  if (value.startsWith('/') && !value.startsWith('//') && !/\s/.test(value)) return { kind: 'route', href: value as Href };
  if (/^https:\/\/[^\s/]+/i.test(value)) return { kind: 'url', url: value };
  return null;
}

/** The inbox item a campaign push stands for: it is marked read (counts as opened) when tapped. */
export function campaignNotificationId(payload: unknown): string | null {
  const fields = fieldsOf(payload);
  return notificationType(payload) === 'campaign' ? str(fields, 'notification_id') : null;
}

/** Doc 21: where a demand push points ({type: "demand", name, lat, lng}), or null. */
export function demandPushPoint(payload: unknown): { lat: number; lng: number } | null {
  if (notificationType(payload) !== 'demand') return null;
  const fields = fieldsOf(payload);
  const lat = Number(fields.lat);
  const lng = Number(fields.lng);
  if (fields.lat == null || fields.lng == null || !Number.isFinite(lat) || !Number.isFinite(lng)) return null;
  return { lat, lng };
}

/** Ride completed: the screen depends on whether a rating is pending, so the opener asks first. */
export const needsPendingRating = (payload: unknown) =>
  notificationType(payload) === 'ride' && notificationEvent(payload) === 'completed';

// Doc 15: "reassigning" (the driver cancelled, looking for another) and "no_show" are passenger events too.
const PASSENGER_RIDE_EVENTS = new Set(['assigned', 'arrived', 'cancelled_by_driver', 'no_drivers', 'reassigning', 'no_show']);
const DRIVER_RIDE_EVENTS = new Set(['offer', 'cancelled_by_passenger']);
const FEE_TO_PAY = new Set(['fee_pending', 'fee_due_soon', 'fee_overdue']);

function rideTarget(fields: Fields, event: string | null, context: NotificationContext): NotificationTarget {
  const rideId = str(fields, 'ride_id');
  // A new offer shows full screen over any screen in driver mode: home is where the driver waits for it.
  if (event === 'offer') return { kind: 'route', href: '/', mode: 'driver' };
  if (!rideId) return { kind: 'route', href: '/' };
  if (event === 'message') return { kind: 'route', href: { pathname: '/ride/chat', params: { id: rideId } } };
  if (event === 'completed') {
    return context.pendingRatingRideId === rideId
      ? { kind: 'route', href: '/ride/rate' }
      : { kind: 'route', href: { pathname: '/ride/detail', params: { id: rideId } } };
  }
  const role: NotificationRole = PASSENGER_RIDE_EVENTS.has(event ?? '')
    ? 'passenger'
    : DRIVER_RIDE_EVENTS.has(event ?? '')
      ? 'driver'
      : (context.role ?? 'passenger');
  // The passenger's ride screen also shows cancellations and "no drivers" with "Pedir otra"; a driver whose
  // ride was cancelled sees the ride's detail.
  if (role === 'passenger') return { kind: 'route', href: { pathname: '/ride', params: { id: rideId } } };
  if (event?.startsWith('cancelled')) return { kind: 'route', href: { pathname: '/ride/detail', params: { id: rideId } } };
  return { kind: 'route', href: { pathname: '/drive', params: { id: rideId } } };
}

/** Where a notification (push data, or an inbox item with its `deep_link`) takes the user. */
export function hrefForNotification(payload: unknown, context: NotificationContext): NotificationTarget {
  const fields = fieldsOf(payload);
  const type = notificationType(payload);
  const event = str(fields, 'event');

  // Doc 13: support answers open the conversation, lost items the ride's lost item screen.
  const support = supportHrefOf(fields);
  if (support) return { kind: 'route', href: support };
  // Doc 12: a selfie request or an expiring document opens where it is solved.
  const verification = verificationHrefOf(fields);
  if (verification) return { kind: 'route', href: verification };

  switch (type) {
    case 'ride':
      return rideTarget(fields, event, context);
    case 'wallet':
    case 'promo_credit':
      return { kind: 'route', href: '/wallet', mode: 'driver' };
    case 'subscription':
      // Something to pay: the wallet (balance, top up and the fee card). Otherwise the list of fees
      // (fee_paid, fee_waived and doc 17's fee_reduced).
      return FEE_TO_PAY.has(event ?? '')
        ? { kind: 'route', href: '/wallet', mode: 'driver' }
        : { kind: 'route', href: '/wallet/charges', mode: 'driver' };
    case 'referral':
      return { kind: 'route', href: '/profile/invite' };
    case 'account':
      // Home shows the suspension panel (or nothing once it is lifted).
      return { kind: 'route', href: '/' };
    case 'support':
    case 'report':
      return { kind: 'route', href: '/reports' };
    case 'safety': {
      const rideId = str(fields, 'ride_id');
      if (!rideId) return { kind: 'route', href: '/' };
      return context.role === 'driver'
        ? { kind: 'route', href: { pathname: '/drive', params: { id: rideId } } }
        : { kind: 'route', href: { pathname: '/ride', params: { id: rideId } } };
    }
    case 'quality': {
      // Doc 15: a pause or a warning about the rates. Drivers see "Mi calidad"; a paused passenger, home.
      const role = str(fields, 'role') ?? context.role;
      return role === 'driver' ? { kind: 'route', href: '/driver/quality', mode: 'driver' } : { kind: 'route', href: '/' };
    }
    case 'risk':
      // Doc 16: a mock location app took the driver offline; home says why and goes online again.
      return { kind: 'route', href: '/', mode: 'driver' };
    case 'demand':
      // Doc 21: "Mucha demanda en Chacao" opens the driver home (the drive map), with the demand layer there.
      return { kind: 'route', href: '/', mode: 'driver' };
    case 'driver_status':
    case 'driver_document':
      // Driver home shows the application or the documents that need something.
      return { kind: 'route', href: '/', mode: 'driver' };
    default:
      // Campaigns and admin messages: their link, else the inbox.
      return deepLinkTarget(fields.deep_link) ?? INBOX;
  }
}

/** True when the target is the inbox itself (tapping an item there then just marks it read). */
export const isInboxTarget = (target: NotificationTarget) => target.kind === 'route' && target.href === INBOX_HREF;

/** The icon family of an inbox item. */
export type NotificationKind =
  | 'ride'
  | 'wallet'
  | 'subscription'
  | 'support'
  | 'safety'
  | 'campaign'
  | 'account'
  | 'documents'
  | 'referral'
  | 'quality'
  | 'general';

export function notificationKind(payload: unknown, category?: string | null): NotificationKind {
  const type = notificationType(payload);
  if (type === 'campaign' || category === 'marketing') return 'campaign';
  if (type === 'safety' || category === 'safety') return 'safety';
  if (type === 'support' || type === 'lost_item' || type?.startsWith('report') || category === 'support') return 'support';
  if (type === 'ride' || type?.startsWith('ride') || type === 'demand') return 'ride';
  if (type === 'wallet' || type === 'promo_credit') return 'wallet';
  if (type?.startsWith('subscription')) return 'subscription';
  if (type?.startsWith('driver_')) return 'documents';
  if (type === 'referral') return 'referral';
  if (type === 'quality') return 'quality';
  if (type?.startsWith('account') || type === 'risk') return 'account';
  return 'general';
}

// ── Inbox grouping ──

export type DayLabel = { kind: 'today' } | { kind: 'yesterday' } | { kind: 'date'; date: Date };

export interface DayGroup<T> {
  /** Local calendar day, YYYY-MM-DD. */
  key: string;
  label: DayLabel;
  items: T[];
}

const pad = (n: number) => String(n).padStart(2, '0');
const dayKey = (date: Date) => `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}`;

/** Groups items (newest first, as the API returns them) by local day: Hoy, Ayer, then the date. */
export function groupByDay<T extends { created_at: string }>(items: readonly T[], now: Date = new Date()): DayGroup<T>[] {
  const today = dayKey(now);
  const yesterday = dayKey(new Date(now.getFullYear(), now.getMonth(), now.getDate() - 1));
  const groups: DayGroup<T>[] = [];
  const byKey = new Map<string, DayGroup<T>>();
  for (const item of items) {
    const date = new Date(item.created_at);
    if (Number.isNaN(date.getTime())) continue;
    const key = dayKey(date);
    let group = byKey.get(key);
    if (!group) {
      const label: DayLabel =
        key === today ? { kind: 'today' } : key === yesterday ? { kind: 'yesterday' } : { kind: 'date', date };
      group = { key, label, items: [] };
      byKey.set(key, group);
      groups.push(group);
    }
    group.items.push(item);
  }
  return groups;
}
