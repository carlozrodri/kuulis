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
  LogOut,
  Mail,
  MapPin,
  Pencil,
  Sparkles,
  Star,
  Settings,
} from '@/components/icons';
import { showToast } from '@/components/Toast';
import { Button, Card, IconTile, ListRow, TAB_BAR_SPACE, Txt, Wordmark } from '@/components/ui';
import { useDriverProfile } from '@/hooks/useDriver';
import { useDriverStats, usePassengerStats } from '@/hooks/useRides';
import { apiErrorMessage } from '@/i18n';
import { api } from '@/lib/api';
import { config as appConfig } from '@/lib/config';
import { formatKm, missingProfileSteps, PROFILE_STEPS_TOTAL, type ProfileStep, ratingValue } from '@/lib/profile';
import { formatFare } from '@/lib/ride';
import { useAuth } from '@/providers/AuthProvider';
import { type AppMode, useMode } from '@/providers/ModeProvider';
import { space, useTheme } from '@/theme';

import { Meter, Section, Segmented, type Stat, StatStrip } from './components';
import { DriverProfile } from './DriverProfile';
import { PassengerProfile } from './PassengerProfile';
import { HEADER_OVERLAP, ProfileHeader } from './ProfileHeader';

export function ProfileScreen() {
  const { t, i18n } = useTranslation();
  const theme = useTheme();
  const insets = useSafeAreaInsets();
  const { user, signOut, refreshUser } = useAuth();
  const { mode: storedMode, setMode } = useMode();
  const mode: AppMode = storedMode ?? 'passenger';
  const [signingOut, setSigningOut] = useState(false);
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


  async function resendVerification() {
    try {
      await api('/auth/verify-email/resend', { method: 'POST' });
      setVerifySent(true);
      showToast(t('home.verifySent'), 'success');
    } catch (e) {
      showToast(apiErrorMessage(e), 'danger');
    }
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

          <Card style={{ paddingVertical: space.xxs, marginTop: space.xl }}>
            <ListRow icon={Settings} title={t('profile.menu.settings')} subtitle={t('profile.menu.settingsHint')} onPress={() => router.push('/profile/settings')} />
          </Card>

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
