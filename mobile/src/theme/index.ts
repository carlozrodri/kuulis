import { useColorScheme } from 'react-native';

const palette = {
  light: { background: '#FFFFFF', surface: '#F4F5F7', text: '#0F172A', muted: '#64748B', primary: '#4F46E5', danger: '#DC2626', border: '#E2E8F0' },
  dark: { background: '#0B1120', surface: '#151E32', text: '#F1F5F9', muted: '#94A3B8', primary: '#818CF8', danger: '#F87171', border: '#1E293B' },
};

export type Theme = typeof palette.light;

export function useTheme(): Theme {
  return palette[useColorScheme() === 'dark' ? 'dark' : 'light'];
}
