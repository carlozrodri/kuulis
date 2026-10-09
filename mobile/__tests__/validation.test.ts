import { describe, expect, it } from '@jest/globals';

import { isEmail, isPassword } from '@/lib/validation';

describe('validation', () => {
  it('validates emails', () => {
    expect(isEmail('carlos@example.com')).toBe(true);
    expect(isEmail('not-an-email')).toBe(false);
  });

  it('requires 8+ character passwords', () => {
    expect(isPassword('short')).toBe(false);
    expect(isPassword('long-enough')).toBe(true);
  });
});
