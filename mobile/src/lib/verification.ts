/**
 * Ongoing driver verification (doc 12), pure logic so it can be unit tested: expiry dates and badges, the
 * "Mis documentos" list, why going online is blocked and what to do about it.
 * Rules come from docs/produccion/12-verificacion-continua-motorizados.md; the API decides again.
 */
import { ApiError } from './api';
import { DEFAULT_VERIFICATION, documentChecklist, parseDisplayDate } from './driver';
import type {
  AppConfig,
  CheckKind,
  DocumentKind,
  DriverCheck,
  DriverDocument,
  DriverProfile,
  VerificationConfig,
  VerificationState,
} from './types';

/** Kinds an approved driver can renew from "Mis documentos" (selfie and moto photos go through checks). */
export const RENEWABLE_KINDS: readonly DocumentKind[] = [
  'id_card',
  'rif',
  'drivers_license',
  'medical_certificate',
  'vehicle_registration',
  'criminal_record',
];

/** The API only takes expiry dates within these years. */
const MIN_EXPIRY_YEAR = 2000;
const MAX_EXPIRY_YEAR = 2100;

/** Verification settings with the documented defaults for anything an older server leaves out. */
export function verificationConfig(config: AppConfig): VerificationConfig {
  const value = config.verification;
  return {
    expiring_documents: value?.expiring_documents ?? DEFAULT_VERIFICATION.expiring_documents,
    optional_documents: value?.optional_documents ?? DEFAULT_VERIFICATION.optional_documents,
    expiry_notice_days: value?.expiry_notice_days?.length ? value.expiry_notice_days : DEFAULT_VERIFICATION.expiry_notice_days,
    selfie_every_days: value?.selfie_every_days ?? DEFAULT_VERIFICATION.selfie_every_days,
  };
}

/** Whether uploading this kind asks for its expiry date. */
export const needsExpiry = (kind: DocumentKind, config: AppConfig) =>
  verificationConfig(config).expiring_documents.includes(kind);

/** Optional kinds (not in the required list) the driver may add: shown apart and never block the submit. */
export function optionalKinds(config: AppConfig): DocumentKind[] {
  return verificationConfig(config).optional_documents.filter(
    (kind) => !config.driver_required_documents.includes(kind) && RENEWABLE_KINDS.includes(kind),
  );
}

/** Onboarding checklist of the optional kinds (same states as the required ones). */
export const optionalChecklist = (profile: DriverProfile | null | undefined, config: AppConfig) =>
  documentChecklist(profile, { ...config, driver_required_documents: optionalKinds(config) });

/** Days ahead the dashboard warns about an expiry (the largest notice, 30 by default). */
export const warningWindow = (config: AppConfig) => Math.max(...verificationConfig(config).expiry_notice_days);

// ── Dates ──

/** Local calendar date as "YYYY-MM-DD". */
export function todayIso(now: Date = new Date()): string {
  const pad = (n: number) => String(n).padStart(2, '0');
  return `${now.getFullYear()}-${pad(now.getMonth() + 1)}-${pad(now.getDate())}`;
}

const dayNumber = (iso: string) => {
  const [year, month, day] = iso.slice(0, 10).split('-').map(Number);
  return Date.UTC(year, month - 1, day) / 86_400_000;
};

/** Whole calendar days from `today` to `iso` (negative once it passed, 0 on the day itself). */
export function daysUntil(iso: string, today: Date = new Date()): number {
  return Math.round(dayNumber(iso) - dayNumber(todayIso(today)));
}

export type ExpiryInputError = 'invalid' | 'past';

/** "31/12/2027" typed by the driver -> "2027-12-31". An expiry today is still valid; yesterday is not. */
export function parseExpiryInput(
  value: string,
  today: Date = new Date(),
): { iso: string; error?: undefined } | { iso?: undefined; error: ExpiryInputError } {
  const iso = parseDisplayDate(value);
  if (!iso) return { error: 'invalid' };
  const year = Number(iso.slice(0, 4));
  if (year < MIN_EXPIRY_YEAR || year > MAX_EXPIRY_YEAR) return { error: 'invalid' };
  if (daysUntil(iso, today) < 0) return { error: 'past' };
  return { iso };
}

/** Translation key (and count) for "Vencido" / "Vence hoy" / "Vence mañana" / "Vence en 12 días". */
export function expiryLabel(daysLeft: number): { key: string; count?: number } {
  if (daysLeft < 0) return { key: 'verification.badge.expired' };
  if (daysLeft === 0) return { key: 'verification.badge.today' };
  if (daysLeft === 1) return { key: 'verification.badge.tomorrow' };
  return { key: 'verification.badge.inDays', count: daysLeft };
}

// ── "Mis documentos" ──

export type MyDocumentState =
  | 'expired'
  | 'expiring'
  | 'missing_expiry'
  | 'rejected'
  | 'in_review'
  | 'valid'
  | 'not_added';

