import { describe, expect, it } from '@jest/globals';

import { channelForNotification, NOTIFICATION_CHANNELS, reportedChannels } from '@/lib/notificationChannels';
import {
  defaultQuietUpdate,
  normalizeClock,
  QUIET_TIME_OPTIONS,
  quietOff,
  usesDefaultQuiet,
  withUpdate,
} from '@/lib/notificationPreferences';
import {
  campaignNotificationId,
  deepLinkTarget,
  groupByDay,
  hrefForNotification,
  isInboxTarget,
  needsPendingRating,
  notificationKind,
} from '@/lib/notificationRoutes';
import type { NotificationPreferences } from '@/lib/types';

const passenger = { role: 'passenger' as const };
const driver = { role: 'driver' as const };
const route = (href: unknown, mode?: 'driver') => ({ kind: 'route', href, ...(mode ? { mode } : {}) });

describe('hrefForNotification: rides', () => {
  it('sends a new offer to driver home, where it shows full screen', () => {
    expect(hrefForNotification({ type: 'ride', event: 'offer', ride_id: 'r1' }, passenger)).toEqual(route('/', 'driver'));
  });

  it('opens the passenger ride screen for assigned, arrived, driver cancelled and no drivers', () => {
    for (const event of ['assigned', 'arrived', 'cancelled_by_driver', 'no_drivers']) {
      expect(hrefForNotification({ type: 'ride', event, ride_id: 'r1' }, driver)).toEqual(
        route({ pathname: '/ride', params: { id: 'r1' } }),
      );
    }
  });

  it('opens the chat for a message', () => {
    expect(hrefForNotification({ type: 'ride', event: 'message', ride_id: 'r1' }, passenger)).toEqual(
      route({ pathname: '/ride/chat', params: { id: 'r1' } }),
    );
  });

  it('opens the rating when that ride waits for one, else the detail', () => {
    const data = { type: 'ride', event: 'completed', ride_id: 'r1' };
    expect(needsPendingRating(data)).toBe(true);
    expect(hrefForNotification(data, { role: 'passenger', pendingRatingRideId: 'r1' })).toEqual(route('/ride/rate'));
    expect(hrefForNotification(data, { role: 'passenger', pendingRatingRideId: 'other' })).toEqual(
      route({ pathname: '/ride/detail', params: { id: 'r1' } }),
    );
    expect(hrefForNotification(data, { role: 'driver', pendingRatingRideId: null })).toEqual(
      route({ pathname: '/ride/detail', params: { id: 'r1' } }),
    );
  });

  it('shows the detail to a driver whose ride was cancelled', () => {
    expect(hrefForNotification({ type: 'ride', event: 'cancelled_by_passenger', ride_id: 'r1' }, passenger)).toEqual(
      route({ pathname: '/ride/detail', params: { id: 'r1' } }),
    );
    expect(hrefForNotification({ type: 'ride', event: 'cancelled_by_admin', ride_id: 'r1' }, driver)).toEqual(
      route({ pathname: '/ride/detail', params: { id: 'r1' } }),
    );
    expect(hrefForNotification({ type: 'ride', event: 'cancelled_by_admin', ride_id: 'r1' }, passenger)).toEqual(
      route({ pathname: '/ride', params: { id: 'r1' } }),
    );
  });

  it('uses the mode for unknown ride events', () => {
    expect(hrefForNotification({ type: 'ride', event: 'started', ride_id: 'r1' }, driver)).toEqual(
      route({ pathname: '/drive', params: { id: 'r1' } }),
    );
    expect(hrefForNotification({ type: 'ride', event: 'started' }, driver)).toEqual(route('/'));
  });
});

describe('hrefForNotification: quality (doc 15)', () => {
  it('opens Mi calidad for drivers and home for a paused passenger', () => {
    expect(hrefForNotification({ type: 'quality', event: 'paused', role: 'driver' }, passenger)).toEqual(
      route('/driver/quality', 'driver'),
    );
    expect(hrefForNotification({ type: 'quality', event: 'warn', role: 'driver' }, driver)).toEqual(route('/driver/quality', 'driver'));
    expect(hrefForNotification({ type: 'quality', event: 'paused', role: 'passenger' }, driver)).toEqual(route('/'));
    // Without a role: the mode decides.
    expect(hrefForNotification({ type: 'quality' }, driver)).toEqual(route('/driver/quality', 'driver'));
    expect(hrefForNotification({ type: 'quality' }, passenger)).toEqual(route('/'));
    expect(notificationKind({ type: 'quality', event: 'low_priority' })).toBe('quality');
  });

  it('opens the passenger ride screen when the driver cancelled or the passenger did not show up', () => {
    for (const event of ['reassigning', 'no_show']) {
      expect(hrefForNotification({ type: 'ride', event, ride_id: 'r1' }, driver)).toEqual(
        route({ pathname: '/ride', params: { id: 'r1' } }),
      );
    }
  });
});

