import * as Application from 'expo-application';
import * as Haptics from 'expo-haptics';
import { router, useFocusEffect } from 'expo-router';
import { setStatusBarStyle } from 'expo-status-bar';
import { useCallback, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { RefreshControl, ScrollView, StyleSheet, View } from 'react-native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';

import {
  Bike,
  Camera,
  LifeBuoy,
  LockKeyhole,
  LogOut,
  Mail,
  MapPin,
  Moon,
  MonitorSmartphone,
  Pencil,
  Sparkles,
  Star,
  Sun,
  UserX,
} from '@/components/icons';
import { showToast } from '@/components/Toast';
import { Button, Card, IconTile, ListRow, Sheet, TAB_BAR_SPACE, Txt, Wordmark } from '@/components/ui';
import { useDriverProfile } from '@/hooks/useDriver';
import { useDriverStats, usePassengerStats } from '@/hooks/useRides';
import { apiErrorMessage, SUPPORTED_LOCALES, type Locale } from '@/i18n';
import { api } from '@/lib/api';
import { config as appConfig } from '@/lib/config';
import { formatKm, missingProfileSteps, PROFILE_STEPS_TOTAL, type ProfileStep, ratingValue } from '@/lib/profile';
import { formatFare } from '@/lib/ride';
import { useStore } from '@/lib/store';
import { useAuth } from '@/providers/AuthProvider';
import { type AppMode, useMode } from '@/providers/ModeProvider';
import { setThemePreference, space, themePreference, type ThemePreference, useTheme } from '@/theme';

import { Meter, Section, Segmented, type Stat, StatStrip } from './components';
import { DriverProfile } from './DriverProfile';
import { PassengerProfile } from './PassengerProfile';
import { HEADER_OVERLAP, ProfileHeader } from './ProfileHeader';

const LANGUAGE_LABELS: Record<Locale, string> = { es: 'Español', en: 'English' };

type Confirm = 'logoutAll' | 'deactivate' | null;

export function ProfileScreen() {
  const { t, i18n } = useTranslation();
  const theme = useTheme();
  const insets = useSafeAreaInsets();
  const { user, signOut, refreshUser } = useAuth();
  const { mode: storedMode, setMode } = useMode();
  const mode: AppMode = storedMode ?? 'passenger';
  const preference = useStore(themePreference);
  const [signingOut, setSigningOut] = useState(false);
  const [confirm, setConfirm] = useState<Confirm>(null);
  const [verifySent, setVerifySent] = useState(false);

  // White status bar text over the green header while this tab is on screen.
  useFocusEffect(
    useCallback(() => {
      setStatusBarStyle('light');
      return () => setStatusBarStyle('auto');
    }, []),
  );

  const driver = useDriverProfile(mode === 'driver');
  const approvedDriver = mode === 'driver' && (driver.data?.status === 'approved' || driver.data?.status === 'suspended');
  const driverStats = useDriverStats(approvedDriver);
  const passengerStats = usePassengerStats(!approvedDriver);

  const stats: Stat[] = approvedDriver
    ? [
        { label: t('profile.stats.trips'), value: String(driverStats.data?.total_rides ?? 0), icon: undefined },
        {
          label: t('profile.stats.rating'),
          value: driverStats.data?.rating != null ? driverStats.data.rating.toFixed(1) : '—',
          icon: Star,
        },
        { label: t('profile.stats.month'), value: formatFare(driverStats.data?.month.earnings ?? 0) },
      ]
    : [
        { label: t('profile.stats.trips'), value: String(passengerStats.data?.rides ?? 0) },
        {
          label: t('profile.stats.rating'),
          value: ratingValue(user?.rating_avg)?.toFixed(1) ?? '—',
          icon: Star,
        },
        { label: t('profile.stats.km'), value: formatKm(passengerStats.data?.distance_m, i18n.language) },
      ];
  const statsLoading = approvedDriver ? driverStats.isPending : passengerStats.isPending;
  const rating = approvedDriver ? ratingValue(driverStats.data?.rating) : ratingValue(user?.rating_avg);

  const [refreshing, setRefreshing] = useState(false);
  const refresh = async () => {
    setRefreshing(true);
    await Promise.allSettled([
      refreshUser(),
      approvedDriver ? driverStats.refetch() : passengerStats.refetch(),
      mode === 'driver' ? driver.refetch() : Promise.resolve(),
    ]);
    setRefreshing(false);
  };

  function switchMode(next: AppMode) {
    if (next === mode) return;
    void Haptics.selectionAsync().catch(() => undefined);
    void setMode(next);
  }

  async function changeLanguage(locale: Locale) {
    if (locale === i18n.language) return;
    await i18n.changeLanguage(locale);
    try {
      await api('/users/me', { method: 'PATCH', body: { locale } });
      await refreshUser();
    } catch (e) {
      showToast(apiErrorMessage(e), 'danger');
    }
  }

  async function resendVerification() {
    try {
      await api('/auth/verify-email/resend', { method: 'POST' });
      setVerifySent(true);
      showToast(t('home.verifySent'), 'success');
    } catch (e) {
      showToast(apiErrorMessage(e), 'danger');
    }
  }

  async function logoutEverywhere() {
    try {
      await api('/auth/logout-all', { method: 'POST' });
    } catch (e) {
      showToast(apiErrorMessage(e), 'danger');
      return;
    }
    await signOut();
  }

  async function deactivate() {
    try {
      await api('/users/me', { method: 'DELETE' });
    } catch (e) {
      showToast(apiErrorMessage(e), 'danger');
      return;
    }
    await signOut();
  }

  const missing = missingProfileSteps(user);

  return (
    <View style={{ flex: 1, backgroundColor: theme.background }}>
      <ScrollView
        contentContainerStyle={{ paddingBottom: TAB_BAR_SPACE + insets.bottom }}
        showsVerticalScrollIndicator={false}
        refreshControl={<RefreshControl refreshing={refreshing} onRefresh={() => void refresh()} tintColor={theme.onHero} />}>
        <ProfileHeader mode={mode} rating={rating} />

        <View style={styles.body}>
          <View style={{ marginTop: -HEADER_OVERLAP }}>
            <StatStrip stats={stats} loading={statsLoading} />
          </View>

          {missing.length ? (
            <CompleteProfile
              missing={missing}
              verifySent={verifySent}
              onVerify={() => void resendVerification()}
            />
          ) : null}

          <Section title={t('profile.mode')}>
            <Segmented
              label={t('profile.mode')}
              value={mode}
              onChange={switchMode}
              options={[
                { value: 'passenger', label: t('mode.passenger.title'), icon: MapPin },
                { value: 'driver', label: t('mode.driver.title'), icon: Bike },
              ]}
            />
          </Section>

          {mode === 'driver' ? (
            <DriverProfile driver={driver.data} loading={driver.isPending} stats={driverStats.data} />
          ) : (
            <PassengerProfile stats={passengerStats.data} loading={passengerStats.isPending} />
          )}

          <Section title={t('profile.account')}>
            <Card style={{ paddingVertical: space.xxs }}>
              <ListRow icon={Pencil} title={t('profile.edit.title')} subtitle={t('profile.edit.hint')} divider onPress={() => router.push('/profile/edit')} />
              <ListRow icon={LockKeyhole} title={t('profile.password.title')} subtitle={t('profile.password.hint')} divider onPress={() => router.push('/profile/password')} />
              <ListRow icon={LifeBuoy} title={t('profile.help')} subtitle={t('profile.helpHint')} onPress={() => router.push('/reports')} />
            </Card>
          </Section>

          <Section title={t('profile.preferences')}>
            <Card style={{ gap: space.lg }}>
              <View style={{ gap: space.xs }}>
                <Txt variant="label" color="muted">
                  {t('profile.language')}
                </Txt>
                <Segmented
                  label={t('profile.language')}
                  value={(SUPPORTED_LOCALES.includes(i18n.language as Locale) ? i18n.language : 'es') as Locale}
                  onChange={(locale) => void changeLanguage(locale)}
                  options={SUPPORTED_LOCALES.map((locale) => ({ value: locale, label: LANGUAGE_LABELS[locale] }))}
                />
              </View>
              <View style={{ gap: space.xs }}>
                <Txt variant="label" color="muted">
                  {t('profile.appearance.title')}
                </Txt>
                <Segmented<ThemePreference>
                  label={t('profile.appearance.title')}
                  value={preference}
                  onChange={(value) => {
                    void Haptics.selectionAsync().catch(() => undefined);
                    setThemePreference(value);
                  }}
                  options={[
                    { value: 'system', label: t('profile.appearance.system') },
                    { value: 'light', label: t('profile.appearance.light'), icon: Sun },
                    { value: 'dark', label: t('profile.appearance.dark'), icon: Moon },
                  ]}
                />
              </View>
            </Card>
          </Section>

          <Section title={t('profile.security')}>
            <Card style={{ paddingVertical: space.xxs }}>
              <ListRow
                icon={MonitorSmartphone}
                iconTone="neutral"
                title={t('profile.logoutAll.title')}
                subtitle={t('profile.logoutAll.hint')}
                divider
                onPress={() => setConfirm('logoutAll')}
              />
              <ListRow
                icon={UserX}
                iconTone="danger"
                title={t('profile.deactivate.title')}
                subtitle={t('profile.deactivate.hint')}
                onPress={() => setConfirm('deactivate')}
              />
            </Card>
          </Section>

          <Button
            title={t('auth.logout')}
            variant="danger"
            icon={LogOut}
            loading={signingOut}
            style={{ marginTop: space.xl }}
            onPress={async () => {
              setSigningOut(true);
              await signOut();
            }}
          />

          <View style={styles.footer} accessible accessibilityLabel={`Kuulis ${t('profile.version')} ${Application.nativeApplicationVersion ?? 'dev'}`}>
            <Wordmark size={22} />
            <Txt variant="caption" color="muted">
              {t('profile.footer', { version: Application.nativeApplicationVersion ?? 'dev', env: appConfig.appEnv })}
            </Txt>
          </View>
        </View>
      </ScrollView>

      <Sheet
        visible={confirm !== null}
        title={confirm === 'deactivate' ? t('profile.deactivate.confirmTitle') : t('profile.logoutAll.confirmTitle')}
        subtitle={confirm === 'deactivate' ? t('profile.deactivate.confirmBody') : t('profile.logoutAll.confirmBody')}
        onClose={() => setConfirm(null)}
        options={
          confirm === 'deactivate'
            ? [{ label: t('profile.deactivate.confirm'), icon: UserX, destructive: true, onPress: () => void deactivate() }]
            : [{ label: t('profile.logoutAll.confirm'), icon: LogOut, destructive: true, onPress: () => void logoutEverywhere() }]
        }
      />
    </View>
  );
}

const STEP_ICONS = { photo: Camera, name: Pencil, email: Mail } as const;

/** "Completa tu perfil": what is missing (photo, full name, verified email) with a shortcut for each. */
function CompleteProfile({
  missing,
  verifySent,
  onVerify,
}: {
  missing: ProfileStep[];
  verifySent: boolean;
  onVerify: () => void;
}) {
  const { t } = useTranslation();
  const done = PROFILE_STEPS_TOTAL - missing.length;
  const action = (step: ProfileStep) => {
    if (step === 'email') onVerify();
    else router.push('/profile/edit');
  };
  return (
    <Card tone="accent" style={{ marginTop: space.lg, gap: space.sm }}>
      <View style={styles.row}>
        <IconTile icon={Sparkles} tone="accent" />
        <View style={{ flex: 1, gap: 2 }}>
          <Txt variant="bodyStrong">{t('profile.complete.title')}</Txt>
          <Txt variant="caption" color="onAccentSoft">
            {t('profile.complete.progress', { done, total: PROFILE_STEPS_TOTAL })}
          </Txt>
        </View>
      </View>
      <Meter value={done} total={PROFILE_STEPS_TOTAL} />
      <View>
        {missing.map((step) => (
          <ListRow
            key={step}
            icon={STEP_ICONS[step]}
            iconTone="accent"
            title={t(`profile.complete.${step}`)}
            subtitle={step === 'email' && verifySent ? t('home.verifySent') : t(`profile.complete.${step}Hint`)}
            onPress={step === 'email' && verifySent ? undefined : () => action(step)}
          />
        ))}
      </View>
    </Card>
  );
}

const styles = StyleSheet.create({
  body: { paddingHorizontal: space.lg },
  row: { flexDirection: 'row', alignItems: 'center', gap: space.md },
  footer: { alignItems: 'center', gap: 4, marginTop: space.xxl },
});
