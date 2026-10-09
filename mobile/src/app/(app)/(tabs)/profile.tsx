import * as Application from 'expo-application';
import * as Haptics from 'expo-haptics';
import { router } from 'expo-router';
import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { StyleSheet, View } from 'react-native';

import { BadgeCheck, Bike, Languages, LifeBuoy, LogOut, MapPin, Smartphone } from '@/components/icons';
import { Button, Card, Chip, ErrorText, IconTile, ListRow, Screen, StatusPill, Txt } from '@/components/ui';
import { apiErrorMessage, SUPPORTED_LOCALES, type Locale } from '@/i18n';
import { api } from '@/lib/api';
import { config } from '@/lib/config';
import { useAuth } from '@/providers/AuthProvider';
import { type AppMode, useMode } from '@/providers/ModeProvider';
import { fonts, space, useTheme } from '@/theme';

const LABELS: Record<Locale, string> = { es: 'Español', en: 'English' };

function initials(name: string | undefined, email: string | undefined) {
  const source = name?.trim() || email || '?';
  const parts = source.split(/\s+/).filter(Boolean);
  return ((parts[0]?.[0] ?? '') + (parts[1]?.[0] ?? '')).toUpperCase() || '?';
}

export default function ProfileScreen() {
  const { t, i18n } = useTranslation();
  const theme = useTheme();
  const { user, signOut, refreshUser } = useAuth();
  const { mode, setMode } = useMode();
  const [error, setError] = useState<string>();
  const [signingOut, setSigningOut] = useState(false);

  async function changeLanguage(locale: Locale) {
    setError(undefined);
    await i18n.changeLanguage(locale);
    try {
      await api('/users/me', { method: 'PATCH', body: { locale } });
      await refreshUser();
    } catch (e) {
      setError(apiErrorMessage(e));
    }
  }

  function switchMode(next: AppMode) {
    if (next === mode) return;
    void Haptics.selectionAsync().catch(() => undefined);
    void setMode(next);
  }

  return (
    <Screen tabBar>
      <View style={styles.header}>
        <View style={[styles.avatar, { backgroundColor: theme.primary }]}>
          <Txt style={{ fontFamily: fonts.extrabold, fontSize: 26, color: theme.onPrimary }}>{initials(user?.full_name, user?.email)}</Txt>
        </View>
        <View style={{ flex: 1, gap: 2 }}>
          <Txt variant="heading" numberOfLines={1} accessibilityRole="header">
            {user?.full_name || t('tabs.profile')}
          </Txt>
          <Txt color="muted" numberOfLines={1}>
            {user?.email}
          </Txt>
          {user?.is_verified ? (
            <View style={{ marginTop: 4 }}>
              <StatusPill label={t('profile.verified')} tone="primary" />
            </View>
          ) : null}
        </View>
      </View>

      <Txt variant="overline" color="muted" style={{ marginTop: space.xl, marginBottom: space.xs }}>
        {t('profile.mode')}
      </Txt>
      <View style={{ flexDirection: 'row', gap: space.sm }}>
        {(['passenger', 'driver'] as const).map((option) => (
          <Card
            key={option}
            style={styles.modeCard}
            selected={mode === option}
            accessibilityLabel={t(`mode.${option}.title`)}
            accessibilityHint={t('profile.modeHint')}
            onPress={() => switchMode(option)}>
            <IconTile icon={option === 'passenger' ? MapPin : Bike} tone={option === 'passenger' ? 'primary' : 'accent'} size={44} />
            <Txt variant="bodyStrong">{t(`mode.${option}.title`)}</Txt>
            {mode === option ? <StatusPill label={t('profile.current')} tone="primary" /> : null}
          </Card>
        ))}
      </View>

      <Txt variant="overline" color="muted" style={{ marginTop: space.xl, marginBottom: space.xs }}>
        {t('profile.language')}
      </Txt>
      <Card>
        <View style={{ flexDirection: 'row', alignItems: 'center', gap: space.sm }}>
          <IconTile icon={Languages} size={40} />
          <View style={{ flexDirection: 'row', gap: space.xs, flex: 1, flexWrap: 'wrap' }}>
            {SUPPORTED_LOCALES.map((locale) => (
              <Chip key={locale} label={LABELS[locale]} selected={i18n.language === locale} onPress={() => changeLanguage(locale)} />
            ))}
          </View>
        </View>
      </Card>
      <ErrorText>{error}</ErrorText>

      <Txt variant="overline" color="muted" style={{ marginTop: space.xl, marginBottom: space.xs }}>
        {t('profile.support')}
      </Txt>
      <Card style={{ paddingVertical: space.xxs }}>
        <ListRow
          icon={LifeBuoy}
          title={t('profile.help')}
          subtitle={t('profile.helpHint')}
          onPress={() => router.push('/reports')}
        />
      </Card>

      <Txt variant="overline" color="muted" style={{ marginTop: space.xl, marginBottom: space.xs }}>
        {t('profile.about')}
      </Txt>
      <Card style={{ paddingVertical: space.xxs }}>
        <ListRow icon={Smartphone} iconTone="neutral" title={t('profile.version')} subtitle={Application.nativeApplicationVersion ?? 'dev'} divider />
        <ListRow icon={BadgeCheck} iconTone="neutral" title={t('profile.environment')} subtitle={config.appEnv} />
      </Card>

      <Button
        title={t('auth.logout')}
        variant="danger"
        size="md"
        icon={LogOut}
        loading={signingOut}
        style={{ marginTop: space.xl }}
        onPress={async () => {
          setSigningOut(true);
          await signOut();
        }}
      />
    </Screen>
  );
}

const styles = StyleSheet.create({
  header: { flexDirection: 'row', alignItems: 'center', gap: space.md, paddingTop: space.xl },
  avatar: { width: 72, height: 72, borderRadius: 36, alignItems: 'center', justifyContent: 'center' },
  modeCard: { flex: 1, gap: space.sm, padding: space.md },
});
