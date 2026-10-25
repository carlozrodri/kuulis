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

it('es and en use the same {{placeholders}} in every string', () => {
  const values = (obj: Record<string, unknown>, prefix = ''): [string, string][] =>
    Object.entries(obj).flatMap(([k, v]) =>
      v && typeof v === 'object' ? values(v as Record<string, unknown>, `${prefix}${k}.`) : [[`${prefix}${k}`, String(v)]],
    );
  const placeholders = (text: string) => [...text.matchAll(/{{\s*(\w+)\s*}}/g)].map((m) => m[1]).sort().join(',');
  const english = Object.fromEntries(values(en));
  const mismatched = values(es)
    .filter(([key, text]) => placeholders(text) !== placeholders(english[key] ?? ''))
    .map(([key]) => key);
  expect(mismatched).toEqual([]);
});

it('every static translation key used in src exists in es', () => {
  // eslint-disable-next-line @typescript-eslint/no-require-imports
  const fs = require('fs') as typeof import('fs');
  // eslint-disable-next-line @typescript-eslint/no-require-imports
  const path = require('path') as typeof import('path');
  const files: string[] = [];
  const walk = (dir: string) => {
    for (const entry of fs.readdirSync(dir, { withFileTypes: true })) {
      const full = path.join(dir, entry.name);
      if (entry.isDirectory()) walk(full);
      else if (/\.tsx?$/.test(entry.name)) files.push(full);
    }
  };
  walk(path.join(__dirname, '..', 'src'));
  const known = new Set(keys(es));
  const missing = files.flatMap((file) =>
    [...fs.readFileSync(file, 'utf8').matchAll(/\bt\(\s*['"]([a-zA-Z0-9_.]+)['"]/g)]
      .map((m) => m[1])
      // Plural keys exist only with their suffixes (trips_one / trips_other).
      .filter((key) => !known.has(key) && !known.has(`${key}_other`)),
  );
  expect(missing).toEqual([]);
});
