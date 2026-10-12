import { describe, expect, it } from '@jest/globals';

import {
  type Announcement,
  ctaTarget,
  DEFAULT_FLAGS,
  emergencyNumberFrom,
  flagValue,
  formatEta,
  localize,
  locationIntervalMs,
  maintenanceNotice,
  type Notice,
  parseAnnouncement,
  parseBootstrap,
  parseDismissed,
  parseNotice,
  pauseNotice,
  randomClientId,
  refreshIntervalMs,
  rememberDismissed,
  serviceNotice,
  supportWhatsappUrl,
  visibleAnnouncements,
  withServiceNotice,
} from '@/lib/bootstrap';

const pause: Notice = { kind: 'pause', area: 'Caracas', message: { es: 'Lluvia fuerte', en: 'Heavy rain' }, eta: null };
const maintenance: Notice = { kind: 'maintenance', area: null, message: { es: 'Mantenimiento', en: '' }, eta: null };

const SAMPLE = {
  area: 'Caracas',
  maintenance: null,
  paused_areas: [pause],
  service: pause,
  flags: { chat: false, promotions: true, transfers: false, binance_auto: false, share_live_link: true },
  announcements: [
    {
      id: 'a1',
      title: { es: 'Hola', en: 'Hello' },
      body: { es: 'Cuerpo', en: '' },
      target: { roles: ['passenger'], areas: [] },
      cta: { label: { es: 'Ver', en: 'See' }, url: null, screen: 'wallet' },
      starts_at: '2026-01-01T00:00:00Z',
      ends_at: '2027-01-01T00:00:00Z',
      dismissible: true,
      style: 'promo',
    },
  ],
  links: { support_whatsapp: '+58 412-555', support_email: 'ayuda@kuulis.app', emergency_number: '171', terms_url: '', privacy_url: '' },
  location_intervals: { online_seconds: 10, on_ride_seconds: 3 },
  min_build: 42,
  refresh_seconds: 300,
};

describe('parseBootstrap', () => {
  it('reads a full answer', () => {
    const data = parseBootstrap(SAMPLE);
    expect(data.area).toBe('Caracas');
    expect(data.service).toEqual(pause);
    expect(data.paused_areas).toHaveLength(1);
    expect(data.flags.chat).toBe(false);
    expect(data.flags.share_live_link).toBe(true);
    expect(data.announcements[0].cta).toEqual({ label: { es: 'Ver', en: 'See' }, url: null, screen: 'wallet' });
    expect(data.links.emergency_number).toBe('171');
    expect(data.location_intervals).toEqual({ online_seconds: 10, on_ride_seconds: 3 });
    expect(data.min_build).toBe(42);
  });

  it('falls back to defaults for anything missing or malformed', () => {
    const data = parseBootstrap(null);
    expect(data.maintenance).toBeNull();
    expect(data.service).toBeNull();
    expect(data.flags).toEqual(DEFAULT_FLAGS);
    expect(data.announcements).toEqual([]);
    expect(data.links.emergency_number).toBe('');
    expect(data.refresh_seconds).toBe(300);
    const odd = parseBootstrap({ flags: { chat: 'no', transfers: false }, refresh_seconds: 5, announcements: [{}, null] });
    expect(odd.flags.chat).toBe(true);
    expect(odd.flags.transfers).toBe(false);
    expect(odd.refresh_seconds).toBe(30);
    expect(odd.announcements).toEqual([]);
  });

  it('drops notices with an unknown kind and invalid ETAs', () => {
    expect(parseNotice({ kind: 'other', message: { es: 'x' } })).toBeNull();
    expect(parseNotice({ kind: 'pause', message: { es: 'x' }, eta: 'not a date' })?.eta).toBeNull();
  });

  it('keeps only https links in banner buttons', () => {
    const a = parseAnnouncement({ id: 'x', title: { es: 't' }, cta: { label: { es: 'Ir' }, url: 'http://evil', screen: null } });
    expect(a?.cta).toBeNull();
    const b = parseAnnouncement({ id: 'y', title: { es: 't' }, cta: { label: { es: 'Ir' }, url: 'https://kuulis.app', screen: null } });
    expect(b?.cta?.url).toBe('https://kuulis.app');
  });
});

