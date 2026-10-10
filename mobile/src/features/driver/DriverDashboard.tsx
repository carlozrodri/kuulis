import { useQueryClient } from '@tanstack/react-query';
import { router } from 'expo-router';
import { useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Animated, StyleSheet, View } from 'react-native';

import { Bike, ChevronRight, Clock, Info, LockKeyhole, Power, Wallet } from '@/components/icons';
import { RideMap } from '@/components/map/RideMap';
import { MapSheetLayout } from '@/components/MapSheetLayout';
import { showToast } from '@/components/Toast';
import { Button, Card, IconTile, Notice, Skeleton, StatusPill, Txt } from '@/components/ui';
import { SuspendedPanel } from '@/features/account/SuspendedPanel';
import { LocationPrompt } from '@/features/ride/LocationPrompt';
import { useWalletFormat } from '@/features/wallet/format';
import { EarningsCard, goToTopUp } from '@/features/wallet/SubscriptionCard';
import { getFreshPosition, requestLocationPermission, useUserLocation } from '@/hooks/useLocation';
import { useActiveRide, useDriverState, useGoOffline, useGoOnline } from '@/hooks/useRides';
import { useSuspension } from '@/hooks/useSuspension';
import { isSubscriptionOverdue, refreshSubscription, useSubscription, useWallet } from '@/hooks/useWallet';
import { apiErrorMessage } from '@/i18n';
import { confirmHaptic, heavyHaptic } from '@/lib/feedback';
import { backgroundLocationActive } from '@/lib/backgroundLocation';
import { formatAmount } from '@/lib/money';
import { formatFare, isActiveStatus } from '@/lib/ride';
import { useStore } from '@/lib/store';
import type { SubscriptionSummary } from '@/lib/types';
import { nextDueAt, pendingTotal, shortfall, subscriptionState } from '@/lib/wallet';
import { elevation, radius, space, useTheme } from '@/theme';

/** Breathing green dot while online. */
function LiveDot({ online }: { online: boolean }) {
  const theme = useTheme();
  const [pulse] = useState(() => new Animated.Value(0));
  useEffect(() => {
    if (!online) return;
    const loop = Animated.loop(Animated.timing(pulse, { toValue: 1, duration: 1600, useNativeDriver: true }));
    loop.start();
    return () => loop.stop();
  }, [online, pulse]);
  const color = online ? theme.success : theme.muted;
  return (
    <View style={styles.liveWrap}>
      {online ? (
        <Animated.View
          style={[
            styles.liveHalo,
            {
              backgroundColor: color,
              opacity: pulse.interpolate({ inputRange: [0, 1], outputRange: [0.45, 0] }),
              transform: [{ scale: pulse.interpolate({ inputRange: [0, 1], outputRange: [1, 2.6] }) }],
            },
          ]}
        />
      ) : null}
      <View style={[styles.liveDot, { backgroundColor: color }]} />
    </View>
  );
}

/**
 * Approved driver's home: this month's earnings and fee on top (Motorizado-Inicio) and a huge CONECTARME /
 * DESCONECTARME over the map. Going online sends the current position (POST /drivers/me/online); the
 * DriverController then streams it every ~4 s over the socket. A driver blocked for an unpaid fee sees why
 * and a Recargar button instead; a suspended account (phase 1E) sees the suspension and Ayuda y reportes.
 */
