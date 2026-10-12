/**
 * Remote control of the app (doc 10): GET /app/bootstrap says whether the app is in maintenance, which
 * cities have new rides paused, which features are on, which banners to show and a few remote settings
 * (support contacts, emergency number, legal links, location intervals). Pure, so it is unit tested; the
 * hook that fetches and caches it lives in hooks/useBootstrap.
 */

export type Localized = { es: string; en: string };
export type NoticeKind = 'maintenance' | 'pause';
export type Notice = { kind: NoticeKind; area: string | null; message: Localized; eta: string | null };

export type FlagKey = 'chat' | 'promotions' | 'transfers' | 'binance_auto' | 'share_live_link';
export type Flags = Record<FlagKey, boolean>;

export type AnnouncementStyle = 'info' | 'warning' | 'promo';
export type CtaScreen = 'home' | 'wallet' | 'promotions' | 'profile' | 'about' | 'driver_signup';
export type Announcement = {
  id: string;
  title: Localized;
  body: Localized;
  target: { roles: ('passenger' | 'driver')[]; areas: string[] };
  cta: { label: Localized; url: string | null; screen: CtaScreen | null } | null;
  starts_at: string | null;
  ends_at: string | null;
  dismissible: boolean;
  style: AnnouncementStyle;
};

export type AppLinks = {
  support_whatsapp: string;
  support_email: string;
  emergency_number: string;
  terms_url: string;
  privacy_url: string;
};

export type LocationIntervals = { online_seconds: number; on_ride_seconds: number };

export type Bootstrap = {
  area: string | null;
  maintenance: Notice | null;
  paused_areas: Notice[];
  service: Notice | null;
  flags: Flags;
  announcements: Announcement[];
  links: AppLinks;
  location_intervals: LocationIntervals;
  min_build: number;
  refresh_seconds: number;
};

/** While the bootstrap is unknown, features that exist today stay on; new ones stay off. */
export const DEFAULT_FLAGS: Flags = {
  chat: true,
  promotions: true,
  transfers: true,
  binance_auto: true,
  share_live_link: false,
};

/** What the app used before these were remote. */
export const DEFAULT_EMERGENCY_NUMBER = '911';
export const DEFAULT_LOCATION_INTERVALS: LocationIntervals = { online_seconds: 4, on_ride_seconds: 4 };
export const DEFAULT_REFRESH_SECONDS = 300;
/** How often the maintenance screen asks again whether it is over. */
export const MAINTENANCE_RETRY_SECONDS = 30;

export const EMPTY_LINKS: AppLinks = {
  support_whatsapp: '',
  support_email: '',
  emergency_number: '',
  terms_url: '',
  privacy_url: '',
};

const isRecord = (value: unknown): value is Record<string, unknown> =>
  !!value && typeof value === 'object' && !Array.isArray(value);
const str = (value: unknown): string => (typeof value === 'string' ? value : '');
const strOrNull = (value: unknown): string | null => (typeof value === 'string' && value ? value : null);

function intIn(value: unknown, min: number, max: number, fallback: number): number {
  const n = typeof value === 'number' ? value : Number(value);
  if (!Number.isFinite(n)) return fallback;
  return Math.min(max, Math.max(min, Math.round(n)));
}

export function parseLocalized(value: unknown): Localized {
  if (typeof value === 'string') return { es: value, en: '' };
  if (!isRecord(value)) return { es: '', en: '' };
  return { es: str(value.es), en: str(value.en) };
}

/** The text in the app language; English falls back to Spanish when empty (and Spanish to English). */
export function localize(text: Localized | null | undefined, language: string): string {
  if (!text) return '';
  const lang = language.toLowerCase().startsWith('en') ? 'en' : 'es';
  const primary = (lang === 'en' ? text.en : text.es)?.trim();
  if (primary) return primary;
  return (text.es?.trim() || text.en?.trim() || '').trim();
}

export function parseNotice(value: unknown): Notice | null {
  if (!isRecord(value)) return null;
  const kind = value.kind === 'maintenance' || value.kind === 'pause' ? value.kind : null;
  if (!kind) return null;
  const eta = strOrNull(value.eta);
  return {
    kind,
    area: strOrNull(value.area),
    message: parseLocalized(value.message),
    eta: eta && !Number.isNaN(Date.parse(eta)) ? eta : null,
  };
}

const ROLES = ['passenger', 'driver'] as const;
const STYLES: AnnouncementStyle[] = ['info', 'warning', 'promo'];
const SCREENS: CtaScreen[] = ['home', 'wallet', 'promotions', 'profile', 'about', 'driver_signup'];