describe('flags', () => {
  it('defaults while unknown: existing features on, share_live_link off', () => {
    expect(flagValue(null, 'chat')).toBe(true);
    expect(flagValue(null, 'promotions')).toBe(true);
    expect(flagValue(null, 'transfers')).toBe(true);
    expect(flagValue(null, 'share_live_link')).toBe(false);
    expect(flagValue(parseBootstrap(SAMPLE), 'chat')).toBe(false);
  });
});

describe('localize', () => {
  it('uses the app language and falls back to Spanish', () => {
    expect(localize({ es: 'Hola', en: 'Hello' }, 'en')).toBe('Hello');
    expect(localize({ es: 'Hola', en: 'Hello' }, 'es-VE')).toBe('Hola');
    expect(localize({ es: 'Hola', en: '' }, 'en-US')).toBe('Hola');
    expect(localize({ es: '', en: 'Hello' }, 'es')).toBe('Hello');
    expect(localize(null, 'es')).toBe('');
  });
});

describe('notices', () => {
  const base = parseBootstrap(SAMPLE);

  it('global maintenance wins and is full screen', () => {
    const data = { ...base, maintenance };
    expect(maintenanceNotice(data)).toBe(maintenance);
    expect(serviceNotice(data)).toBe(maintenance);
    expect(pauseNotice(data)).toBeNull();
  });

  it('city maintenance from service is full screen too', () => {
    const city: Notice = { ...maintenance, area: 'Caracas' };
    expect(maintenanceNotice({ ...base, service: city })).toBe(city);
  });

  it('a city pause only stops quoting', () => {
    expect(maintenanceNotice(base)).toBeNull();
    expect(pauseNotice(base)).toEqual(pause);
    expect(pauseNotice({ ...base, service: null })).toBeNull();
    expect(maintenanceNotice(null)).toBeNull();
  });

  it('applies a 503 service_paused right away', () => {
    const clear = { ...base, service: null, area: null };
    expect(withServiceNotice(clear, pause).service).toBe(pause);
    expect(withServiceNotice(clear, pause).area).toBe('Caracas');
    expect(withServiceNotice(clear, maintenance).maintenance).toBe(maintenance);
  });

  it('retries every 30 s during maintenance, else every refresh_seconds', () => {
    expect(refreshIntervalMs(null)).toBe(300_000);
    expect(refreshIntervalMs({ ...base, refresh_seconds: 120 })).toBe(120_000);
    expect(refreshIntervalMs({ ...base, maintenance })).toBe(30_000);
  });
});

