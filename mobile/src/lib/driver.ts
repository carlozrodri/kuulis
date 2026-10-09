/**
 * Pure driver-onboarding logic (no React, no network) so it can be unit tested.
 * Rules come from docs/product/roles-and-flows.md and docs/api/phase-1a.md; the API validates again.
 */
import type {
  AppConfig,
  DocumentKind,
  DocumentStatus,
  DriverDocument,
  DriverProfile,
  DriverStatus,
  VehicleType,
} from './types';

/** Defaults from docs/api/phase-1a.md, used until GET /config/public answers. */
export const DEFAULT_APP_CONFIG: AppConfig = {
  driver_min_age: 21,
  vehicle_min_year: { moto: 2013, car: 1993 },
  enabled_vehicle_types: ['moto'],
  driver_required_documents: [
    'id_card',
    'rif',
    'drivers_license',
    'medical_certificate',
    'vehicle_registration',
    'selfie',
    'vehicle_photo',
  ],
  vehicle_photo_min_count: 2,
};

export const MULTI_FILE_KINDS: readonly DocumentKind[] = ['vehicle_photo'];
/** Kinds that must be a photo taken on the spot (no PDF). */
export const PHOTO_ONLY_KINDS: readonly DocumentKind[] = ['selfie', 'vehicle_photo'];

export const EDITABLE_STATUSES: readonly DriverStatus[] = ['draft', 'rejected'];
export const isEditable = (status: DriverStatus | undefined) => !status || EDITABLE_STATUSES.includes(status);

// ── Dates ──

/** Masks free typing into DD/MM/AAAA. */
export function maskDateInput(raw: string): string {
  const digits = raw.replace(/\D/g, '').slice(0, 8);
  if (digits.length <= 2) return digits;
  if (digits.length <= 4) return `${digits.slice(0, 2)}/${digits.slice(2)}`;
  return `${digits.slice(0, 2)}/${digits.slice(2, 4)}/${digits.slice(4)}`;
}

/** "12/04/1995" -> "1995-04-12", or null when it is not a real calendar date. */
export function parseDisplayDate(value: string): string | null {
  const match = /^(\d{2})\/(\d{2})\/(\d{4})$/.exec(value.trim());
  if (!match) return null;
  const [, dd, mm, yyyy] = match;
  const day = Number(dd);
  const month = Number(mm);
  const year = Number(yyyy);
  if (year < 1900 || month < 1 || month > 12 || day < 1) return null;
  const date = new Date(Date.UTC(year, month - 1, day));
  if (date.getUTCFullYear() !== year || date.getUTCMonth() !== month - 1 || date.getUTCDate() !== day) return null;
  return `${yyyy}-${mm}-${dd}`;
}

/** "1995-04-12" -> "12/04/1995". */
export function isoToDisplayDate(iso: string | null | undefined): string {
  const match = iso ? /^(\d{4})-(\d{2})-(\d{2})/.exec(iso) : null;
  return match ? `${match[3]}/${match[2]}/${match[1]}` : '';
}

/** Whole years between an ISO birth date and `today` (local calendar). */
export function ageOn(birthIso: string, today: Date = new Date()): number {
  const [year, month, day] = birthIso.split('-').map(Number);
  let age = today.getFullYear() - year;
  const monthDiff = today.getMonth() + 1 - month;
  if (monthDiff < 0 || (monthDiff === 0 && today.getDate() < day)) age -= 1;
  return age;
}

export function isOldEnough(birthIso: string, minAge: number, today: Date = new Date()): boolean {
  return ageOn(birthIso, today) >= minAge;
}

// ── Venezuelan identifiers ──

const clean = (value: string) => value.toUpperCase().replace(/[^A-Z0-9]/g, '');

/** Cédula: "v-12.345.678" -> "V12345678". A bare number defaults to "V". */
export function normalizeNationalId(value: string): string {
  const id = clean(value);
  return /^\d/.test(id) ? `V${id}` : id;
}

export const isValidNationalId = (value: string) => /^[VE]\d{6,9}$/.test(normalizeNationalId(value));

/** RIF: "V-12345678-9" -> "V123456789" (letter + 8 digits + check digit). */
export function normalizeRif(value: string): string {
  const rif = clean(value);
  return /^\d/.test(rif) ? `V${rif}` : rif;
}

export const isValidRif = (value: string) => /^[VEJPG]\d{9}$/.test(normalizeRif(value));

/**
 * Phone in E.164. Local Venezuelan mobiles are expanded: "0412-123.45.67" -> "+584121234567".
 * Numbers typed with "+" follow the API rule: "+" and 10–15 digits. Returns null when invalid.
 */
export function normalizePhone(value: string): string | null {
  const trimmed = value.trim();
  const digits = trimmed.replace(/\D/g, '');
  if (trimmed.startsWith('+') && !digits.startsWith('58')) {
    return /^\d{10,15}$/.test(digits) ? `+${digits}` : null;
  }
  let local = digits.startsWith('58') ? digits.slice(2) : digits;
  if (local.startsWith('0')) local = local.slice(1);
  return /^4(12|14|16|22|24|26)\d{7}$/.test(local) ? `+58${local}` : null;
}

