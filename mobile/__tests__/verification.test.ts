import { describe, expect, it } from '@jest/globals';

import { ApiError } from '@/lib/api';
import { DEFAULT_APP_CONFIG } from '@/lib/driver';
import type { AppConfig, DriverDocument, DriverProfile, VerificationState } from '@/lib/types';
import {
  blockHref,
  checkInReview,
  dashboardAlert,
  daysUntil,
  documentBadge,
  expiryLabel,
  myDocuments,
  needsAttention,
  needsExpiry,
  onlineBlock,
  onlineBlockFromError,
  optionalChecklist,
  optionalKinds,
  parseExpiryInput,
  photosNeeded,
  requestedCheck,
  todayIso,
  verificationConfig,
  verificationHrefOf,
  warningWindow,
} from '@/lib/verification';

const TODAY = new Date(2026, 9, 13, 10, 30); // 13 Oct 2026, local time

const doc = (overrides: Partial<DriverDocument> = {}): DriverDocument => ({
  id: 'd1',
  kind: 'drivers_license',
  status: 'approved',
  content_type: 'image/jpeg',
  rejection_reason: null,
  expires_on: null,
  expiry_confirmed: false,
  created_at: '2026-01-01T10:00:00Z',
  ...overrides,
});

const profile = (documents: DriverDocument[], overrides: Partial<DriverProfile> = {}): DriverProfile => ({
  id: 'p1',
  user_id: 'u1',
  status: 'approved',
  birth_date: '1990-01-01',
  national_id: 'V12345678',
  rif: 'V123456789',
  phone: '+584121234567',
  city: 'Caracas',
  rejection_reason: null,
  submitted_at: null,
  reviewed_at: null,
  approved_at: null,
  vehicle: null,
  documents,
  requirements: {
    missing_documents: [],
    vehicle_photos: 2,
    vehicle_photos_required: 2,
    age_ok: true,
    vehicle_ok: true,
    can_submit: true,
  },
  ...overrides,
});

const state = (overrides: Partial<VerificationState> = {}): VerificationState => ({
  expired: [],
  expiring: [],
  missing_expiry: [],
  required_check_id: null,
  required_check_kind: null,
  can_go_online: true,
  ...overrides,
});

describe('config', () => {
  it('falls back to the documented defaults when the server omits verification', () => {
    const config: AppConfig = { ...DEFAULT_APP_CONFIG, verification: undefined };
    expect(verificationConfig(config).expiring_documents).toEqual(['drivers_license', 'medical_certificate', 'vehicle_registration']);
    expect(needsExpiry('drivers_license', config)).toBe(true);
    expect(needsExpiry('id_card', config)).toBe(false);
    expect(warningWindow(config)).toBe(30);
    expect(optionalKinds(config)).toEqual(['criminal_record']);
  });

  it('does not list an optional kind that is already required', () => {
    const config: AppConfig = {
      ...DEFAULT_APP_CONFIG,
      driver_required_documents: [...DEFAULT_APP_CONFIG.driver_required_documents, 'criminal_record'],
    };
    expect(optionalKinds(config)).toEqual([]);
  });

  it('builds the optional checklist apart from the required one', () => {
    const items = optionalChecklist(profile([doc({ kind: 'criminal_record', status: 'pending' })]), DEFAULT_APP_CONFIG);
    expect(items).toHaveLength(1);
    expect(items[0]).toMatchObject({ kind: 'criminal_record', state: 'pending' });
  });
});

describe('dates', () => {
  it('formats today and counts calendar days', () => {
    expect(todayIso(TODAY)).toBe('2026-10-13');
    expect(daysUntil('2026-10-13', TODAY)).toBe(0);
    expect(daysUntil('2026-10-25', TODAY)).toBe(12);
    expect(daysUntil('2026-10-12', TODAY)).toBe(-1);
    expect(daysUntil('2027-10-13', TODAY)).toBe(365);
  });

  it('parses the typed expiry date', () => {
    expect(parseExpiryInput('31/12/2027', TODAY)).toEqual({ iso: '2027-12-31' });
    expect(parseExpiryInput('13/10/2026', TODAY)).toEqual({ iso: '2026-10-13' });
    expect(parseExpiryInput('12/10/2026', TODAY)).toEqual({ error: 'past' });
    expect(parseExpiryInput('31/02/2027', TODAY)).toEqual({ error: 'invalid' });
    expect(parseExpiryInput('01/01/2101', TODAY)).toEqual({ error: 'invalid' });
    expect(parseExpiryInput('1/1/27', TODAY)).toEqual({ error: 'invalid' });
  });

  it('labels the days left', () => {
    expect(expiryLabel(-3)).toEqual({ key: 'verification.badge.expired' });
    expect(expiryLabel(0)).toEqual({ key: 'verification.badge.today' });
    expect(expiryLabel(1)).toEqual({ key: 'verification.badge.tomorrow' });
    expect(expiryLabel(12)).toEqual({ key: 'verification.badge.inDays', count: 12 });
  });
});

