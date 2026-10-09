import '@/i18n';

// Per-weight imports so only the five weights we use are bundled.
import { PlusJakartaSans_400Regular } from '@expo-google-fonts/plus-jakarta-sans/400Regular';
import { PlusJakartaSans_500Medium } from '@expo-google-fonts/plus-jakarta-sans/500Medium';
import { PlusJakartaSans_600SemiBold } from '@expo-google-fonts/plus-jakarta-sans/600SemiBold';
import { PlusJakartaSans_700Bold } from '@expo-google-fonts/plus-jakarta-sans/700Bold';
import { PlusJakartaSans_800ExtraBold } from '@expo-google-fonts/plus-jakarta-sans/800ExtraBold';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { useFonts } from 'expo-font';
import { Stack } from 'expo-router';
import * as SplashScreen from 'expo-splash-screen';
import { StatusBar } from 'expo-status-bar';
import * as SystemUI from 'expo-system-ui';
import { useEffect, useState } from 'react';

import { usePushNotifications } from '@/hooks/usePushNotifications';
import { AuthProvider, useAuth } from '@/providers/AuthProvider';
import { ModeProvider, useMode } from '@/providers/ModeProvider';
import { useTheme } from '@/theme';

// Keep the native splash until fonts, the session and the chosen mode are ready.
void SplashScreen.preventAutoHideAsync().catch(() => undefined);
SplashScreen.setOptions({ duration: 250, fade: true });

function RootNavigator({ fontsReady }: { fontsReady: boolean }) {
  const theme = useTheme();
  const { user, isLoading } = useAuth();
  const { mode, isLoading: modeLoading } = useMode();
  usePushNotifications(!!user);

  const ready = fontsReady && !isLoading && !modeLoading;

  useEffect(() => {
    void SystemUI.setBackgroundColorAsync(theme.background).catch(() => undefined);
  }, [theme.background]);

  useEffect(() => {
    if (ready) SplashScreen.hide();
  }, [ready]);

  if (!ready) return null;

  return (
    <Stack screenOptions={{ headerShown: false, contentStyle: { backgroundColor: theme.background }, animation: 'fade' }}>
      <Stack.Protected guard={!user}>
        <Stack.Screen name="(auth)" />
      </Stack.Protected>
      <Stack.Protected guard={!!user && !mode}>
        <Stack.Screen name="welcome" />
      </Stack.Protected>
      <Stack.Protected guard={!!user && !!mode}>
        <Stack.Screen name="(app)" />
      </Stack.Protected>
    </Stack>
  );
}

export default function RootLayout() {
  const [fontsLoaded, fontError] = useFonts({
    PlusJakartaSans_400Regular,
    PlusJakartaSans_500Medium,
    PlusJakartaSans_600SemiBold,
    PlusJakartaSans_700Bold,
    PlusJakartaSans_800ExtraBold,
  });
  const [queryClient] = useState(
    () => new QueryClient({ defaultOptions: { queries: { staleTime: 30_000, retry: 1 } } }),
  );
  return (
    <QueryClientProvider client={queryClient}>
      <AuthProvider>
        <ModeProvider>
          <StatusBar style="auto" />
          {/* A font error falls back to the system font rather than blocking the app. */}
          <RootNavigator fontsReady={fontsLoaded || !!fontError} />
        </ModeProvider>
      </AuthProvider>
    </QueryClientProvider>
  );
}