export function DriverDashboard() {
  const { t } = useTranslation();
  const theme = useTheme();
  const queryClient = useQueryClient();
  const state = useDriverState(true);
  const subscription = useSubscription();
  const wallet = useWallet();
  // Set when going online answered 403 subscription_overdue, until a newer fee summary says otherwise.
  const [overdueAt, setOverdueAt] = useState<number | null>(null);
  const active = useActiveRide();
  const goOnline = useGoOnline();
  const goOffline = useGoOffline();
  const { permission } = useUserLocation();
  const [locating, setLocating] = useState(false);
  const { suspension, handleError: handleSuspended } = useSuspension();
  // Android shares the position from the background while online; elsewhere the app must stay on screen.
  const sharingInBackground = useStore(backgroundLocationActive);

  const online = !!state.data?.online;
  const activeRide = active.data && isActiveStatus(active.data.status) ? active.data : null;
  const summary = subscription.data;
  const fee = subscriptionState(summary);
  const blocked =
    fee === 'blocked' || (overdueAt !== null && (!summary || subscription.dataUpdatedAt <= overdueAt));
  // The API disconnects a suspended driver; while the state catches up the disconnect button stays.
  const suspended = !!suspension && !online;

  const connect = async () => {
    setLocating(true);
    try {
      if (permission !== 'granted' && !(await requestLocationPermission())) {
        showToast(t('location.requiredToConnect'), 'danger');
        return;
      }
      const position = await getFreshPosition();
      if (!position) {
        showToast(t('location.unavailable'), 'danger');
        return;
      }
      await goOnline.mutateAsync({ lat: position.lat, lng: position.lng });
      confirmHaptic();
    } catch (error) {
      if (handleSuspended(error)) {
        // 403 account_suspended: the suspension panel replaces the button.
        heavyHaptic();
        return;
      }
      if (isSubscriptionOverdue(error)) {
        // The blocked banner explains it; refresh the fee so it shows the amount.
        heavyHaptic();
        setOverdueAt(Date.now());
        refreshSubscription(queryClient);
        return;
      }
      showToast(apiErrorMessage(error), 'danger');
    } finally {
      setLocating(false);
    }
  };

  const disconnect = () => {
    heavyHaptic();
    goOffline.mutate(undefined, { onError: (error) => showToast(apiErrorMessage(error), 'danger') });
  };

  return (
    <MapSheetLayout
      map={(insets) => <RideMap insets={insets} followUser showUser />}
      topBar={
        <View style={{ gap: space.sm }} pointerEvents="box-none">
          {summary ? <EarningsCard summary={summary} blocked={blocked} /> : null}
          <View style={styles.topRow} pointerEvents="box-none">
            <View style={[styles.statusChip, { backgroundColor: theme.surface }, elevation(theme)]}>
              <LiveDot online={online} />
              <Txt variant="bodyStrong">{online ? t('drive.home.onlineChip') : t('drive.home.offlineChip')}</Txt>
            </View>
          </View>
        </View>
      }>
      {state.isPending ? (
        <View style={{ gap: space.sm }}>
          <Skeleton height={28} width="60%" />
          <Skeleton height={68} radius={radius.pill} />
        </View>
      ) : (
        <>
          {suspended && suspension ? (
            <SuspendedPanel suspension={suspension} variant="driver" />
          ) : blocked && !online ? (
            <BlockedPanel summary={summary} balance={wallet.data?.balance} />
          ) : (
            <View style={{ gap: 4 }}>
              <Txt variant="heading" accessibilityRole="header">
                {online ? t('drive.home.online') : t('driver.home.offline')}
              </Txt>
              <Txt color="muted">{online ? t('drive.home.onlineBody') : t('driver.home.offlineBody')}</Txt>
            </View>
          )}

          {activeRide ? (
            <Card tone="tint" onPress={() => router.push({ pathname: '/drive', params: { id: activeRide.id } })} style={styles.activeCard}>
              <IconTile icon={Bike} />
              <View style={{ flex: 1 }}>
                <Txt variant="bodyStrong">{t('home.activeRide')}</Txt>
                <Txt variant="caption" color="muted">
                  {t(`ride.status.${activeRide.status}`)}
                </Txt>
              </View>
              <ChevronRight size={20} color={theme.muted} />
            </Card>
          ) : null}

          {fee === 'pending' && summary && !blocked ? <PendingFeeNotice summary={summary} /> : null}

          {permission !== 'granted' && !(blocked && !online) && !suspended ? <LocationPrompt variant="driver" /> : null}

          {online ? (
            <Button
              title={t('drive.home.disconnect')}
              size="lg"
              variant="danger"
              icon={Power}
              loading={goOffline.isPending}
              disabled={!!activeRide}
              onPress={disconnect}
            />
          ) : suspended ? null : blocked ? (
            <Button title={t('wallet.topUpNow')} size="lg" variant="accent" icon={Wallet} onPress={goToTopUp} />
          ) : (
            <Button
              title={t('driver.home.connect')}
              size="lg"
              icon={Power}
              loading={locating || goOnline.isPending}
              onPress={() => void connect()}
            />
          )}

          {online ? (
            sharingInBackground ? null : (
              <Notice tone="info" icon={Info}>
                {t('drive.home.foregroundOnly')}
              </Notice>
            )
          ) : suspended ? null : blocked ? (
            <Button title={t('home.blocked.details')} variant="ghost" size="sm" onPress={() => router.push('/wallet')} />
          ) : !summary || fee === 'not_started' ? (
            <View style={{ alignItems: 'center' }}>
              <StatusPill label={t('driver.home.freeMonths')} tone="accent" />
            </View>
          ) : null}
        </>
      )}
    </MapSheetLayout>
  );
}

