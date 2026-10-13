import { describe, expect, it } from '@jest/globals';

import { ApiError } from '@/lib/api';
import {
  alertIdOf,
  autoShareActive,
  autoShareContacts,
  autoShareFields,
  autoShareMode,
  caracasMinutes,
  checkInAnswerOf,
  cleanPin,
  isSafetyNotification,
  liveShareMessage,
  needsPin,
  pinAttemptsLeft,
  pinErrorKind,
  secondsToAnswer,
  spacedPin,
} from '@/lib/safety';
import type { Ride, TrustedContact } from '@/lib/types';

const contact = (overrides: Partial<TrustedContact> = {}): TrustedContact => ({
  id: 'c1',
  name: 'María Pérez',
  phone: '+584141234567',
  auto_share: true,
  auto_share_from: null,
  auto_share_to: null,
  ...overrides,
});

// Caracas is UTC-4: 23:30 UTC is 19:30 there.
const caracas = (hh: number, mm = 0) => new Date(Date.UTC(2026, 9, 13, hh + 4, mm));

describe('PIN', () => {
  it('keeps four digits', () => {
    expect(cleanPin('12a3 45')).toBe('1234');
    expect(spacedPin('4821')).toBe('4 8 2 1');
    expect(spacedPin(null)).toBe('');
  });

  it('is asked only on arrival when the ride requires it', () => {
    expect(needsPin({ status: 'driver_arrived', pin_required: true })).toBe(true);
    expect(needsPin({ status: 'driver_assigned', pin_required: true })).toBe(false);
    expect(needsPin({ status: 'driver_arrived', pin_required: false })).toBe(false);
  });

  it('reads the API errors', () => {
    const wrong = new ApiError(400, 'pin_invalid', 'Wrong', { attempts_left: 2 });
    expect(pinErrorKind(wrong)).toBe('invalid');
    expect(pinAttemptsLeft(wrong)).toBe(2);
    expect(pinErrorKind(new ApiError(429, 'pin_attempts_exceeded', 'Locked'))).toBe('locked');
    expect(pinErrorKind(new ApiError(409, 'ride_invalid_transition', 'No'))).toBeNull();
    expect(pinErrorKind(new Error('network'))).toBeNull();
    expect(pinAttemptsLeft(new ApiError(400, 'pin_invalid', 'Wrong'))).toBeNull();
  });
});

describe('auto-share', () => {
  it('uses Caracas time', () => {
    expect(caracasMinutes(new Date(Date.UTC(2026, 0, 1, 2, 15)))).toBe(22 * 60 + 15);
  });

  it('is always on without hours and off when disabled', () => {
    expect(autoShareActive(contact(), caracas(12))).toBe(true);
    expect(autoShareActive(contact({ auto_share: false }), caracas(12))).toBe(false);
  });

  it('respects a window that crosses midnight', () => {
    const night = contact({ auto_share_from: '19:00', auto_share_to: '06:00' });
    expect(autoShareActive(night, caracas(19, 30))).toBe(true);
    expect(autoShareActive(night, caracas(2))).toBe(true);
    expect(autoShareActive(night, caracas(6))).toBe(false);
    expect(autoShareActive(night, caracas(12))).toBe(false);
  });

  it('respects a daytime window', () => {
    const day = contact({ auto_share_from: '08:00', auto_share_to: '17:00' });
    expect(autoShareActive(day, caracas(8))).toBe(true);
    expect(autoShareActive(day, caracas(17))).toBe(false);
  });

  it('filters the contacts due now', () => {
    const list = [contact(), contact({ id: 'c2', auto_share: false })];
    expect(autoShareContacts(list, caracas(12)).map((c) => c.id)).toEqual(['c1']);
    expect(autoShareContacts(undefined, caracas(12))).toEqual([]);
  });

  it('maps the form choice to API fields', () => {
    expect(autoShareMode(null)).toBe('off');
    expect(autoShareMode(contact())).toBe('always');
    expect(autoShareMode(contact({ auto_share_from: '20:00', auto_share_to: '05:00' }))).toBe('night');
    expect(autoShareFields('off')).toEqual({ auto_share: false, auto_share_from: null, auto_share_to: null });
    expect(autoShareFields('always')).toEqual({ auto_share: true, auto_share_from: null, auto_share_to: null });
    expect(autoShareFields('night')).toEqual({ auto_share: true, auto_share_from: '19:00', auto_share_to: '06:00' });
    // Custom hours the person already had are kept.
    expect(autoShareFields('night', { auto_share_from: '20:00', auto_share_to: '05:00' })).toEqual({
      auto_share: true,
      auto_share_from: '20:00',
      auto_share_to: '05:00',
    });
  });
});

describe('live link message', () => {
  it('fills the driver, plate, destination and url', () => {
    const ride = {
      driver: { first_name: 'Luis', vehicle: { plate: 'ab123cd' } },
      dropoff: { address: 'Sambil, Chacao, Caracas' },
    } as unknown as Ride;
    const t = (key: string, options?: Record<string, unknown>) => `${key} ${JSON.stringify(options)}`;
    const text = liveShareMessage(ride, 'https://kuulis.app/v/abc', t);
    expect(text).toContain('safety.live.message');
    expect(text).toContain('"plate":"AB1 23CD"');
    expect(text).toContain('"dropoff":"Sambil"');
    expect(liveShareMessage(ride, 'u', t, true)).toContain('safety.live.sosMessage');
  });
});

describe('notifications', () => {
  it('recognises check-in pushes and their buttons', () => {
    const data = { type: 'safety', event: 'check_in', alert_id: 'a1', ride_id: 'r1' };
    expect(isSafetyNotification(data)).toBe(true);
    expect(isSafetyNotification({ data })).toBe(true);
    expect(isSafetyNotification({ type: 'ride.updated' })).toBe(false);
    expect(alertIdOf(data)).toBe('a1');
    expect(alertIdOf({ data })).toBe('a1');
    expect(checkInAnswerOf('ok')).toBe('ok');
    expect(checkInAnswerOf('help')).toBe('help');
    expect(checkInAnswerOf('expo.modules.notifications.actions.DEFAULT')).toBeNull();
  });

  it('counts down to the deadline', () => {
    const now = Date.parse('2026-10-13T12:00:00Z');
    expect(secondsToAnswer('2026-10-13T12:01:30Z', now)).toBe(90);
    expect(secondsToAnswer('2026-10-13T11:59:00Z', now)).toBe(0);
    expect(secondsToAnswer(null, now)).toBeNull();
  });
});
