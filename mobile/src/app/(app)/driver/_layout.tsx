import { Stack } from 'expo-router';

import { useTheme } from '@/theme';

/** Driver onboarding steps, pushed over the tabs (no tab bar). */
export default function DriverLayout() {
  const theme = useTheme();
  return <Stack screenOptions={{ headerShown: false, contentStyle: { backgroundColor: theme.background } }} />;
}
