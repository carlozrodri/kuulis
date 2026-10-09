import { Stack } from 'expo-router';
import { View } from 'react-native';

import { ConnectionBanner } from '@/components/ConnectionBanner';
import { ToastHost } from '@/components/Toast';
import { DriverController, RideNavigator, RideSync } from '@/features/ride/RideController';
import { RealtimeProvider } from '@/hooks/useRealtime';
import { useAuth } from '@/providers/AuthProvider';
import { useMode } from '@/providers/ModeProvider';
import { useTheme } from '@/theme';

export const unstable_settings = { initialRouteName: '(tabs)' };

/**
 * Signed-in area: the tabs plus full-screen flows pushed over them (driver onboarding, ride screens).
 * Owns the realtime socket and the ride state machinery shared by every screen.
 */
export default function AppLayout() {
  const theme = useTheme();
  const { user } = useAuth();
  const { mode } = useMode();
  return (
    <RealtimeProvider enabled={!!user}>
      <View style={{ flex: 1, backgroundColor: theme.background }}>
        <Stack screenOptions={{ headerShown: false, contentStyle: { backgroundColor: theme.background } }}>
          <Stack.Screen name="(tabs)" />
          <Stack.Screen name="driver" />
          <Stack.Screen name="ride/search" options={{ animation: 'slide_from_bottom' }} />
          <Stack.Screen name="ride/pin" />
          <Stack.Screen name="ride/quote" />
          <Stack.Screen name="ride/index" />
          <Stack.Screen name="ride/chat" />
          <Stack.Screen name="ride/detail" />
          {/* Rating is mandatory: no swipe back. */}
          <Stack.Screen name="ride/rate" options={{ gestureEnabled: false, animation: 'slide_from_bottom' }} />
          <Stack.Screen name="drive" />
        </Stack>
        <RideSync />
        <RideNavigator />
        {mode === 'driver' ? <DriverController /> : null}
        <ConnectionBanner />
        <ToastHost />
      </View>
    </RealtimeProvider>
  );
}
