import { Stack } from 'expo-router';

import { useTheme } from '@/theme';

export const unstable_settings = { initialRouteName: '(tabs)' };

/** Signed-in area: the tabs plus full-screen flows pushed over them (driver onboarding). */
export default function AppLayout() {
  const theme = useTheme();
  return (
    <Stack screenOptions={{ headerShown: false, contentStyle: { backgroundColor: theme.background } }}>
      <Stack.Screen name="(tabs)" />
      <Stack.Screen name="driver" />
    </Stack>
  );
}
