import * as AppleAuthentication from 'expo-apple-authentication';
import { useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { ActivityIndicator, Pressable, StyleSheet, Text, View } from 'react-native';
import Svg, { Path } from 'react-native-svg';

import { Divider, ErrorText, Notice } from '@/components/ui';
import { apiErrorMessage } from '@/i18n';
import { appleAvailable, appleCredential, googleAvailability, googleIdToken, SocialCancelled } from '@/lib/social';
import { useAuth } from '@/providers/AuthProvider';
import { fonts, radius, space, useTheme } from '@/theme';

function GoogleGlyph() {
  return (
    <Svg width={20} height={20} viewBox="0 0 48 48" accessibilityElementsHidden importantForAccessibility="no">
      <Path fill="#FFC107" d="M43.6 20.5H42V20H24v8h11.3C33.7 32.7 29.2 36 24 36c-6.6 0-12-5.4-12-12s5.4-12 12-12c3.1 0 5.8 1.2 7.9 3.1l5.7-5.7C34 6.1 29.3 4 24 4 12.9 4 4 12.9 4 24s8.9 20 20 20 20-8.9 20-20c0-1.3-.1-2.4-.4-3.5z" />
      <Path fill="#FF3D00" d="M6.3 14.7l6.6 4.8C14.7 15.1 19 12 24 12c3.1 0 5.8 1.2 7.9 3.1l5.7-5.7C34 6.1 29.3 4 24 4 16.3 4 9.7 8.3 6.3 14.7z" />
      <Path fill="#4CAF50" d="M24 44c5.2 0 9.9-2 13.4-5.2l-6.2-5.2C29.2 35.1 26.7 36 24 36c-5.2 0-9.6-3.3-11.3-7.9l-6.5 5C9.5 39.6 16.2 44 24 44z" />
      <Path fill="#1976D2" d="M43.6 20.5H42V20H24v8h11.3c-.8 2.2-2.2 4.2-4.1 5.6l6.2 5.2C37 39.2 44 34 44 24c0-1.3-.1-2.4-.4-3.5z" />
    </Svg>
  );
}

/**
 * "Continuar con Google" (when configured) and "Continuar con Apple" (iOS only) plus an "o" divider.
 * Renders nothing when no provider is offered on this build.
 */
export function SocialButtons({ onBusyChange }: { onBusyChange?: (busy: boolean) => void }) {
  const { t } = useTranslation();
  const theme = useTheme();
  const { signInWithGoogle, signInWithApple } = useAuth();
  const [google] = useState(googleAvailability);
  const [apple, setApple] = useState(false);
  const [busy, setBusy] = useState<'google' | 'apple' | null>(null);
  const [error, setError] = useState<string>();
  const [info, setInfo] = useState<string>();

  useEffect(() => {
    appleAvailable().then(setApple);
  }, []);

  async function run(provider: 'google' | 'apple', fn: () => Promise<void>) {
    setError(undefined);
    setInfo(undefined);
    setBusy(provider);
    onBusyChange?.(true);
    try {
      await fn();
    } catch (e) {
      if (!(e instanceof SocialCancelled)) setError(apiErrorMessage(e));
    } finally {
      setBusy(null);
      onBusyChange?.(false);
    }
  }

  const onGoogle = () => {
    if (google === 'unavailable') {
      setInfo(t('auth.social.installedOnly'));
      return;
    }
    void run('google', async () => signInWithGoogle(await googleIdToken()));
  };

  const onApple = () =>
    run('apple', async () => {
      const { idToken, fullName } = await appleCredential();
      await signInWithApple(idToken, fullName);
    });

  if (google === 'hidden' && !apple) return null;

  return (
    <View style={{ gap: space.sm }}>
      {apple ? (
        <View style={{ opacity: busy ? 0.6 : 1 }} pointerEvents={busy ? 'none' : 'auto'}>
          <AppleAuthentication.AppleAuthenticationButton
            buttonType={AppleAuthentication.AppleAuthenticationButtonType.CONTINUE}
            buttonStyle={
              theme.scheme === 'dark'
                ? AppleAuthentication.AppleAuthenticationButtonStyle.WHITE
                : AppleAuthentication.AppleAuthenticationButtonStyle.BLACK
            }
            cornerRadius={28}
            style={styles.apple}
            onPress={onApple}
          />
        </View>
      ) : null}
      {google !== 'hidden' ? (
        <Pressable
          accessibilityRole="button"
          accessibilityLabel={t('auth.social.google')}
          accessibilityState={{ disabled: !!busy, busy: busy === 'google' }}
          disabled={!!busy}
          onPress={onGoogle}
          style={({ pressed }) => [
            styles.google,
            { backgroundColor: pressed ? theme.surfaceAlt : theme.surface, borderColor: theme.border, opacity: google === 'unavailable' ? 0.75 : 1 },
          ]}>
          {busy === 'google' ? (
            <ActivityIndicator color={theme.text} />
          ) : (
            <>
              <GoogleGlyph />
              <Text maxFontSizeMultiplier={1.3} style={[styles.googleText, { color: theme.text }]}>
                {t('auth.social.google')}
              </Text>
            </>
          )}
        </Pressable>
      ) : null}
      {info ? <Notice tone="info">{info}</Notice> : null}
      <ErrorText>{error}</ErrorText>
      <Divider label={t('auth.social.or')} />
    </View>
  );
}

const styles = StyleSheet.create({
  apple: { width: '100%', height: 56 },
  google: {
    height: 56,
    borderRadius: radius.pill,
    borderWidth: 1.5,
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: space.sm,
  },
  googleText: { fontFamily: fonts.bold, fontSize: 16 },
});