export type BadgeTone = 'danger' | 'warning' | 'info' | 'success' | 'neutral';

export interface MyDocumentItem {
  kind: DocumentKind;
  optional: boolean;
  needsExpiry: boolean;
  /** The approved file in use. */
  inUse: DriverDocument | null;
  /** A newer file not approved yet: a renewal under review, or the verifier's rejection of it. */
  renewal: DriverDocument | null;
  state: MyDocumentState;
  /** Days until the file in use expires (null without a date). */
  daysLeft: number | null;
  /** "Indicar fecha": approved before doc 12 without a date. */
  canSetExpiry: boolean;
}

const newestFirst = (a: DriverDocument, b: DriverDocument) => b.created_at.localeCompare(a.created_at);

/** Most urgent first; the order of the config is kept within the same urgency. */
const STATE_RANK: Record<MyDocumentState, number> = {
  expired: 0,
  rejected: 1,
  missing_expiry: 2,
  expiring: 3,
  in_review: 4,
  valid: 5,
  not_added: 6,
};

/** Documents in use for an approved driver, each with what it needs (renew, type its date, nothing). */
export function myDocuments(
  profile: DriverProfile | null | undefined,
  config: AppConfig,
  today: Date = new Date(),
): MyDocumentItem[] {
  const window = warningWindow(config);
  const required = config.driver_required_documents.filter((kind) => RENEWABLE_KINDS.includes(kind));
  const kinds = [...required, ...optionalKinds(config)];
  const items = kinds.map((kind): MyDocumentItem => {
    const files = (profile?.documents ?? []).filter((doc) => doc.kind === kind).sort(newestFirst);
    const inUse = files.find((doc) => doc.status === 'approved') ?? null;
    const renewal =
      files.find((doc) => doc.status !== 'approved' && (!inUse || doc.created_at > inUse.created_at)) ?? null;
    const expiring = needsExpiry(kind, config);
    const daysLeft = inUse?.expires_on ? daysUntil(inUse.expires_on, today) : null;
    let state: MyDocumentState;
    if (renewal?.status === 'pending') state = 'in_review';
    else if (renewal?.status === 'rejected') state = 'rejected';
    else if (!inUse) state = 'not_added';
    else if (expiring && daysLeft === null) state = 'missing_expiry';
    else if (expiring && daysLeft !== null && daysLeft < 0) state = 'expired';
    else if (expiring && daysLeft !== null && daysLeft <= window) state = 'expiring';
    else state = 'valid';
    return {
      kind,
      optional: !required.includes(kind),
      needsExpiry: expiring,
      inUse,
      renewal,
      state,
      daysLeft,
      canSetExpiry: expiring && !!inUse && !inUse.expires_on && !inUse.expiry_confirmed,
    };
  });
  return items
    .map((item, index) => ({ item, index }))
    .sort((a, b) => STATE_RANK[a.item.state] - STATE_RANK[b.item.state] || a.index - b.index)
    .map(({ item }) => item);
}

/** The pill of a document in "Mis documentos". */
export function documentBadge(item: MyDocumentItem): { key: string; count?: number; tone: BadgeTone } {
  switch (item.state) {
    case 'in_review':
      return { key: 'verification.badge.in_review', tone: 'info' };
    case 'rejected':
      return { key: 'verification.badge.rejected', tone: 'danger' };
    case 'not_added':
      return { key: item.optional ? 'verification.badge.optional' : 'verification.badge.missing', tone: 'neutral' };
    case 'missing_expiry':
      return { key: 'verification.badge.missing_expiry', tone: 'warning' };
    case 'expired':
    case 'expiring':
      return { ...expiryLabel(item.daysLeft ?? -1), tone: item.state === 'expired' ? 'danger' : 'warning' };
    case 'valid':
    default:
      return { key: item.needsExpiry ? 'verification.badge.valid' : 'verification.badge.approved', tone: 'success' };
  }
}

/** How many documents need the driver (the Perfil row and the dashboard count). */
export const needsAttention = (items: MyDocumentItem[]) =>
  items.filter((item) => ['expired', 'expiring', 'missing_expiry', 'rejected'].includes(item.state)).length;

// ── Going online ──

export type OnlineBlock =
  | { reason: 'selfie_required'; checkId: string | null; checkKind: 'selfie' | 'reverification' }
  | { reason: 'document_expired'; kinds: DocumentKind[]; renewalPending: boolean };

/** Why the API will refuse POST /drivers/me/online, from the profile's verification state. */
export function onlineBlock(verification: VerificationState | null | undefined): OnlineBlock | null {
  if (!verification || verification.can_go_online) return null;
  if (verification.expired.length) {
    const pending = verification.expiring.filter((alert) => alert.days_left < 0 && alert.renewal_pending);
    return {
      reason: 'document_expired',
      kinds: verification.expired,
      renewalPending: verification.expired.every((kind) => pending.some((alert) => alert.kind === kind)),
    };
  }
  if (verification.required_check_id) {
    return {
      reason: 'selfie_required',
      checkId: verification.required_check_id,
      checkKind: verification.required_check_kind === 'reverification' ? 'reverification' : 'selfie',
    };
  }
  return null;
}