export function parseAnnouncement(value: unknown): Announcement | null {
  if (!isRecord(value) || typeof value.id !== 'string' || !value.id) return null;
  const target = isRecord(value.target) ? value.target : {};
  const roles = Array.isArray(target.roles)
    ? target.roles.filter((r): r is 'passenger' | 'driver' => (ROLES as readonly unknown[]).includes(r))
    : [];
  const areas = Array.isArray(target.areas) ? target.areas.filter((a): a is string => typeof a === 'string') : [];
  let cta: Announcement['cta'] = null;
  if (isRecord(value.cta)) {
    const url = strOrNull(value.cta.url);
    const screen = SCREENS.includes(value.cta.screen as CtaScreen) ? (value.cta.screen as CtaScreen) : null;
    // Only https links leave the app.
    const safeUrl = url && /^https:\/\//i.test(url) ? url : null;
    if (safeUrl || screen) cta = { label: parseLocalized(value.cta.label), url: safeUrl, screen: safeUrl ? null : screen };
  }
  return {
    id: value.id,
    title: parseLocalized(value.title),
    body: parseLocalized(value.body),
    target: { roles, areas },
    cta,
    starts_at: strOrNull(value.starts_at),
    ends_at: strOrNull(value.ends_at),
    dismissible: value.dismissible !== false,
    style: STYLES.includes(value.style as AnnouncementStyle) ? (value.style as AnnouncementStyle) : 'info',
  };
}

export function parseFlags(value: unknown): Flags {
  const flags = { ...DEFAULT_FLAGS };
  if (!isRecord(value)) return flags;
  for (const key of Object.keys(DEFAULT_FLAGS) as FlagKey[]) {
    if (typeof value[key] === 'boolean') flags[key] = value[key] as boolean;
  }
  return flags;
}

export function parseLinks(value: unknown): AppLinks {
  if (!isRecord(value)) return { ...EMPTY_LINKS };
  return {
    support_whatsapp: str(value.support_whatsapp).trim(),
    support_email: str(value.support_email).trim(),
    emergency_number: str(value.emergency_number).replace(/\D/g, ''),
    terms_url: str(value.terms_url).trim(),
    privacy_url: str(value.privacy_url).trim(),
  };
}

export function parseIntervals(value: unknown): LocationIntervals {
  if (!isRecord(value)) return { ...DEFAULT_LOCATION_INTERVALS };
  return {
    online_seconds: intIn(value.online_seconds, 1, 120, DEFAULT_LOCATION_INTERVALS.online_seconds),
    on_ride_seconds: intIn(value.on_ride_seconds, 1, 60, DEFAULT_LOCATION_INTERVALS.on_ride_seconds),
  };
}

/** Tolerant parser: anything missing or malformed falls back to the defaults (never throws). */
export function parseBootstrap(value: unknown): Bootstrap {
  const data = isRecord(value) ? value : {};
  return {
    area: strOrNull(data.area),
    maintenance: parseNotice(data.maintenance),
    paused_areas: Array.isArray(data.paused_areas)
      ? data.paused_areas.map(parseNotice).filter((n): n is Notice => !!n)
      : [],
    service: parseNotice(data.service),
    flags: parseFlags(data.flags),
    announcements: Array.isArray(data.announcements)
      ? data.announcements.map(parseAnnouncement).filter((a): a is Announcement => !!a)
      : [],
    links: parseLinks(data.links),
    location_intervals: parseIntervals(data.location_intervals),
    min_build: intIn(data.min_build, 0, Number.MAX_SAFE_INTEGER, 0),
    refresh_seconds: intIn(data.refresh_seconds, 30, 3600, DEFAULT_REFRESH_SECONDS),
  };
}

/** Feature value, with the defaults while the bootstrap is unknown. */
export function flagValue(bootstrap: Pick<Bootstrap, 'flags'> | null | undefined, key: FlagKey): boolean {
  return bootstrap?.flags?.[key] ?? DEFAULT_FLAGS[key];
}

/** Full-screen maintenance: global maintenance, or maintenance in the user's city. */
export function maintenanceNotice(bootstrap: Bootstrap | null | undefined): Notice | null {
  if (!bootstrap) return null;
  if (bootstrap.maintenance) return bootstrap.maintenance;
  return bootstrap.service?.kind === 'maintenance' ? bootstrap.service : null;
}

/** Why new rides (and going online) are stopped where the user is: maintenance or a city pause. */
export function serviceNotice(bootstrap: Bootstrap | null | undefined): Notice | null {
  if (!bootstrap) return null;
  return bootstrap.maintenance ?? bootstrap.service ?? null;
}

/** Only the city pause (the passenger search and driver panel show it; maintenance has its own screen). */
export function pauseNotice(bootstrap: Bootstrap | null | undefined): Notice | null {
  const notice = serviceNotice(bootstrap);
  return notice?.kind === 'pause' ? notice : null;
}

/** A 503 service_paused tells the app right away, before the next bootstrap: apply it to the cached one. */
export function withServiceNotice(bootstrap: Bootstrap, notice: Notice): Bootstrap {
  if (notice.kind === 'maintenance' && !notice.area) return { ...bootstrap, maintenance: notice, service: notice };
  return { ...bootstrap, service: notice, area: bootstrap.area ?? notice.area };
}

