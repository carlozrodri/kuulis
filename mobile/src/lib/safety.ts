/**
 * Pure logic for trip safety (doc 11): the start PIN, trusted contacts and their auto-share hours, the live
 * link message and the safety pushes. No React and no network, so it can be unit tested.
 */
import { ApiError } from './api';
import { formatPlate, shortAddress } from './ride';
import type { Ride, TrustedContact } from './types';

export const MAX_TRUSTED_CONTACTS = 5;
export const PIN_LENGTH = 4;
/** Hold the SOS button this long (ms) so it is never pressed by accident. */
export const SOS_HOLD_MS = 2000;
/** Venezuela has no daylight saving: Caracas is always UTC-4. */
const CARACAS_OFFSET_MIN = -4 * 60;

// ── PIN ──

/** Keeps only digits, at most four. */
export const cleanPin = (value: string) => value.replace(/\D/g, '').slice(0, PIN_LENGTH);

/** "4821" → "4 8 2 1", easier to read aloud to the driver. */
export const spacedPin = (pin: string | null | undefined) => (pin ?? '').split('').join(' ');

/** The driver must type the passenger's PIN before "Iniciar viaje". */
export const needsPin = (ride: Pick<Ride, 'status' | 'pin_required'>) =>
  !!ride.pin_required && ride.status === 'driver_arrived';

export type PinErrorKind = 'invalid' | 'locked' | null;

/** 400 pin_invalid (try again) or 429 pin_attempts_exceeded (call support or cancel). */
export function pinErrorKind(error: unknown): PinErrorKind {
  if (!(error instanceof ApiError)) return null;
  if (error.code === 'pin_invalid') return 'invalid';
  if (error.code === 'pin_attempts_exceeded') return 'locked';
  return null;
}

/** Tries left after a wrong PIN, when the API says so. */
export function pinAttemptsLeft(error: unknown): number | null {
  if (!(error instanceof ApiError)) return null;
  const value = (error.details as { attempts_left?: unknown } | null)?.attempts_left;
  return typeof value === 'number' ? value : null;
}

// ── Trusted contacts ──

const HHMM = /^([01]\d|2[0-3]):([0-5]\d)$/;

export const isClock = (value: string) => HHMM.test(value);

function minutesOf(value: string): number | null {
  const match = HHMM.exec(value);
  return match ? Number(match[1]) * 60 + Number(match[2]) : null;
}

/** Minutes since midnight in Caracas. */
export function caracasMinutes(date: Date): number {
  const utc = date.getUTCHours() * 60 + date.getUTCMinutes();
  return (((utc + CARACAS_OFFSET_MIN) % 1440) + 1440) % 1440;
}

/**
 * Is this contact's auto-share on right now? Without hours, always; with hours, only between them
 * (Caracas time). "19:00"–"06:00" crosses midnight.
 */
export function autoShareActive(contact: Pick<TrustedContact, 'auto_share' | 'auto_share_from' | 'auto_share_to'>, now: Date): boolean {
  if (!contact.auto_share) return false;
  const from = contact.auto_share_from ? minutesOf(contact.auto_share_from) : null;
  const to = contact.auto_share_to ? minutesOf(contact.auto_share_to) : null;
  if (from === null || to === null || from === to) return true;
  const current = caracasMinutes(now);
  return from < to ? current >= from && current < to : current >= from || current < to;
}

/** Contacts that should get this ride automatically. */
export const autoShareContacts = (contacts: TrustedContact[] | undefined, now: Date) =>
  (contacts ?? []).filter((contact) => autoShareActive(contact, now));

// ── Live link ──

type Translate = (key: string, options?: Record<string, unknown>) => string;

/** What goes to WhatsApp or the share sheet with the live link. */
export function liveShareMessage(ride: Pick<Ride, 'driver' | 'dropoff'>, url: string, t: Translate, sos = false) {
  const vehicle = ride.driver?.vehicle;
  return t(sos ? 'safety.live.sosMessage' : 'safety.live.message', {
    driver: ride.driver?.first_name ?? '',
    plate: formatPlate(vehicle?.plate),
    dropoff: shortAddress(ride.dropoff.address),
    url,
  });
}

// ── Notifications ──

export const SAFETY_CATEGORY = 'safety_check';
export type CheckInAnswer = 'ok' | 'help';

type SafetyPayload = {
  type?: unknown;
  event?: unknown;
  alert_id?: unknown;
  data?: { type?: unknown; event?: unknown; alert_id?: unknown } | null;
} | null;

/** Safety pushes carry {type: "safety", event: "check_in", alert_id, ride_id}. */
export function isSafetyNotification(payload: unknown): boolean {
  const record = payload as SafetyPayload;
  return (record?.type ?? record?.data?.type) === 'safety';
}

export function alertIdOf(payload: unknown): string | null {
  const record = payload as SafetyPayload;
  const value = record?.alert_id ?? record?.data?.alert_id;
  return typeof value === 'string' && value ? value : null;
}

/** The action buttons of the "¿Todo bien?" push. */
export function checkInAnswerOf(actionIdentifier: string | null | undefined): CheckInAnswer | null {
  return actionIdentifier === 'ok' || actionIdentifier === 'help' ? actionIdentifier : null;
}

/** Seconds left to answer a check-in (0 when overdue). */
export function secondsToAnswer(deadline: string | null | undefined, now: number): number | null {
  if (!deadline) return null;
  const at = Date.parse(deadline);
  return Number.isNaN(at) ? null : Math.max(0, Math.round((at - now) / 1000));
}

// ── Auto-share choice in the contact form ──

export type AutoShareMode = 'off' | 'always' | 'night';
export const NIGHT_HOURS = { from: '19:00', to: '06:00' } as const;

export function autoShareMode(contact: Pick<TrustedContact, 'auto_share' | 'auto_share_from' | 'auto_share_to'> | null): AutoShareMode {
  if (!contact?.auto_share) return 'off';
  return contact.auto_share_from && contact.auto_share_to ? 'night' : 'always';
}

/** The API fields for a choice; "night" keeps hours the person already had. */
export function autoShareFields(
  mode: AutoShareMode,
  previous?: Pick<TrustedContact, 'auto_share_from' | 'auto_share_to'> | null,
): Pick<TrustedContact, 'auto_share' | 'auto_share_from' | 'auto_share_to'> {
  if (mode === 'off') return { auto_share: false, auto_share_from: null, auto_share_to: null };
  if (mode === 'always') return { auto_share: true, auto_share_from: null, auto_share_to: null };
  const keep = previous?.auto_share_from && previous.auto_share_to;
  return {
    auto_share: true,
    auto_share_from: keep ? previous.auto_share_from : NIGHT_HOURS.from,
    auto_share_to: keep ? previous.auto_share_to : NIGHT_HOURS.to,
  };
}
