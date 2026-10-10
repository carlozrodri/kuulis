import { describe, expect, it } from '@jest/globals';

import { firstName, formatKm, initials, memberSince, missingProfileSteps, ratingValue } from '@/lib/profile';

describe('profile helpers', () => {
  it('builds initials from the name, then the email', () => {
    expect(initials('Ana María Pérez')).toBe('AM');
    expect(initials('  luis  ')).toBe('L');
    expect(initials('', 'carlos@example.com')).toBe('C');
    expect(initials(null, null)).toBe('?');
  });

  it('takes the first name', () => {
    expect(firstName(' Ana María ')).toBe('Ana');
    expect(firstName(undefined)).toBe('');
  });

  it('formats member since as month and year', () => {
    expect(memberSince('2026-10-09T12:00:00Z', 'es')).toMatch(/oct.*2026/i);
    expect(memberSince('2026-10-09T12:00:00Z', 'en')).toMatch(/Oct.*2026/);
    expect(memberSince('nope')).toBe('');
    expect(memberSince(null)).toBe('');
  });

  it('rounds kilometres', () => {
    expect(formatKm(9400)).toBe('9');
    expect(formatKm(0)).toBe('0');
    expect(formatKm(undefined)).toBe('0');
    expect(formatKm(1_250_000, 'en')).toBe('1,250');
  });

  it('shows a rating only when there is one', () => {
    expect(ratingValue(4.86)).toBe(4.9);
    expect(ratingValue('4.20')).toBe(4.2);
    expect(ratingValue(null)).toBeNull();
    expect(ratingValue(0)).toBeNull();
  });

  it('lists what is missing for a complete profile', () => {
    expect(missingProfileSteps(null)).toEqual([]);
    expect(missingProfileSteps({ avatar_key: null, full_name: 'Ana', is_verified: false })).toEqual(['photo', 'name', 'email']);
    expect(missingProfileSteps({ avatar_key: 'k', full_name: 'Ana Pérez', is_verified: true })).toEqual([]);
  });
});