/** Banners to show now: in their dates, for this mode and city, not closed on this device. */
export function visibleAnnouncements(
  announcements: Announcement[],
  options: { mode: 'passenger' | 'driver' | null; area: string | null; dismissed: Iterable<string>; now?: number },
): Announcement[] {
  const now = options.now ?? Date.now();
  const dismissed = new Set(options.dismissed);
  return announcements.filter((a) => {
    if (dismissed.has(a.id)) return false;
    const starts = a.starts_at ? Date.parse(a.starts_at) : NaN;
    const ends = a.ends_at ? Date.parse(a.ends_at) : NaN;
    if (!Number.isNaN(starts) && starts > now) return false;
    if (!Number.isNaN(ends) && ends <= now) return false;
    if (a.target.roles.length && options.mode && !a.target.roles.includes(options.mode)) return false;
    // The server already filtered by city; an unknown city here does not hide it.
    if (a.target.areas.length && options.area && !a.target.areas.includes(options.area)) return false;
    return !!(a.title.es || a.title.en || a.body.es || a.body.en);
  });
}

/** Remembered closed banners: newest last, without duplicates, at most `limit`. */
export function rememberDismissed(ids: readonly string[], id: string, limit = 200): string[] {
  const next = ids.filter((existing) => existing !== id);
  next.push(id);
  return next.slice(Math.max(0, next.length - limit));
}

export function parseDismissed(raw: string | null | undefined): string[] {
  if (!raw) return [];
  try {
    const value: unknown = JSON.parse(raw);
    return Array.isArray(value) ? value.filter((v): v is string => typeof v === 'string') : [];
  } catch {
    return [];
  }
}

export type CtaTarget =
  | { kind: 'url'; url: string }
  | { kind: 'route'; href: '/' | '/wallet' | '/profile' | '/profile/about' }
  | { kind: 'driver_signup' };

/** Where a banner button goes; null when this app has no such screen (the button is then hidden). */
export function ctaTarget(
  cta: Announcement['cta'],
  options: { mode: 'passenger' | 'driver' | null; hasWallet: boolean },
): CtaTarget | null {
  if (!cta) return null;
  if (cta.url) return /^https:\/\//i.test(cta.url) ? { kind: 'url', url: cta.url } : null;
  switch (cta.screen) {
    case 'home':
      return { kind: 'route', href: '/' };
    case 'wallet':
      // The wallet is the approved driver's.
      return options.mode === 'driver' && options.hasWallet ? { kind: 'route', href: '/wallet' } : null;
    case 'profile':
      return { kind: 'route', href: '/profile' };
    case 'about':
      return { kind: 'route', href: '/profile/about' };
    case 'driver_signup':
      return { kind: 'driver_signup' };
    default:
      // "promotions" has no screen in the app yet.
      return null;
  }
}

/** The emergency number to call: the remote one, else 911. */
export function emergencyNumberFrom(links: Pick<AppLinks, 'emergency_number'> | null | undefined): string {
  const digits = (links?.emergency_number ?? '').replace(/\D/g, '');
  return digits || DEFAULT_EMERGENCY_NUMBER;
}

/** How often the driver's position is sent: faster on a ride. In milliseconds. */
export function locationIntervalMs(intervals: LocationIntervals | null | undefined, onRide: boolean): number {
  const value = intervals ?? DEFAULT_LOCATION_INTERVALS;
  const seconds = onRide ? value.on_ride_seconds : value.online_seconds;
  return Math.max(1, seconds) * 1000;
}

/** Refetch period: every `refresh_seconds`, or every 30 s while the maintenance screen is up. */
export function refreshIntervalMs(bootstrap: Bootstrap | null | undefined): number {
  if (maintenanceNotice(bootstrap)) return MAINTENANCE_RETRY_SECONDS * 1000;
  return (bootstrap?.refresh_seconds ?? DEFAULT_REFRESH_SECONDS) * 1000;
}

/** Same-day ETA as a time ("14:30"); another day adds the date ("sáb 12 oct, 14:30"). */
export function formatEta(eta: string | null | undefined, language: string, now = new Date()): string | null {
  if (!eta) return null;
  const date = new Date(eta);
  if (Number.isNaN(date.getTime())) return null;
  const time = date.toLocaleTimeString(language, { hour: '2-digit', minute: '2-digit' });
  const sameDay =
    date.getFullYear() === now.getFullYear() && date.getMonth() === now.getMonth() && date.getDate() === now.getDate();
  if (sameDay) return time;
  const day = date.toLocaleDateString(language, { weekday: 'short', day: 'numeric', month: 'short' });
  return `${day}, ${time}`;
}

/** WhatsApp link for the support number (digits only); null when there is none. */
export function supportWhatsappUrl(phone: string | null | undefined): string | null {
  const digits = (phone ?? '').replace(/\D/g, '');
  return digits ? `https://wa.me/${digits}` : null;
}

/** A random id for this install (sent as client_id before login and for stable rollouts). */
export function randomClientId(random: () => number = Math.random): string {
  const hex = Array.from({ length: 32 }, () => Math.floor(random() * 16).toString(16));
  hex[12] = '4';
  hex[16] = ((parseInt(hex[16], 16) & 0x3) | 0x8).toString(16);
  const s = hex.join('');
  return `${s.slice(0, 8)}-${s.slice(8, 12)}-${s.slice(12, 16)}-${s.slice(16, 20)}-${s.slice(20)}`;
}