describe('hrefForNotification: account and money', () => {
  it('routes wallet pushes to the wallet', () => {
    for (const event of ['top_up_credited', 'top_up_rejected', 'transfer_received', 'adjustment', 'promo_credit']) {
      expect(hrefForNotification({ type: 'wallet', event }, driver)).toEqual(route('/wallet', 'driver'));
    }
  });

  it('routes fees to pay to the wallet and the rest to the fee list', () => {
    expect(hrefForNotification({ type: 'subscription', event: 'fee_overdue' }, driver)).toEqual(route('/wallet', 'driver'));
    expect(hrefForNotification({ type: 'subscription', event: 'fee_due_soon' }, driver)).toEqual(route('/wallet', 'driver'));
    expect(hrefForNotification({ type: 'subscription', event: 'fee_paid' }, driver)).toEqual(route('/wallet/charges', 'driver'));
    expect(hrefForNotification({ type: 'subscription', event: 'fee_waived' }, driver)).toEqual(route('/wallet/charges', 'driver'));
  });

  it('routes referral, account and driver application pushes', () => {
    expect(hrefForNotification({ type: 'referral', event: 'reward' }, passenger)).toEqual(route('/profile/invite'));
    expect(hrefForNotification({ type: 'account', event: 'suspended' }, passenger)).toEqual(route('/'));
    expect(hrefForNotification({ type: 'driver_status', event: 'approved', status: 'approved' }, passenger)).toEqual(
      route('/', 'driver'),
    );
  });

  it('reuses the support and verification links', () => {
    expect(hrefForNotification({ type: 'support', event: 'reply', report_id: 'rep1' }, passenger)).toEqual(
      route({ pathname: '/reports/[id]', params: { id: 'rep1' } }),
    );
    expect(hrefForNotification({ type: 'lost_item', event: 'lost_item_asked', ride_id: 'r1' }, driver)).toEqual(
      route({ pathname: '/ride/lost-item', params: { id: 'r1' } }),
    );
    expect(hrefForNotification({ type: 'support', event: 'closed' }, passenger)).toEqual(route('/reports'));
    expect(hrefForNotification({ type: 'driver_document', event: 'document_expiring' }, driver)).toEqual(
      route({ pathname: '/driver/my-documents' }),
    );
  });

  it('opens the ride of a safety check-in', () => {
    const data = { type: 'safety', event: 'check_in', alert_id: 'a1', ride_id: 'r1' };
    expect(hrefForNotification(data, passenger)).toEqual(route({ pathname: '/ride', params: { id: 'r1' } }));
    expect(hrefForNotification(data, driver)).toEqual(route({ pathname: '/drive', params: { id: 'r1' } }));
  });
});

describe('hrefForNotification: campaigns and the rest', () => {
  it('opens an app path in the app and an https link in the browser', () => {
    expect(hrefForNotification({ type: 'campaign', campaign_id: 'c', notification_id: 'n1', deep_link: '/wallet' }, driver)).toEqual(
      route('/wallet'),
    );
    expect(
      hrefForNotification({ type: 'campaign', notification_id: 'n1', deep_link: 'https://kuulis.app/promo' }, passenger),
    ).toEqual({ kind: 'url', url: 'https://kuulis.app/promo' });
  });

  it('falls back to the inbox without a usable link', () => {
    expect(isInboxTarget(hrefForNotification({ type: 'campaign', notification_id: 'n1' }, passenger))).toBe(true);
    expect(isInboxTarget(hrefForNotification({ type: 'campaign', deep_link: 'javascript:alert(1)' }, passenger))).toBe(true);
    expect(isInboxTarget(hrefForNotification({ type: 'admin_message' }, passenger))).toBe(true);
    expect(isInboxTarget(hrefForNotification(null, passenger))).toBe(true);
  });

  it('reads inbox items, whose link sits next to the data', () => {
    const item = { id: 'n1', data: { type: 'campaign', campaign_id: 'c' }, deep_link: '/profile/invite' };
    expect(hrefForNotification(item, passenger)).toEqual(route('/profile/invite'));
    expect(hrefForNotification({ id: 'n2', data: { type: 'ride', event: 'message', ride_id: 'r9' } }, passenger)).toEqual(
      route({ pathname: '/ride/chat', params: { id: 'r9' } }),
    );
  });

  it('knows which inbox item a campaign push is', () => {
    expect(campaignNotificationId({ type: 'campaign', notification_id: 'n1' })).toBe('n1');
    expect(campaignNotificationId({ type: 'wallet', notification_id: 'n1' })).toBeNull();
  });

  it('accepts only app paths and https links', () => {
    expect(deepLinkTarget('/help')).toEqual(route('/help'));
    expect(deepLinkTarget('//evil.com')).toBeNull();
    expect(deepLinkTarget('http://kuulis.app')).toBeNull();
    expect(deepLinkTarget('kuulis://wallet')).toBeNull();
    expect(deepLinkTarget('')).toBeNull();
    expect(deepLinkTarget(42)).toBeNull();
  });
});

