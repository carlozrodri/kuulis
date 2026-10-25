import { describe, expect, it } from '@jest/globals';

import { palette, type ThemeColors } from '@/theme';

/** WCAG 2.1 contrast ratio between two #RRGGBB colors. */
function contrast(a: string, b: string): number {
  const luminance = (hex: string) => {
    const [r, g, bl] = [1, 3, 5]
      .map((i) => parseInt(hex.slice(i, i + 2), 16) / 255)
      .map((v) => (v <= 0.03928 ? v / 12.92 : ((v + 0.055) / 1.055) ** 2.4));
    return 0.2126 * r + 0.7152 * g + 0.0722 * bl;
  };
  const [hi, lo] = [luminance(a), luminance(b)].sort((x, y) => y - x);
  return (hi + 0.05) / (lo + 0.05);
}

// Text color on the background it is used on (doc 20: AA, 4.5:1, in light and dark).
const PAIRS: [keyof ThemeColors, keyof ThemeColors][] = [
  ['text', 'background'],
  ['text', 'surface'],
  ['text', 'surfaceAlt'],
  ['muted', 'background'],
  ['muted', 'surface'],
  ['muted', 'surfaceAlt'],
  ['onPrimary', 'primary'],
  ['onAccent', 'accent'],
  ['onHero', 'hero'],
  ['onAccentSoft', 'accentSoft'],
  ['success', 'successSoft'],
  ['warning', 'warningSoft'],
  ['danger', 'dangerSoft'],
  ['info', 'infoSoft'],
  ['danger', 'surface'],
  ['primary', 'surface'],
  ['onDisabled', 'disabled'],
  ['navIcon', 'nav'],
  ['onDangerStrong', 'dangerStrong'],
];

// Outlines of controls that must be seen to be used (unchecked radio, checkbox, switch track, empty star): 3:1 (WCAG 1.4.11).
const CONTROL_OUTLINES: [keyof ThemeColors, keyof ThemeColors][] = [
  ['muted', 'background'],
  ['muted', 'surface'],
  ['muted', 'surfaceAlt'],
  ['primary', 'surface'],
  ['primary', 'background'],
];

describe.each(['light', 'dark'] as const)('%s theme contrast', (scheme) => {
  it.each(PAIRS)('%s on %s reaches AA (4.5:1)', (fg, bg) => {
    expect(contrast(palette[scheme][fg] as string, palette[scheme][bg] as string)).toBeGreaterThanOrEqual(4.5);
  });

  it.each(CONTROL_OUTLINES)('control outline %s on %s reaches 3:1', (fg, bg) => {
    expect(contrast(palette[scheme][fg] as string, palette[scheme][bg] as string)).toBeGreaterThanOrEqual(3);
  });
});

describe('source checks', () => {
  // eslint-disable-next-line @typescript-eslint/no-require-imports
  const fs = require('fs') as typeof import('fs');
  // eslint-disable-next-line @typescript-eslint/no-require-imports
  const path = require('path') as typeof import('path');
  const files: string[] = [];
  const walk = (dir: string) => {
    for (const entry of fs.readdirSync(dir, { withFileTypes: true })) {
      const full = path.join(dir, entry.name);
      if (entry.isDirectory()) walk(full);
      else if (entry.name.endsWith('.tsx')) files.push(full);
    }
  };
  walk(path.join(__dirname, '..', 'src'));
  const sources = files.map((file) => ({ file: path.relative(path.join(__dirname, '..'), file), text: fs.readFileSync(file, 'utf8') }));
  const lineOf = (text: string, index: number) => text.slice(0, index).split('\n').length;

  it('every Pressable tells screen readers what it is', () => {
    const missing = sources.flatMap(({ file, text }) =>
      [...text.matchAll(/<Pressable\b([^>]*?)>/gs)]
        .filter((m) => !/accessibilityRole|\{\.\.\./.test(m[1]))
        .map((m) => `${file}:${lineOf(text, m.index ?? 0)}`),
    );
    expect(missing).toEqual([]);
  });

  it('text is never faded with opacity (it drops below 4.5:1)', () => {
    const faded = sources.flatMap(({ file, text }) =>
      [...text.matchAll(/<Txt\b[^>]*?opacity:\s*0?\.\d+[^>]*>/gs)].map((m) => `${file}:${lineOf(text, m.index ?? 0)}`),
    );
    expect(faded).toEqual([]);
  });

  it('white text only sits on fills made for it', () => {
    // A literal white on a theme color fails in dark mode (e.g. white on the light red danger is 2.8:1).
    const literal = sources.flatMap(({ file, text }) =>
      [...text.matchAll(/<Txt\b[^>]*?color:\s*['"]#FFF(FFF)?['"][^>]*>/gis)].map((m) => `${file}:${lineOf(text, m.index ?? 0)}`),
    );
    expect(literal).toEqual([]);
  });
});
