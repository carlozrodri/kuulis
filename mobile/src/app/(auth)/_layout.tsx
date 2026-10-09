import { Stack } from 'expo-router';

import { useTheme } from '@/theme';

export const unstable_settings = { initialRouteName: 'login' };

export default function AuthLayout() {
  const theme = useTheme();
  return <Stack screenOptions={{ headerShown: false, contentStyle: { backgroundColor: theme.background } }} />;
}
