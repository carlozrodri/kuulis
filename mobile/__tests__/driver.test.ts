import { describe, expect, it } from '@jest/globals';

import {
  DEFAULT_APP_CONFIG,
  ageOn,
  contentTypeFor,
  documentChecklist,
  formatPhoneLocal,
  isOldEnough,
  isValidNationalId,
  isValidPlate,
  isValidRif,
  isValidVehicleYear,
  isoToDisplayDate,
  maskDateInput,
  nextDriverStep,
  normalizeNationalId,
  normalizePhone,
  normalizePlate,
  parseDisplayDate,
  requirementChecklist,
} from '@/lib/driver';
import type { DriverDocument, DriverProfile } from '@/lib/types';

const today = new Date(2026, 9, 9); // 9 Oct 2026

function doc(kind: DriverDocument['kind'], status: DriverDocument['status'] = 'pending', i = 0): DriverDocument {
  return {
    id: `${kind}-${i}`,
    kind,
    status,
    content_type: 'image/jpeg',
    rejection_reason: status === 'rejected' ? 'Borrosa' : null,
    created_at: `2026-10-0${i + 1}T10:00:00Z`,
  };
}

function profile(overrides: Partial<DriverProfile> = {}): DriverProfile {
  return {
    id: 'p',
    user_id: 'u',
    status: 'draft',
    birth_date: '1995-04-12',
    national_id: 'V12345678',
    rif: 'V123456789',
    phone: '+584121234567',
    city: 'caracas',
    rejection_reason: null,
    submitted_at: null,
    reviewed_at: null,
    approved_at: null,
    vehicle: null,
    documents: [],
    requirements: {
      missing_documents: [],
      vehicle_photos: 0,
      vehicle_photos_required: 2,
      age_ok: true,
      vehicle_ok: false,
      can_submit: false,
    },
    ...overrides,
  };
}

const allDocs = [
  doc('id_card'),
  doc('rif'),
  doc('drivers_license'),
  doc('medical_certificate'),
  doc('vehicle_registration'),
  doc('selfie'),
  doc('vehicle_photo', 'pending', 0),
  doc('vehicle_photo', 'pending', 1),
];
const vehicle = { id: 'v', type: 'moto' as const, brand: 'Bera', model: 'SBR', year: 2019, plate: 'AB2C34D', color: 'Negra' };

describe('dates and age', () => {
  it('masks and parses DD/MM/AAAA', () => {
    expect(maskDateInput('12041995')).toBe('12/04/1995');
    expect(maskDateInput('1204')).toBe('12/04');
    expect(parseDisplayDate('12/04/1995')).toBe('1995-04-12');
    expect(parseDisplayDate('31/02/2000')).toBeNull();
    expect(parseDisplayDate('1995-04-12')).toBeNull();
    expect(isoToDisplayDate('1995-04-12')).toBe('12/04/1995');
  });

  it('computes age on the birthday boundary', () => {
    expect(ageOn('2005-10-09', today)).toBe(21);
    expect(ageOn('2005-10-10', today)).toBe(20);
    expect(isOldEnough('2005-10-09', 21, today)).toBe(true);
    expect(isOldEnough('2005-10-10', 21, today)).toBe(false);
  });
});

describe('identifiers', () => {
  it('validates cédula and RIF', () => {
    expect(normalizeNationalId('12.345.678')).toBe('V12345678');
    expect(isValidNationalId('e-1234567')).toBe(true);
    expect(isValidNationalId('X123')).toBe(false);
    expect(isValidRif('V-12345678-9')).toBe(true);
    expect(isValidRif('J-12345678')).toBe(false);
  });

  it('normalizes Venezuelan mobiles', () => {
    expect(normalizePhone('0412-123.45.67')).toBe('+584121234567');
    expect(normalizePhone('+58 424 1234567')).toBe('+584241234567');
    expect(normalizePhone('0212 1234567')).toBeNull();
    expect(normalizePhone('+1 (305) 555-0100')).toBe('+13055550100');
    expect(normalizePhone('+12345')).toBeNull();
    expect(formatPhoneLocal('+584121234567')).toBe('0412 123 4567');
  });

  it('validates plates', () => {
    expect(normalizePlate(' ab-2c 34d ')).toBe('AB2C34D');
    expect(isValidPlate('AB2C34D')).toBe(true);
    expect(isValidPlate('AB.2C-34D')).toBe(true);
    expect(isValidPlate('ABCDEFGHI')).toBe(false);
    expect(isValidPlate('AB1')).toBe(false);
  });

  it('enforces the minimum vehicle year from config', () => {
    expect(isValidVehicleYear(2013, DEFAULT_APP_CONFIG, 'moto', today)).toBe(true);
    expect(isValidVehicleYear(2012, DEFAULT_APP_CONFIG, 'moto', today)).toBe(false);
    expect(isValidVehicleYear(2028, DEFAULT_APP_CONFIG, 'moto', today)).toBe(false);
  });
});

describe('requirements', () => {
  it('starts at personal data without a profile', () => {
    const checklist = requirementChecklist(null, DEFAULT_APP_CONFIG);
    expect(checklist.done).toBe(0);
    expect(nextDriverStep(null, DEFAULT_APP_CONFIG)).toBe('personal');
  });

  it('counts vehicle photos against the configured minimum', () => {
    const items = documentChecklist(profile({ documents: [doc('vehicle_photo')] }), DEFAULT_APP_CONFIG);
    const photos = items.find((item) => item.kind === 'vehicle_photo');
    expect(photos?.state).toBe('partial');
    expect(photos?.uploaded).toBe(1);
    expect(photos?.required).toBe(2);
  });

  it('flags rejected documents with their reason', () => {
    const items = documentChecklist(profile({ documents: [doc('selfie', 'rejected')] }), DEFAULT_APP_CONFIG);
    const selfie = items.find((item) => item.kind === 'selfie');
    expect(selfie?.state).toBe('rejected');
    expect(selfie?.rejectionReason).toBe('Borrosa');
  });

  it('walks the steps in order', () => {
    expect(nextDriverStep(profile(), DEFAULT_APP_CONFIG)).toBe('vehicle');
    const withVehicle = profile({ vehicle, requirements: { ...profile().requirements, vehicle_ok: true } });
    expect(nextDriverStep(withVehicle, DEFAULT_APP_CONFIG)).toBe('documents');
    const complete = { ...withVehicle, documents: allDocs };
    expect(nextDriverStep(complete, DEFAULT_APP_CONFIG)).toBe('review');
    expect(requirementChecklist(complete, DEFAULT_APP_CONFIG).complete).toBe(true);
  });

  it('only checks the documents the config requires', () => {
    const config = { ...DEFAULT_APP_CONFIG, driver_required_documents: ['id_card' as const] };
    expect(documentChecklist(profile(), config)).toHaveLength(1);
  });

  it('maps content types', () => {
    expect(contentTypeFor('a.JPG')).toBe('image/jpeg');
    expect(contentTypeFor('scan.pdf', 'application/pdf')).toBe('application/pdf');
    expect(contentTypeFor('file.gif', 'image/gif')).toBeNull();
  });
});