describe('myDocuments', () => {
  const config = DEFAULT_APP_CONFIG;

  it('lists renewable kinds plus optional ones, most urgent first', () => {
    const items = myDocuments(
      profile([
        doc({ id: 'id', kind: 'id_card' }),
        doc({ id: 'lic', kind: 'drivers_license', expires_on: '2026-10-25' }),
        doc({ id: 'med', kind: 'medical_certificate', expires_on: '2026-10-01' }),
        doc({ id: 'reg', kind: 'vehicle_registration' }),
        doc({ id: 'selfie', kind: 'selfie' }),
      ]),
      config,
      TODAY,
    );
    expect(items.map((item) => [item.kind, item.state])).toEqual([
      ['medical_certificate', 'expired'],
      ['vehicle_registration', 'missing_expiry'],
      ['drivers_license', 'expiring'],
      ['id_card', 'valid'],
      ['rif', 'not_added'],
      ['criminal_record', 'not_added'],
    ]);
    expect(items.find((item) => item.kind === 'vehicle_registration')?.canSetExpiry).toBe(true);
    expect(items.find((item) => item.kind === 'criminal_record')?.optional).toBe(true);
    expect(needsAttention(items)).toBe(3);
  });

  it('keeps the file in use while a renewal is reviewed or after it is rejected', () => {
    const [inReview] = myDocuments(
      profile([
        doc({ id: 'old', expires_on: '2026-10-01' }),
        doc({ id: 'new', status: 'pending', expires_on: '2031-10-01', created_at: '2026-10-10T10:00:00Z' }),
      ]),
      config,
      TODAY,
    );
    expect(inReview).toMatchObject({ state: 'in_review', daysLeft: -12 });
    expect(inReview.inUse?.id).toBe('old');
    expect(inReview.renewal?.id).toBe('new');
    expect(documentBadge(inReview)).toEqual({ key: 'verification.badge.in_review', tone: 'info' });

    const [rejected] = myDocuments(
      profile([
        doc({ id: 'old', expires_on: '2026-11-30' }),
        doc({ id: 'new', status: 'rejected', rejection_reason: 'Borrosa', created_at: '2026-10-10T10:00:00Z' }),
      ]),
      config,
      TODAY,
    );
    expect(rejected.state).toBe('rejected');
    expect(documentBadge(rejected).tone).toBe('danger');
  });

  it('does not offer a date for a confirmed expiry', () => {
    const items = myDocuments(profile([doc({ expires_on: '2027-05-01', expiry_confirmed: true })]), config, TODAY);
    const license = items.find((item) => item.kind === 'drivers_license');
    expect(license).toMatchObject({ state: 'valid', canSetExpiry: false });
    expect(documentBadge(license!)).toEqual({ key: 'verification.badge.valid', tone: 'success' });
  });

  it('badges expiring and non-expiring documents', () => {
    const items = myDocuments(
      profile([doc({ expires_on: '2026-10-25' }), doc({ id: 'rif', kind: 'rif' })]),
      config,
      TODAY,
    );
    expect(documentBadge(items[0])).toEqual({ key: 'verification.badge.inDays', count: 12, tone: 'warning' });
    expect(documentBadge(items.find((item) => item.kind === 'rif')!)).toEqual({
      key: 'verification.badge.approved',
      tone: 'success',
    });
  });
});