/** A 403 document_expired / selfie_required from going online, as the action to offer instead of a toast. */
export function onlineBlockFromError(error: unknown): OnlineBlock | null {
  if (!(error instanceof ApiError) || error.status !== 403) return null;
  const details = (error.details && typeof error.details === 'object' ? error.details : {}) as Record<string, unknown>;
  if (error.code === 'document_expired') {
    const kinds = Array.isArray(details.kinds) ? (details.kinds.filter((k) => typeof k === 'string') as DocumentKind[]) : [];
    return { reason: 'document_expired', kinds, renewalPending: false };
  }
  if (error.code === 'selfie_required') {
    return {
      reason: 'selfie_required',
      checkId: typeof details.check_id === 'string' ? details.check_id : null,
      checkKind: details.kind === 'reverification' ? 'reverification' : 'selfie',
    };
  }
  return null;
}

/** Where a block is solved: the documents list or the live selfie. */
export function blockHref(block: OnlineBlock) {
  if (block.reason === 'document_expired') return { pathname: '/driver/my-documents' as const };
  return {
    pathname: '/driver/selfie' as const,
    params: block.checkId ? { checkId: block.checkId, kind: block.checkKind } : { kind: block.checkKind },
  };
}

export type DashboardAlert =
  | OnlineBlock
  | { reason: 'missing_expiry'; kinds: DocumentKind[] }
  | { reason: 'expiring'; kind: DocumentKind; daysLeft: number; count: number };

/** The one banner on the driver dashboard, most urgent first; null when everything is in order. */
export function dashboardAlert(verification: VerificationState | null | undefined): DashboardAlert | null {
  if (!verification) return null;
  const block = onlineBlock(verification);
  if (block) return block;
  if (verification.missing_expiry.length) return { reason: 'missing_expiry', kinds: verification.missing_expiry };
  const upcoming = verification.expiring
    .filter((alert) => alert.days_left >= 0 && !alert.renewal_pending)
    .sort((a, b) => a.days_left - b.days_left);
  if (upcoming.length) {
    return { reason: 'expiring', kind: upcoming[0].kind, daysLeft: upcoming[0].days_left, count: upcoming.length };
  }
  return null;
}

// ── Live selfie and re-verification ──

/** The check waiting for my photos, from the route params or the profile. */
export function requestedCheck(
  profile: DriverProfile | null | undefined,
  checkId?: string | null,
): DriverCheck | null {
  const open = (profile?.checks ?? []).filter(
    (check) => check.status === 'requested' && (check.kind === 'selfie' || check.kind === 'reverification'),
  );
  return open.find((check) => check.id === checkId) ?? open.find((check) => check.id === profile?.verification?.required_check_id) ?? open[0] ?? null;
}

/** A selfie or re-verification sent and waiting for a verifier ("En revisión"). */
export function checkInReview(profile: DriverProfile | null | undefined): DriverCheck | null {
  return (
    (profile?.checks ?? []).find(
      (check) => check.status === 'pending' && (check.kind === 'selfie' || check.kind === 'reverification'),
    ) ?? null
  );
}

/** Moto photos a check needs: none for a selfie, at least `vehicle_photo_min_count` otherwise. */
export function photosNeeded(kind: CheckKind, config: AppConfig): number {
  return kind === 'selfie' || kind === 'document_renewal' ? 0 : Math.max(1, config.vehicle_photo_min_count);
}

/** The moto change under review (with its open check), if any. */
export function pendingVehicleCheck(profile: DriverProfile | null | undefined): DriverCheck | null {
  return (profile?.checks ?? []).find((check) => check.kind === 'vehicle_change' && check.status === 'pending') ?? null;
}

// ── Notifications ──

type Href = '/driver/selfie' | '/driver/my-documents' | '/driver/vehicle-change';

/** Screen a doc 12 push or inbox item opens: {type: "driver_*", event, check_id?}. */
export function verificationHrefOf(payload: unknown): { pathname: Href; params?: Record<string, string> } | null {
  const record = payload as { type?: unknown; event?: unknown; check_id?: unknown; data?: Record<string, unknown> } | null;
  const data = (record && typeof record.event === 'string' ? record : record?.data) as Record<string, unknown> | undefined;
  const type = data?.type;
  if (typeof type !== 'string' || !type.startsWith('driver_')) return null;
  switch (data?.event) {
    case 'selfie_requested':
      return typeof data.check_id === 'string'
        ? { pathname: '/driver/selfie', params: { checkId: data.check_id } }
        : { pathname: '/driver/selfie' };
    case 'document_expiring':
    case 'document_expired':
      return { pathname: '/driver/my-documents' };
    case 'vehicle_rejected':
      return { pathname: '/driver/vehicle-change' };
    default:
      return null;
  }
}
