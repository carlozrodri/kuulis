import { expect, it } from '@jest/globals';

import exported from '@/i18n/api-error-codes.json';
import { ADMIN_ONLY_ERROR_CODES } from '@/i18n/apiErrors';
import en from '@/i18n/locales/en.json';
import es from '@/i18n/locales/es.json';

// Doc 20: a new error code in the API fails here until the app can say it in both languages.
const appCodes = Object.keys(exported.codes).filter((code) => !ADMIN_ONLY_ERROR_CODES.has(code));

it('every API error code the app can receive has a Spanish text', () => {
  expect(appCodes.filter((code) => !(code in es.errors))).toEqual([]);
});

it('every API error code the app can receive has an English text', () => {
  expect(appCodes.filter((code) => !(code in en.errors))).toEqual([]);
});

it('the admin-only list names only codes the API still has', () => {
  expect([...ADMIN_ONLY_ERROR_CODES].filter((code) => !(code in exported.codes))).toEqual([]);
});