describe('announcements', () => {
  const now = Date.parse('2026-10-12T12:00:00Z');
  const make = (over: Partial<Announcement>): Announcement => ({
    id: 'a',
    title: { es: 'T', en: '' },
    body: { es: 'B', en: '' },
    target: { roles: [], areas: [] },
    cta: null,
    starts_at: '2026-10-01T00:00:00Z',
    ends_at: '2026-11-01T00:00:00Z',
    dismissible: true,
    style: 'info',
    ...over,
  });

  it('filters by dates, mode, city and closed ones', () => {
    const list = [
      make({ id: 'ok' }),
      make({ id: 'future', starts_at: '2026-10-20T00:00:00Z' }),
      make({ id: 'past', ends_at: '2026-10-10T00:00:00Z' }),
      make({ id: 'driver', target: { roles: ['driver'], areas: [] } }),
      make({ id: 'valencia', target: { roles: [], areas: ['Valencia'] } }),
      make({ id: 'closed' }),
      make({ id: 'empty', title: { es: '', en: '' }, body: { es: '', en: '' } }),
    ];
    const visible = visibleAnnouncements(list, { mode: 'passenger', area: 'Caracas', dismissed: ['closed'], now });
    expect(visible.map((a) => a.id)).toEqual(['ok']);
  });

  it('does not hide a city banner when the city is unknown', () => {
    const list = [make({ id: 'valencia', target: { roles: [], areas: ['Valencia'] } })];
    expect(visibleAnnouncements(list, { mode: 'driver', area: null, dismissed: [], now })).toHaveLength(1);
  });

  it('remembers closed banners without duplicates and with a limit', () => {
    expect(rememberDismissed(['a', 'b'], 'a')).toEqual(['b', 'a']);
    expect(rememberDismissed(['a', 'b', 'c'], 'd', 3)).toEqual(['b', 'c', 'd']);
    expect(parseDismissed('["a",1,"b"]')).toEqual(['a', 'b']);
    expect(parseDismissed('oops')).toEqual([]);
    expect(parseDismissed(null)).toEqual([]);
  });

  it('maps banner buttons to existing screens only', () => {
    const cta = (screen: Announcement['cta']) => screen;
    const label = { es: 'Ir', en: '' };
    const passenger = { mode: 'passenger' as const, hasWallet: false };
    expect(ctaTarget(cta({ label, url: 'https://kuulis.app', screen: null }), passenger)).toEqual({ kind: 'url', url: 'https://kuulis.app' });
    expect(ctaTarget(cta({ label, url: null, screen: 'home' }), passenger)).toEqual({ kind: 'route', href: '/' });
    expect(ctaTarget(cta({ label, url: null, screen: 'about' }), passenger)).toEqual({ kind: 'route', href: '/profile/about' });
    expect(ctaTarget(cta({ label, url: null, screen: 'promotions' }), passenger)).toBeNull();
    expect(ctaTarget(cta({ label, url: null, screen: 'wallet' }), passenger)).toBeNull();
    expect(ctaTarget(cta({ label, url: null, screen: 'wallet' }), { mode: 'driver', hasWallet: true })).toEqual({ kind: 'route', href: '/wallet' });
    expect(ctaTarget(cta({ label, url: null, screen: 'driver_signup' }), passenger)).toEqual({ kind: 'driver_signup' });
    expect(ctaTarget(null, passenger)).toBeNull();
  });
});

describe('remote settings', () => {
  it('emergency number falls back to 911', () => {
    expect(emergencyNumberFrom(null)).toBe('911');
    expect(emergencyNumberFrom({ emergency_number: '' })).toBe('911');
    expect(emergencyNumberFrom({ emergency_number: '171' })).toBe('171');
  });

  it('location interval depends on being on a ride', () => {
    expect(locationIntervalMs(null, false)).toBe(4000);
    expect(locationIntervalMs({ online_seconds: 10, on_ride_seconds: 3 }, false)).toBe(10_000);
    expect(locationIntervalMs({ online_seconds: 10, on_ride_seconds: 3 }, true)).toBe(3000);
  });

  it('builds a WhatsApp link from the support number', () => {
    expect(supportWhatsappUrl('+58 412-555')).toBe('https://wa.me/58412555');
    expect(supportWhatsappUrl('')).toBeNull();
  });

  it('formats the ETA in local time, with the date on another day', () => {
    const now = new Date(2026, 9, 12, 9, 0);
    const today = new Date(2026, 9, 12, 16, 30).toISOString();
    const tomorrow = new Date(2026, 9, 13, 8, 0).toISOString();
    expect(formatEta(today, 'es', now)).toMatch(/16:30|4:30/);
    expect(formatEta(tomorrow, 'es', now)).toContain(',');
    expect(formatEta(null, 'es', now)).toBeNull();
    expect(formatEta('bad', 'es', now)).toBeNull();
  });

  it('creates a v4-shaped client id', () => {
    expect(randomClientId()).toMatch(/^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/);
  });
});