describe('going online', () => {
  it('reads the block from the verification state', () => {
    expect(onlineBlock(state())).toBeNull();
    expect(onlineBlock(null)).toBeNull();
    expect(
      onlineBlock(
        state({
          can_go_online: false,
          expired: ['drivers_license'],
          expiring: [{ kind: 'drivers_license', expires_on: '2026-10-01', days_left: -12, renewal_pending: true }],
          required_check_id: 'c1',
          required_check_kind: 'selfie',
        }),
      ),
    ).toEqual({ reason: 'document_expired', kinds: ['drivers_license'], renewalPending: true });
    expect(
      onlineBlock(state({ can_go_online: false, required_check_id: 'c1', required_check_kind: 'reverification' })),
    ).toEqual({ reason: 'selfie_required', checkId: 'c1', checkKind: 'reverification' });
  });

  it('maps the 403 errors to an action', () => {
    const expired = new ApiError(403, 'document_expired', 'x', { kinds: ['medical_certificate'] });
    expect(onlineBlockFromError(expired)).toEqual({
      reason: 'document_expired',
      kinds: ['medical_certificate'],
      renewalPending: false,
    });
    const selfie = new ApiError(403, 'selfie_required', 'x', { check_id: 'c9', kind: 'selfie' });
    const block = onlineBlockFromError(selfie);
    expect(block).toEqual({ reason: 'selfie_required', checkId: 'c9', checkKind: 'selfie' });
    expect(blockHref(block!)).toEqual({ pathname: '/driver/selfie', params: { checkId: 'c9', kind: 'selfie' } });
    expect(blockHref(onlineBlockFromError(expired)!)).toEqual({ pathname: '/driver/my-documents' });
    expect(onlineBlockFromError(new ApiError(403, 'account_suspended', 'x'))).toBeNull();
    expect(onlineBlockFromError(new Error('network'))).toBeNull();
  });

  it('picks the most urgent dashboard banner', () => {
    expect(dashboardAlert(state())).toBeNull();
    expect(dashboardAlert(state({ missing_expiry: ['vehicle_registration'] }))).toEqual({
      reason: 'missing_expiry',
      kinds: ['vehicle_registration'],
    });
    expect(
      dashboardAlert(
        state({
          expiring: [
            { kind: 'drivers_license', expires_on: '2026-11-01', days_left: 19, renewal_pending: false },
            { kind: 'medical_certificate', expires_on: '2026-10-20', days_left: 7, renewal_pending: false },
            { kind: 'vehicle_registration', expires_on: '2026-10-14', days_left: 1, renewal_pending: true },
          ],
        }),
      ),
    ).toEqual({ reason: 'expiring', kind: 'medical_certificate', daysLeft: 7, count: 2 });
    expect(
      dashboardAlert(state({ can_go_online: false, required_check_id: 'c1', required_check_kind: 'selfie' }))?.reason,
    ).toBe('selfie_required');
  });
});

describe('checks', () => {
  const config = DEFAULT_APP_CONFIG;
  const check = (id: string, kind: 'selfie' | 'reverification' | 'vehicle_change', status: 'requested' | 'pending') => ({
    id,
    kind,
    status,
    reason: 'random',
    document_id: null,
    vehicle_id: null,
    requested_at: '2026-10-13T10:00:00Z',
    submitted_at: null,
    reviewed_at: null,
    result_reason: null,
  });

  it('finds the requested check and the one in review', () => {
    const p = profile([], {
      checks: [check('a', 'vehicle_change', 'pending'), check('b', 'reverification', 'requested'), check('c', 'selfie', 'pending')],
      verification: state({ required_check_id: 'b', required_check_kind: 'reverification', can_go_online: false }),
    });
    expect(requestedCheck(p)?.id).toBe('b');
    expect(requestedCheck(p, 'zzz')?.id).toBe('b');
    expect(requestedCheck(profile([]))).toBeNull();
    expect(checkInReview(p)?.id).toBe('c');
  });

  it('asks for moto photos only on a re-verification', () => {
    expect(photosNeeded('selfie', config)).toBe(0);
    expect(photosNeeded('reverification', config)).toBe(2);
    expect(photosNeeded('reverification', { ...config, vehicle_photo_min_count: 0 })).toBe(1);
  });
});

describe('notifications', () => {
  it('opens the screen that solves a doc 12 push', () => {
    expect(verificationHrefOf({ type: 'driver_status', event: 'selfie_requested', check_id: 'c1' })).toEqual({
      pathname: '/driver/selfie',
      params: { checkId: 'c1' },
    });
    expect(verificationHrefOf({ data: { type: 'driver_document', event: 'document_expiring' } })).toEqual({
      pathname: '/driver/my-documents',
    });
    expect(verificationHrefOf({ type: 'driver_status', event: 'vehicle_rejected' })).toEqual({
      pathname: '/driver/vehicle-change',
    });
    expect(verificationHrefOf({ type: 'driver_status', event: 'approved' })).toBeNull();
    expect(verificationHrefOf({ type: 'ride.offer', event: 'selfie_requested' })).toBeNull();
    expect(verificationHrefOf(null)).toBeNull();
  });
});
