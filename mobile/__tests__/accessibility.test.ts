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
];

describe.each(['light', 'dark'] as const)('%s theme contrast', (scheme) => {
  it.each(PAIRS)('%s on %s reaches AA (4.5:1)', (fg, bg) => {
    expect(contrast(palette[scheme][fg] as string, palette[scheme][bg] as string)).toBeGreaterThanOrEqual(4.5);
  });
});
