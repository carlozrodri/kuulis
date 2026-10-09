import { expect, it } from '@jest/globals';

import en from '@/i18n/locales/en.json';
import es from '@/i18n/locales/es.json';

function keys(obj: Record<string, unknown>, prefix = ''): string[] {
  return Object.entries(obj).flatMap(([k, v]) =>
    v && typeof v === 'object' ? keys(v as Record<string, unknown>, `${prefix}${k}.`) : [`${prefix}${k}`],
  );
}

it('es and en translations have the same keys', () => {
  expect(keys(en).sort()).toEqual(keys(es).sort());
});
