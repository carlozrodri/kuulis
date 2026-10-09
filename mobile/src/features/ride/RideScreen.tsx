import { useQueryClient } from '@tanstack/react-query';
import { router, useLocalSearchParams } from 'expo-router';
import { useMemo, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { ActivityIndicator, StyleSheet, View } from 'react-native';

import { ChevronDown, CircleX, MessageCircle, SearchX, Share2, ShieldCheck } from '@/components/icons';
import { RideMap } from '@/components/map/RideMap';
import { type MapInsets, MapSheetLayout } from '@/components/MapSheetLayout';
import { showToast } from '@/components/Toast';
import { Button, EmptyState, IconButton, ProgressSteps, StatusPill, Txt } from '@/components/ui';
import { applyRide, requestAgain, useActiveRide, useCancelRide, useRide } from '@/hooks/useRides';
import { apiErrorMessage } from '@/i18n';
import {
  canPassengerCancel,
  decodePolyline,
  estimateEtaSeconds,
  formatArrival,
  formatClock,
  formatDuration,
  formatFare,
  secondsSince,
} from '@/lib/ride';
import { useStore } from '@/lib/store';
import type { Ride } from '@/lib/types';
import { radius, space, useTheme } from '@/theme';

import { Avatar, PAYMENT_ICONS, PlaceRows, PlateBadge, PulsingRings, RatingBadge, RoundAction } from './components';
import { CancelSheet, SafetySheet, shareRide, useNow } from './RideSheets';
import { chatUnread, routedRides } from './store';

const goHome = () => router.dismissTo('/');

/** Passenger live ride: searching → driver assigned → arrived → in progress, plus the end states. */
export function RideScreen() {
  const { t } = useTranslation();
  const theme = useTheme();
  const params = useLocalSearchParams<{ id?: string }>();
  const active = useActiveRide();
  const rideId = params.id || active.data?.id;
  const rideQuery = useRide(rideId);
  const ride = rideQuery.data;

  const route = useMemo(() => decodePolyline(ride?.polyline), [ride?.polyline]);

  if (!ride) {
    return (
      <View style={[styles.center, { backgroundColor: theme.background }]}>
        {rideQuery.isError || (!rideId && !active.isPending) ? (
          <>
            <EmptyState icon={CircleX} title={t('ride.notFound')} body={rideQuery.isError ? apiErrorMessage(rideQuery.error) : undefined} />
            <Button title={t('common.back')} variant="secondary" onPress={goHome} />
          </>
        ) : (
          <ActivityIndicator color={theme.primary} size="large" />
        )}
      </View>
    );
  }

  const showRoute = ride.status === 'searching' || ride.status === 'in_progress' || ride.status === 'completed';
  const driverPoint = ride.status === 'searching' ? null : ride.driver_location;

  return (
    <MapSheetLayout
      tabBar={false}
      maxSheetRatio={0.66}
      map={(insets) => (
        <RideMap
          insets={insets}
          pickup={ride.status === 'in_progress' ? null : ride.pickup}
          dropoff={ride.dropoff}
          driver={driverPoint}
          route={showRoute ? route : undefined}
          showUser
          fitKey={`${ride.status}-${!!driverPoint}-${route.length}`}>
          {ride.status === 'searching' ? <SearchingOverlay insets={insets} /> : null}
        </RideMap>
      )}
      topBar={
        <View style={{ flexDirection: 'row' }}>
          <IconButton icon={ChevronDown} label={t('ride.minimize')} onPress={() => (router.canGoBack() ? router.back() : goHome())} />
        </View>
      }>
      <RideSheet ride={ride} />
    </MapSheetLayout>
  );
}

function SearchingOverlay({ insets }: { insets: MapInsets }) {
  return (
    <View pointerEvents="none" style={[StyleSheet.absoluteFill, { top: insets.top, bottom: insets.bottom, alignItems: 'center', justifyContent: 'center' }]}>
      <PulsingRings size={240} />
    </View>
  );
}

function RideSheet({ ride }: { ride: Ride }) {
  switch (ride.status) {
    case 'searching':
      return <SearchingSheet ride={ride} />;
    case 'driver_assigned':
    case 'driver_arrived':
    case 'in_progress':
      return <OnTheWaySheet ride={ride} />;
    default:
      return <EndedSheet ride={ride} />;
  }
}

function useCancelFlow(ride: Ride) {
  const { t } = useTranslation();
  const cancel = useCancelRide();
  const [open, setOpen] = useState(false);
  const sheet = (
    <CancelSheet
      visible={open}
      role="passenger"
      onClose={() => setOpen(false)}
      onCancel={(reason) =>
        cancel.mutate(
          { id: ride.id, reason },
          {
            onSuccess: () => {
              showToast(t('ride.cancelled'));
              goHome();
            },
            onError: (error) => showToast(apiErrorMessage(error), 'danger'),
          },
        )
      }
    />
  );
  return { open: () => setOpen(true), sheet, pending: cancel.isPending };
}

function FareRow({ ride }: { ride: Ride }) {
  const { t } = useTranslation();
  const theme = useTheme();
  const PaymentIcon = PAYMENT_ICONS[ride.payment_method];
  return (
    <View style={[styles.fareRow, { backgroundColor: theme.background }]}>
      {PaymentIcon ? <PaymentIcon size={20} color={theme.muted} strokeWidth={2} /> : null}
      <Txt variant="bodyStrong" style={{ flex: 1 }}>
        {t(`payment.${ride.payment_method}`)}
      </Txt>
      <Txt variant="subtitle" tabular>
        {formatFare(ride.fare)}
      </Txt>
    </View>
  );
}

function SearchingSheet({ ride }: { ride: Ride }) {
  const { t } = useTranslation();
  const now = useNow(1000);
  const cancel = useCancelFlow(ride);
  return (
    <>
      <View style={{ gap: 4 }}>
        <View style={styles.titleRow}>
          <Txt variant="heading" accessibilityRole="header" style={{ flex: 1 }}>
            {t('ride.searching.title')}
          </Txt>
          <StatusPill label={formatClock(secondsSince(ride.requested_at, now))} tone="primary" dot />
        </View>
        <Txt color="muted">{t('ride.searching.body')}</Txt>
      </View>
      <ProgressSteps total={4} current={1} />
      <PlaceRows pickup={ride.pickup} dropoff={ride.dropoff} compact />
      <FareRow ride={ride} />
      <Button title={t('ride.cancel')} variant="danger" size="sm" loading={cancel.pending} onPress={cancel.open} />
      {cancel.sheet}
    </>
  );
}

function OnTheWaySheet({ ride }: { ride: Ride }) {
  const { t, i18n } = useTranslation();
  const theme = useTheme();
  const now = useNow(15_000);
  const unread = useStore(chatUnread)[ride.id] ?? 0;
  const cancel = useCancelFlow(ride);
  const [safety, setSafety] = useState(false);
  const driver = ride.driver;
  const vehicle = driver?.vehicle;
  const name = driver?.first_name ?? t('ride.yourDriver');

  let title: string;
  let subtitle: string;
  if (ride.status === 'driver_assigned') {
    title = t('ride.assigned.title', { name });
    const eta = ride.driver_location ? estimateEtaSeconds(ride.driver_location, ride.pickup) : null;
    subtitle = eta != null ? t('ride.assigned.eta', { time: formatDuration(eta) }) : t('ride.assigned.body');
  } else if (ride.status === 'driver_arrived') {
    title = t('ride.arrived.title', { name });
    subtitle = t('ride.arrived.body');
  } else {
    title = t('ride.inProgress.title');
    const left = ride.driver_location
      ? estimateEtaSeconds(ride.driver_location, ride.dropoff)
      : Math.max(60, ride.duration_s - secondsSince(ride.started_at, now));
    subtitle = t('ride.inProgress.eta', { time: formatArrival(left, new Date(now), i18n.language) });
  }

  return (
    <>
      <View style={{ gap: 4 }}>
        {ride.status === 'driver_arrived' ? <StatusPill label={t('ride.status.driver_arrived')} tone="accent" dot /> : null}
        <Txt variant="heading" accessibilityRole="header">
          {title}
        </Txt>
        <Txt color="muted">{subtitle}</Txt>
      </View>
      <ProgressSteps total={4} current={ride.status === 'driver_assigned' ? 2 : ride.status === 'driver_arrived' ? 3 : 4} />

      <View style={[styles.driverCard, { backgroundColor: theme.background }]}>
        <Avatar name={driver?.first_name} photoUrl={driver?.photo_url} size={60} />
        <View style={{ flex: 1, gap: 4 }}>
          <View style={styles.titleRow}>
            <Txt variant="subtitle" numberOfLines={1} style={{ flexShrink: 1 }}>
              {name}
            </Txt>
            <RatingBadge rating={driver?.rating} />
          </View>
          {vehicle ? (
            <Txt variant="caption" color="muted" numberOfLines={1}>
              {[vehicle.brand, vehicle.model, vehicle.color].filter(Boolean).join(' · ')}
            </Txt>
          ) : null}
          <PlateBadge plate={vehicle?.plate} />
        </View>
      </View>

      <View style={styles.actions}>
        <RoundAction
          icon={MessageCircle}
          label={t('ride.chat')}
          badge={unread}
          onPress={() => router.push({ pathname: '/ride/chat', params: { id: ride.id } })}
        />
        <RoundAction icon={Share2} label={t('ride.share')} onPress={() => void shareRide(ride, t)} />
        <RoundAction icon={ShieldCheck} label={t('ride.safety')} onPress={() => setSafety(true)} />
      </View>

      <PlaceRows pickup={ride.pickup} dropoff={ride.dropoff} compact />
      <FareRow ride={ride} />
      {canPassengerCancel(ride.status) ? (
        <Button title={t('ride.cancel')} variant="danger" size="sm" loading={cancel.pending} onPress={cancel.open} />
      ) : null}
      {cancel.sheet}
      <SafetySheet visible={safety} ride={ride} onClose={() => setSafety(false)} />
    </>
  );
}

function EndedSheet({ ride }: { ride: Ride }) {
  const { t } = useTranslation();
  const queryClient = useQueryClient();
  const [retrying, setRetrying] = useState(false);

  const retry = async () => {
    setRetrying(true);
    try {
      const next = await requestAgain(ride);
      routedRides.add(next.id);
      applyRide(queryClient, next);
      router.replace({ pathname: '/ride', params: { id: next.id } });
    } catch (error) {
      showToast(apiErrorMessage(error), 'danger');
    } finally {
      setRetrying(false);
    }
  };

  if (ride.status === 'completed') {
    return (
      // The ride navigator opens the (mandatory) rating right after this.
      <EmptyState icon={ShieldCheck} title={t('ride.completed.title')} body={t('ride.completed.body', { fare: formatFare(ride.fare) })} />
    );
  }

  const noDrivers = ride.status === 'no_drivers';
  // Cancelled by the driver or by Kuulis support: the passenger can ask for another moto right away.
  const byDriver = ride.status === 'cancelled_by_driver' || ride.status === 'cancelled_by_admin';
  const byAdmin = ride.status === 'cancelled_by_admin';
  return (
    <>
      <EmptyState
        icon={noDrivers ? SearchX : CircleX}
        title={
          noDrivers
            ? t('ride.noDrivers.title')
            : byAdmin
              ? t('ride.adminCancelled.title')
              : byDriver
                ? t('ride.driverCancelled.title')
                : t('ride.passengerCancelled.title')
        }
        body={noDrivers ? t('ride.noDrivers.body') : byAdmin ? t('ride.adminCancelled.body') : byDriver ? t('ride.driverCancelled.body') : undefined}
      />
      {noDrivers || byDriver ? (
        <Button title={noDrivers ? t('ride.noDrivers.retry') : t('ride.driverCancelled.retry')} loading={retrying} onPress={() => void retry()} />
      ) : null}
      <Button title={t('ride.backHome')} variant="ghost" onPress={goHome} />
    </>
  );
}

const styles = StyleSheet.create({
  center: { flex: 1, alignItems: 'center', justifyContent: 'center', padding: space.lg, gap: space.md },
  titleRow: { flexDirection: 'row', alignItems: 'center', gap: space.xs },
  fareRow: { flexDirection: 'row', alignItems: 'center', gap: space.sm, borderRadius: radius.tile, padding: space.md },
  driverCard: { flexDirection: 'row', alignItems: 'center', gap: space.md, borderRadius: radius.card, padding: space.md },
  actions: { flexDirection: 'row', justifyContent: 'space-around' },
});