describe('notificationKind', () => {
  it('picks an icon family per type and category', () => {
    expect(notificationKind({ type: 'ride', event: 'assigned' })).toBe('ride');
    expect(notificationKind({ type: 'wallet' })).toBe('wallet');
    expect(notificationKind({ type: 'subscription' })).toBe('subscription');
    expect(notificationKind({ type: 'report' })).toBe('support');
    expect(notificationKind({ type: 'safety' })).toBe('safety');
    expect(notificationKind({ data: { type: 'campaign' } })).toBe('campaign');
    expect(notificationKind({}, 'marketing')).toBe('campaign');
    expect(notificationKind({ type: 'account' })).toBe('account');
    expect(notificationKind({ type: 'driver_document' })).toBe('documents');
    expect(notificationKind({ type: 'referral' })).toBe('referral');
    expect(notificationKind({})).toBe('general');
  });
});

describe('groupByDay', () => {
  const at = (y: number, m: number, d: number, h = 10) => new Date(y, m - 1, d, h).toISOString();
  const now = new Date(2026, 9, 13, 15);

  it('groups newest first into today, yesterday and older dates', () => {
    const items = [
      { id: 'a', created_at: at(2026, 10, 13, 14) },
      { id: 'b', created_at: at(2026, 10, 13, 1) },
      { id: 'c', created_at: at(2026, 10, 12, 23) },
      { id: 'd', created_at: at(2026, 10, 1) },
      { id: 'e', created_at: 'not a date' },
    ];
    const groups = groupByDay(items, now);
    expect(groups.map((g) => g.key)).toEqual(['2026-10-13', '2026-10-12', '2026-10-01']);
    expect(groups[0].label).toEqual({ kind: 'today' });
    expect(groups[0].items.map((i) => i.id)).toEqual(['a', 'b']);
    expect(groups[1].label).toEqual({ kind: 'yesterday' });
    expect(groups[2].label.kind).toBe('date');
  });

  it('handles yesterday across a month change', () => {
    const groups = groupByDay([{ created_at: at(2026, 9, 30) }], new Date(2026, 9, 1, 8));
    expect(groups[0].label).toEqual({ kind: 'yesterday' });
  });

  it('returns nothing for an empty inbox', () => {
    expect(groupByDay([], now)).toEqual([]);
  });
});

describe('channels', () => {
  it('creates the doc 14 channels, without the sound one', () => {
    const ids = NOTIFICATION_CHANNELS.map((c) => c.id);
    expect(ids).toEqual(['ride_offer', 'ride_updates', 'safety', 'account', 'marketing', 'default']);
    expect(ids).not.toContain('ride_offer_sound');
    expect(NOTIFICATION_CHANNELS.find((c) => c.id === 'ride_offer')?.importance).toBe('max');
    expect(NOTIFICATION_CHANNELS.find((c) => c.id === 'marketing')?.importance).toBe('low');
  });

  it('picks the channel the server would use', () => {
    expect(channelForNotification({ type: 'ride', event: 'offer' })).toBe('ride_offer');
    expect(channelForNotification({ type: 'ride', event: 'offer' }, ['ride_offer_sound', 'ride_offer'])).toBe('ride_offer_sound');
    expect(channelForNotification({ type: 'ride', event: 'assigned' })).toBe('ride_updates');
    expect(channelForNotification({ type: 'safety' })).toBe('safety');
    expect(channelForNotification({ type: 'campaign' })).toBe('marketing');
    expect(channelForNotification({ type: 'support' })).toBe('account');
    expect(channelForNotification({ type: 'wallet' })).toBe('account');
    expect(channelForNotification({ type: 'ride', event: 'offer' }, ['default'])).toBe('default');
  });

  it('reports channels only on Android', () => {
    expect(reportedChannels('android', ['ride_offer', 'default', 'default'])).toEqual(['ride_offer', 'default']);
    expect(reportedChannels('ios', ['default'])).toEqual([]);
  });
});

describe('notification preferences', () => {
  const prefs: NotificationPreferences = {
    marketing_push: true,
    marketing_email: true,
    quiet_start: '21:00',
    quiet_end: '08:00',
    default_quiet_start: '21:00',
    default_quiet_end: '08:00',
  };

  it('offers every half hour', () => {
    expect(QUIET_TIME_OPTIONS).toHaveLength(48);
    expect(QUIET_TIME_OPTIONS[0]).toBe('00:00');
    expect(QUIET_TIME_OPTIONS[43]).toBe('21:30');
  });

  it('normalizes clock values', () => {
    expect(normalizeClock('9:00')).toBe('09:00');
    expect(normalizeClock('21:00:00')).toBe('21:00');
    expect(normalizeClock('25:00')).toBeNull();
    expect(normalizeClock(null)).toBeNull();
  });

  it('knows the default window and how to go back to it', () => {
    expect(usesDefaultQuiet(prefs)).toBe(true);
    const changed = withUpdate(prefs, { quiet_start: '22:30' });
    expect(changed.quiet_start).toBe('22:30');
    expect(usesDefaultQuiet(changed)).toBe(false);
    expect(defaultQuietUpdate(changed)).toEqual({ quiet_start: '21:00', quiet_end: '08:00' });
  });

  it('treats the same start and end as no quiet hours', () => {
    expect(quietOff('22:00', '22:00')).toBe(true);
    expect(quietOff('21:00', '08:00')).toBe(false);
  });
});
