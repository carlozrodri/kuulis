import { Stack } from 'expo-router';
import { View } from 'react-native';

import { ConnectionBanner } from '@/components/ConnectionBanner';
import { ToastHost } from '@/components/Toast';
import { MaintenanceGate } from '@/features/control/MaintenanceScreen';
import { NotificationOpener } from '@/features/notifications/NotificationOpener';
import { OutboxSync } from '@/features/offline/OutboxSync';
import { DriverController, RideNavigator, RideSync } from '@/features/ride/RideController';
import { SafetyController } from '@/features/safety/SafetyController';
import { UpdateGate } from '@/features/update/UpdateGate';
import { BootstrapSync } from '@/hooks/useBootstrap';
import { QualitySync } from '@/hooks/useQuality';
import { RealtimeProvider } from '@/hooks/useRealtime';
import { useAuth } from '@/providers/AuthProvider';
import { useMode } from '@/providers/ModeProvider';
import { useTheme } from '@/theme';

export const unstable_settings = { anchor: '(tabs)' };

/**
 * Signed-in area: the tabs plus full-screen flows pushed over them (driver onboarding, ride screens, wallet
 * top-ups, transfers and fees, help and support conversations, profile editing).
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
          <Stack.Screen name="ride/lost-item" />
          {/* Rating is mandatory: no swipe back. */}
          <Stack.Screen name="ride/rate" options={{ gestureEnabled: false, animation: 'slide_from_bottom' }} />
          <Stack.Screen name="drive" />
          <Stack.Screen name="wallet/top-up" />
          <Stack.Screen name="wallet/transfer" />
          <Stack.Screen name="wallet/charges" />
          <Stack.Screen name="wallet/statement" />
          <Stack.Screen name="wallet/receipt" />
          <Stack.Screen name="wallet/dispute" />
          <Stack.Screen name="report" options={{ animation: 'slide_from_bottom' }} />
          <Stack.Screen name="reports/index" />
          <Stack.Screen name="reports/[id]" />
          <Stack.Screen name="help/index" />
          <Stack.Screen name="help/topic/[topic]" />
          <Stack.Screen name="help/article/[slug]" />
          <Stack.Screen name="profile/edit" />
          <Stack.Screen name="profile/password" />
          <Stack.Screen name="profile/place" options={{ animation: 'slide_from_bottom' }} />
          <Stack.Screen name="profile/contact" />
          <Stack.Screen name="profile/data" />
          <Stack.Screen name="profile/delete" />
          <Stack.Screen name="profile/about" />
          <Stack.Screen name="profile/settings" />
          <Stack.Screen name="profile/notifications" />
          <Stack.Screen name="profile/legal" />
          <Stack.Screen name="profile/payment" />
          <Stack.Screen name="profile/frequent" />
          <Stack.Screen name="profile/invite" />
        </Stack>
        {/* Remote control (doc 10): maintenance, city pauses, feature flags, banners and remote settings. */}
        <BootstrapSync />
        <RideSync />
        {/* Doc 20: ride actions, messages and ratings sent without signal go out when it comes back. */}
        <OutboxSync />
        {/* Doc 15: temporary pauses for quality (quality.paused) and "Mi calidad" refreshes. */}
        <QualitySync />
        <RideNavigator />
        {/* Doc 14: tapping a push (also the one that started the app) opens its screen. */}
        <NotificationOpener />
        {mode === 'driver' ? <DriverController /> : null}
        {/* Trip safety (doc 11): "¿Todo bien?", the open SOS banner and its live position. */}
        <SafetyController />
        {/* Maintenance (doc 10): covers home and ride requests, never a ride in progress. */}
        <MaintenanceGate />
        {/* Mandatory APK update (doc 09): covers everything above, except during a ride. */}
        <UpdateGate />
        <ConnectionBanner />
        <ToastHost />
      </View>
    </RealtimeProvider>
  );
}
