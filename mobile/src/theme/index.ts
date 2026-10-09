import { useColorScheme } from 'react-native';

/**
 * Kuulis design system v1 ("Verde Ávila"). Source of truth: docs/product/mobile-design.md.
 * Light and dark follow the system setting.
 */
const light = {
  primary: '#0E7C5A',
  primaryPressed: '#0B6A4C',
  onPrimary: '#FFFFFF',
  accent: '#FFC83D',
  onAccent: '#3A2A00',
  background: '#F3F7F4',
  surface: '#FFFFFF',
  surfaceAlt: '#EAF5EF',
  text: '#14201B',
  muted: '#5B6A63',
  border: '#DCE6E0',
  divider: '#EDF2EF',
  success: '#15803D',
  warning: '#B45309',
  danger: '#B42318',
  info: '#1D4ED8',
  // Soft tints for pills, banners and icon tiles.
  successSoft: '#DCF3E4',
  warningSoft: '#FFF4E0',
  dangerSoft: '#FDECEC',
  infoSoft: '#E6EEFD',
  accentSoft: '#FFF4D6',
  onAccentSoft: '#5C4300',
  // Floating bottom navigation (dark ink in both modes).
  nav: '#14201B',
  navIcon: '#9AADA4',
  // Green header used on welcome and auth screens.
  hero: '#0E7C5A',
  heroShade: '#0B6A4C',
  onHero: '#FFFFFF',
  disabled: '#DCE6E0',
  onDisabled: '#5B6A63',
  shadow: '#14201B',
  backdrop: 'rgba(11, 19, 16, 0.45)',
};

export type ThemeColors = typeof light;

const dark: ThemeColors = {
  primary: '#34C08C',
  primaryPressed: '#2AA77A',
  onPrimary: '#04140D',
  accent: '#FFD25E',
  onAccent: '#2A1E00',
  background: '#0B1310',
  surface: '#131D18',
  surfaceAlt: '#1A2721',
  text: '#E7EFEB',
  muted: '#9AADA4',
  border: '#23322B',
  divider: '#1C2923',
  success: '#4ADE80',
  warning: '#FBBF24',
  danger: '#F87171',
  info: '#60A5FA',
  successSoft: '#12291C',
  warningSoft: '#2B2210',
  dangerSoft: '#2C1515',
  infoSoft: '#142036',
  accentSoft: '#2A2410',
  onAccentSoft: '#FFD25E',
  nav: '#1A2721',
  navIcon: '#9AADA4',
  hero: '#0E5E45',
  heroShade: '#0A4A36',
  onHero: '#FFFFFF',
  disabled: '#23322B',
  onDisabled: '#9AADA4',
  shadow: '#000000',
  backdrop: 'rgba(0, 0, 0, 0.6)',
};

export const palette = { light, dark };

export type Theme = ThemeColors & { scheme: 'light' | 'dark' };

const themes: Record<'light' | 'dark', Theme> = {
  light: { ...light, scheme: 'light' },
  dark: { ...dark, scheme: 'dark' },
};

export function useTheme(): Theme {
  return themes[useColorScheme() === 'dark' ? 'dark' : 'light'];
}

/** Spacing in multiples of 4. */
export const space = {
  xxs: 4,
  xs: 8,
  sm: 12,
  md: 16,
  lg: 20,
  xl: 24,
  xxl: 32,
  xxxl: 40,
} as const;

export const radius = {
  field: 12,
  chip: 12,
  tile: 16,
  card: 20,
  sheet: 28,
  pill: 999,
} as const;

/** Plus Jakarta Sans families. Custom fonts on Android ignore fontWeight, so each weight is its own family. */
export const fonts = {
  regular: 'PlusJakartaSans_400Regular',
  medium: 'PlusJakartaSans_500Medium',
  semibold: 'PlusJakartaSans_600SemiBold',
  bold: 'PlusJakartaSans_700Bold',
  extrabold: 'PlusJakartaSans_800ExtraBold',
} as const;

export const type = {
  display: { fontFamily: fonts.extrabold, fontSize: 32, lineHeight: 38, letterSpacing: -0.6 },
  title: { fontFamily: fonts.extrabold, fontSize: 26, lineHeight: 32, letterSpacing: -0.5 },
  heading: { fontFamily: fonts.extrabold, fontSize: 22, lineHeight: 28, letterSpacing: -0.3 },
  subtitle: { fontFamily: fonts.extrabold, fontSize: 17, lineHeight: 23 },
  body: { fontFamily: fonts.medium, fontSize: 15, lineHeight: 22 },
  bodyStrong: { fontFamily: fonts.bold, fontSize: 15, lineHeight: 22 },
  label: { fontFamily: fonts.semibold, fontSize: 13, lineHeight: 18 },
  caption: { fontFamily: fonts.medium, fontSize: 13, lineHeight: 18 },
  micro: { fontFamily: fonts.bold, fontSize: 12, lineHeight: 16 },
  overline: { fontFamily: fonts.bold, fontSize: 12, lineHeight: 16, letterSpacing: 1.2, textTransform: 'uppercase' },
  button: { fontFamily: fonts.extrabold, fontSize: 15, letterSpacing: 0.9 },
} as const;

export type TypeVariant = keyof typeof type;

/** Soft drop shadow for floating cards. */
export function elevation(theme: Theme, level: 1 | 2 = 1) {
  return {
    shadowColor: theme.shadow,
    shadowOpacity: theme.scheme === 'dark' ? 0.4 : level === 1 ? 0.08 : 0.16,
    shadowRadius: level === 1 ? 12 : 20,
    shadowOffset: { width: 0, height: level === 1 ? 6 : 10 },
    elevation: level === 1 ? 2 : 8,
  };
}