/** "+584121234567" -> "0412 123 4567" for display and prefill. */
export function formatPhoneLocal(e164: string | null | undefined): string {
  const match = e164 ? /^\+58(\d{3})(\d{3})(\d{4})$/.exec(e164) : null;
  return match ? `0${match[1]} ${match[2]} ${match[3]}` : (e164 ?? '');
}

// ── Vehicle ──

/** Plates are stored uppercase without spaces or dashes: "ab-2c 34d" -> "AB2C34D". */
export const normalizePlate = (value: string) => clean(value);

/** Same rule as the API: 5–8 letters or digits after normalizing (e.g. AB2C34D). */
export const isValidPlate = (value: string) => /^[A-Z0-9]{5,8}$/.test(normalizePlate(value));

/** The API accepts at most this many vehicle photos. */
export const MAX_VEHICLE_PHOTOS = 10;

export function vehicleYearRange(config: AppConfig, type: VehicleType, today: Date = new Date()) {
  return { min: config.vehicle_min_year[type] ?? 1950, max: today.getFullYear() + 1 };
}

export function isValidVehicleYear(year: number, config: AppConfig, type: VehicleType, today: Date = new Date()) {
  const { min, max } = vehicleYearRange(config, type, today);
  return Number.isInteger(year) && year >= min && year <= max;
}

// ── Documents and requirements ──

export type DocumentState = 'missing' | 'partial' | DocumentStatus;

export interface DocumentChecklistItem {
  kind: DocumentKind;
  state: DocumentState;
  /** Files uploaded for this kind (newest first). */
  documents: DriverDocument[];
  uploaded: number;
  required: number;
  rejectionReason: string | null;
}

export function requiredCount(kind: DocumentKind, config: AppConfig) {
  return kind === 'vehicle_photo' ? Math.max(1, config.vehicle_photo_min_count) : 1;
}

export function documentChecklist(profile: DriverProfile | null | undefined, config: AppConfig): DocumentChecklistItem[] {
  return config.driver_required_documents.map((kind) => {
    const documents = (profile?.documents ?? [])
      .filter((doc) => doc.kind === kind)
      .sort((a, b) => b.created_at.localeCompare(a.created_at));
    const required = requiredCount(kind, config);
    const relevant = MULTI_FILE_KINDS.includes(kind) ? documents : documents.slice(0, 1);
    const rejected = relevant.find((doc) => doc.status === 'rejected');
    const valid = relevant.filter((doc) => doc.status !== 'rejected');
    let state: DocumentState;
    if (rejected) state = 'rejected';
    else if (valid.length === 0) state = 'missing';
    else if (valid.length < required) state = 'partial';
    else if (valid.every((doc) => doc.status === 'approved')) state = 'approved';
    else state = 'pending';
    return {
      kind,
      state,
      documents,
      uploaded: valid.length,
      required,
      rejectionReason: rejected?.rejection_reason ?? null,
    };
  });
}

export const isDocumentDone = (item: DocumentChecklistItem) => item.state === 'pending' || item.state === 'approved';

export type DriverStep = 'personal' | 'vehicle' | 'documents' | 'review';
export const DRIVER_STEPS: readonly DriverStep[] = ['personal', 'vehicle', 'documents', 'review'];

export interface RequirementItem {
  key: 'personal' | 'age' | 'vehicle' | 'vehicle_year' | 'documents';
  done: boolean;
}

/** Overall checklist shown on the onboarding intro and the review step. */
export function requirementChecklist(profile: DriverProfile | null | undefined, config: AppConfig) {
  const documents = documentChecklist(profile, config);
  const items: RequirementItem[] = [
    { key: 'personal', done: !!profile },
    { key: 'age', done: !!profile && profile.requirements.age_ok },
    { key: 'vehicle', done: !!profile?.vehicle },
    { key: 'vehicle_year', done: !!profile?.vehicle && profile.requirements.vehicle_ok },
    { key: 'documents', done: documents.every(isDocumentDone) },
  ];
  const done = items.filter((item) => item.done).length;
  return { items, documents, done, total: items.length, complete: done === items.length };
}

/** First step that still needs work. */
export function nextDriverStep(profile: DriverProfile | null | undefined, config: AppConfig): DriverStep {
  if (!profile || !profile.requirements.age_ok) return 'personal';
  if (!profile.vehicle || !profile.requirements.vehicle_ok) return 'vehicle';
  if (!documentChecklist(profile, config).every(isDocumentDone)) return 'documents';
  return 'review';
}

/** Content types accepted by POST /drivers/me/documents/presign. */
export const ACCEPTED_CONTENT_TYPES = ['image/jpeg', 'image/png', 'image/webp', 'image/heic', 'application/pdf'];

export function contentTypeFor(filename: string, mimeType?: string | null): string | null {
  const mime = mimeType?.toLowerCase();
  if (mime === 'image/jpg') return 'image/jpeg';
  if (mime && ACCEPTED_CONTENT_TYPES.includes(mime)) return mime;
  const ext = filename.split('.').pop()?.toLowerCase();
  const byExt: Record<string, string> = {
    jpg: 'image/jpeg',
    jpeg: 'image/jpeg',
    png: 'image/png',
    webp: 'image/webp',
    heic: 'image/heic',
    pdf: 'application/pdf',
  };
  return (ext && byExt[ext]) || null;
}
