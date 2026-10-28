import '@/i18n';
// Registers the driver's background location task at startup (TaskManager needs it in the global scope).
import '@/lib/backgroundLocation';

// Per-weight imports so only the five weights we use are bundled.
import { PlusJakartaSans_400Regular } from '@expo-google-fonts/plus-jakarta-sans/400Regular';
import { PlusJakartaSans_500Medium } from '@expo-google-fonts/plus-jakarta-sans/500Medium';
import { PlusJakartaSans_600SemiBold } from '@expo-google-fonts/plus-jakarta-sans/600SemiBold';
import { PlusJakartaSans_700Bold } from '@expo-google-fonts/plus-jakarta-sans/700Bold';
import { PlusJakartaSans_800ExtraBold } from '@expo-google-fonts/plus-jakarta-sans/800ExtraBold';
import NetInfo from '@react-native-community/netinfo';
import { onlineManager, QueryClient } from '@tanstack/react-query';
import { PersistQueryClientProvider } from '@tanstack/react-query-persist-client';
import { useFonts } from 'expo-font';
import { Stack, usePathname, type ErrorBoundaryProps } from 'expo-router';
import * as SplashScreen from 'expo-splash-screen';
import { StatusBar } from 'expo-status-bar';
import * as SystemUI from 'expo-system-ui';
import { useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Pressable, StyleSheet, Text, View } from 'react-native';
import { GestureHandlerRootView } from 'react-native-gesture-handler';

import { usePushNotifications } from '@/hooks/usePushNotifications';
import { setAnalyticsEnabled, startAnalytics, track } from '@/lib/analytics';
import { screenName, usageAllowed } from '@/lib/analyticsCore';
import { installCrashReporting, reportError, setCrashRoute } from '@/lib/crashReport';
import { homeRoute } from '@/lib/homeRoute';
import {
  keepPersistedQueries,
  PERSIST_BUSTER,
  PERSIST_MAX_AGE,
  queryPersister,
  shouldPersistQuery,
} from '@/lib/queryPersistence';
import { AuthProvider, useAuth } from '@/providers/AuthProvider';
import { ModeProvider, useMode } from '@/providers/ModeProvider';
import { loadThemePreference, useTheme } from '@/theme';

// Uncaught JS errors and the last native crash (Android) are sent to the API logs.
installCrashReporting();
// Anonymous usage events (doc 19), off when the user opted out in Profile.
startAnalytics();
// React Query pauses requests without signal (and resumes them) instead of failing and showing errors (doc 20).
onlineManager.setEventListener((setOnline) =>
  NetInfo.addEventListener((state) => setOnline(state.isConnected !== false && state.isInternetReachable !== false)),
);
// Light / dark chosen in Profile (read while the splash is still up).
void loadThemePreference();

// Keep the native splash until fonts, the session and the chosen mode are ready.
void SplashScreen.preventAutoHideAsync().catch(() => undefined);
SplashScreen.setOptions({ duration: 250, fade: true });

function RootNavigator({ fontsReady }: { fontsReady: boolean }) {
  const theme = useTheme();
  const { user, isLoading } = useAuth();
  const { mode, isLoading: modeLoading } = useMode();
  usePushNotifications(!!user);
  const pathname = usePathname();
  useEffect(() => {
    setCrashRoute(pathname);
  }, [pathname]);
  useEffect(() => {
    track('screen_view', { screen: screenName(pathname), ...(mode ? { mode } : {}) });
  }, [pathname, mode]);
  // The signed-in user's answer wins; signed out, the last answer seen on this phone stays.
  useEffect(() => {
    if (user) void setAnalyticsEnabled(usageAllowed(user.consents, true));
  }, [user]);

  const ready = fontsReady && !isLoading && !modeLoading;
  const pendingLegal = !!user?.pending_legal?.length;

  useEffect(() => {
    void SystemUI.setBackgroundColorAsync(theme.background).catch(() => undefined);
  }, [theme.background]);

  useEffect(() => {
    if (ready) SplashScreen.hide();
  }, [ready]);

  if (!ready) return null;

  const home = homeRoute({ signedIn: !!user, pendingLegal, hasMode: !!mode });

  return (
    <Stack screenOptions={{ headerShown: false, contentStyle: { backgroundColor: theme.background }, animation: 'fade' }}>
      <Stack.Protected guard={!user} redirectTo={home}>
        <Stack.Screen name="(auth)" />
      </Stack.Protected>
      {/* New or updated terms (doc 07): nothing else opens until they are accepted. */}
      <Stack.Protected guard={!!user && pendingLegal} redirectTo={home}>
        <Stack.Screen name="accept-terms" />
      </Stack.Protected>
      <Stack.Protected guard={!!user && !pendingLegal && !mode} redirectTo={home}>
        <Stack.Screen name="welcome" />
      </Stack.Protected>
      <Stack.Protected guard={!!user && !pendingLegal && !!mode} redirectTo={home}>
        <Stack.Screen name="(app)" />
      </Stack.Protected>
      {/* Legal texts open from the sign-up form, the acceptance screen and Profile. */}
      <Stack.Screen name="legal/[kind]" options={{ animation: 'slide_from_right' }} />
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
  const [queryClient] = useState(() => {
    const client = new QueryClient({ defaultOptions: { queries: { staleTime: 30_000, retry: 1 } } });
    keepPersistedQueries(client);
    return client;
  });
  return (
    // Gestures (the draggable map sheet) need the root view.
    <GestureHandlerRootView style={StyleSheet.absoluteFill}>
      {/* History, wallet and profile data are kept on the phone and shown when it opens offline (doc 20). */}
      <PersistQueryClientProvider
        client={queryClient}
        persistOptions={{
          persister: queryPersister,
          maxAge: PERSIST_MAX_AGE,
          buster: PERSIST_BUSTER,
          dehydrateOptions: { shouldDehydrateQuery: shouldPersistQuery },
        }}>
        <AuthProvider>
          <ModeProvider>
            <StatusBar style="auto" />
            {/* A font error falls back to the system font rather than blocking the app. */}
            <RootNavigator fontsReady={fontsLoaded || !!fontError} />
          </ModeProvider>
        </AuthProvider>
      </PersistQueryClientProvider>
    </GestureHandlerRootView>
  );
}

/**
 * A screen that throws while rendering shows this instead of closing the app; the error goes to the API
 * logs. Rendered outside the providers, so it only uses plain components.
 */
export function ErrorBoundary({ error, retry }: ErrorBoundaryProps) {
  const { t } = useTranslation();
  const theme = useTheme();
  useEffect(() => {
    void reportError('render', error);
  }, [error]);
  return (
    <View style={{ flex: 1, alignItems: 'center', justifyContent: 'center', padding: 32, gap: 16, backgroundColor: theme.background }}>
      <Text style={{ fontSize: 22, fontWeight: '700', color: theme.text, textAlign: 'center' }}>{t('crash.title')}</Text>
      <Text style={{ fontSize: 16, color: theme.muted, textAlign: 'center' }}>{t('crash.body')}</Text>
      <Pressable
        accessibilityRole="button"
        onPress={() => void retry()}
        style={{ backgroundColor: theme.primary, borderRadius: 999, paddingHorizontal: 28, paddingVertical: 14 }}>
        <Text style={{ color: theme.onPrimary, fontSize: 16, fontWeight: '700' }}>{t('crash.retry')}</Text>
      </Pressable>
    </View>
  );
}