/** Replaces "Estás desconectado" when an unpaid fee is past its grace week. */
function BlockedPanel({ summary, balance }: { summary: SubscriptionSummary | undefined; balance: string | undefined }) {
  const { t } = useTranslation();
  const theme = useTheme();
  const owed = pendingTotal(summary?.pending);
  const missing = shortfall(balance, owed);
  return (
    <View accessibilityRole="alert" style={[styles.blocked, { backgroundColor: theme.dangerSoft }]}>
      <View style={styles.blockedTitle}>
        <LockKeyhole size={22} color={theme.danger} strokeWidth={2.2} />
        <Txt variant="heading" style={{ color: theme.danger, flex: 1 }} accessibilityRole="header">
          {t('home.blocked.title')}
        </Txt>
      </View>
      <Txt style={{ color: theme.text }}>
        {owed > 0 ? t('home.blocked.body', { amount: formatFare(owed) }) : t('home.blocked.bodyNoAmount')}
      </Txt>
      {missing > 0 ? (
        <Txt variant="label" style={{ color: theme.text }}>
          {t('wallet.sub.blocked.topUp', { amount: formatAmount(missing) })}
        </Txt>
      ) : null}
    </View>
  );
}

/** "Tienes una cuota de $5.00 pendiente · vence el 8 de noviembre" during the grace week. */
function PendingFeeNotice({ summary }: { summary: SubscriptionSummary }) {
  const { t } = useTranslation();
  const theme = useTheme();
  const format = useWalletFormat();
  const owed = pendingTotal(summary.pending);
  const dueAt = nextDueAt(summary.pending);
  return (
    <View style={[styles.pending, { backgroundColor: theme.warningSoft }]}>
      <Clock size={18} color={theme.warning} strokeWidth={2.2} />
      <Txt variant="label" style={{ color: theme.warning, flex: 1 }}>
        {dueAt
          ? t('home.pendingFee', { amount: formatFare(owed), date: format.dayMonth(dueAt) })
          : t('home.pendingFeeNoDate', { amount: formatFare(owed) })}
      </Txt>
      <Button title={t('wallet.topUp')} variant="accent" size="sm" onPress={goToTopUp} style={{ marginTop: 0 }} />
    </View>
  );
}

const styles = StyleSheet.create({
  blocked: { borderRadius: radius.card, padding: space.md, gap: space.xs },
  blockedTitle: { flexDirection: 'row', alignItems: 'center', gap: space.xs },
  pending: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: space.xs,
    borderRadius: radius.tile,
    paddingLeft: space.sm,
    paddingRight: space.xs,
    paddingVertical: space.xs,
  },
  topRow: { flexDirection: 'row' },
  statusChip: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: space.xs,
    borderRadius: radius.pill,
    paddingHorizontal: space.md,
    paddingVertical: 10,
  },
  liveWrap: { width: 14, height: 14, alignItems: 'center', justifyContent: 'center' },
  liveHalo: { position: 'absolute', width: 14, height: 14, borderRadius: 7 },
  liveDot: { width: 12, height: 12, borderRadius: 6 },
  activeCard: { flexDirection: 'row', alignItems: 'center', gap: space.sm, padding: space.md },
});
