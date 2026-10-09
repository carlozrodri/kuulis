import { router, useLocalSearchParams } from 'expo-router';
import { useMemo, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { ActivityIndicator, Alert, Linking, Platform, Pressable, StyleSheet, View } from 'react-native';

import { ChevronDown, CircleX, Flag, HandCoins, MapPin, MessageCircle, Navigation, Power } from '@/components/icons';
import { RideMap } from '@/components/map/RideMap';
import { MapSheetLayout } from '@/components/MapSheetLayout';
import { VesLine } from '@/components/Money';
import { showToast } from '@/components/Toast';
import { Button, EmptyState, IconButton, ProgressSteps, StatusPill, Txt } from '@/components/ui';
import { Avatar, PAYMENT_ICONS, RatingBadge, RoundAction } from '@/features/ride/components';
import { CancelSheet } from '@/features/ride/RideSheets';
import { chatUnread } from '@/features/ride/store';
import { useUserLocation } from '@/hooks/useLocation';
import { useActiveRide, useCancelRide, useDriverRideAction, useRide } from '@/hooks/useRides';
import { apiErrorMessage } from '@/i18n';
import { confirmHaptic } from '@/lib/feedback';
import { amountToPay, hasDiscount } from '@/lib/money';
import {
  canDriverCancel,
  decodePolyline,
  estimateEtaSeconds,
  formatDistance,
  formatDuration,
  formatFare,
  googleMapsAppUrl,
  googleMapsNavigationUrl,
  haversineMeters,
  nextDriverAction,
  wazeNavigationUrl,
} from '@/lib/ride';
import { useStore } from '@/lib/store';
import type { LatLng } from '@/lib/types';
import { fonts, radius, space, useTheme } from '@/theme';

const goHome = () => router.dismissTo('/');

async function openNavigation(app: 'google' | 'waze', to: LatLng) {
  if (app === 'waze') {
    await Linking.openURL(wazeNavigationUrl(to)).catch(() => undefined);
    return;
  }
  const native = googleMapsAppUrl(to, Platform.OS);
  const canNative = await Linking.canOpenURL(native).catch(() => false);
  await Linking.openURL(canNative ? native : googleMapsNavigationUrl(to)).catch(() =>
    Linking.openURL(googleMapsNavigationUrl(to)).catch(() => undefined),
  );
}

/** Driver's active ride: go to pickup → "Llegué" → "Iniciar viaje" → "Finalizar", with navigation and chat. */
export function DriveScreen() {
  const { t, i18n } = useTranslation();
  const theme = useTheme();
  const params = useLocalSearchParams<{ id?: string }>();
  const active = useActiveRide();
  const rideId = params.id || active.data?.id;
  const { data: ride, isError, error } = useRide(rideId);
  const action = useDriverRideAction();
  const cancel = useCancelRide();
  const [cancelOpen, setCancelOpen] = useState(false);
  const { position } = useUserLocation();
  const unread = useStore(chatUnread)[rideId ?? ''] ?? 0;
  const route = useMemo(() => decodePolyline(ride?.polyline), [ride?.polyline]);

  if (!ride) {
    return (
      <View style={[styles.center, { backgroundColor: theme.background }]}>
        {isError || (!rideId && !active.isPending) ? (
          <>
            <EmptyState icon={CircleX} title={t('ride.notFound')} body={isError ? apiErrorMessage(error) : undefined} />
            <Button title={t('common.back')} variant="secondary" onPress={goHome} />
          </>
        ) : (
          <ActivityIndicator color={theme.primary} size="large" />
        )}
      </View>
    );
  }

  const next = nextDriverAction(ride.status);
  const toPickup = ride.status === 'driver_assigned' || ride.status === 'driver_arrived';
  const target = toPickup ? ride.pickup : ride.dropoff;
  const me = position ? { lat: position.lat, lng: position.lng } : ride.driver_location;
  const distance = me ? haversineMeters(me, target) : null;
  const PaymentIcon = PAYMENT_ICONS[ride.payment_method];
  const ended = !next;
  const collect = formatFare(amountToPay(ride));
  const credit = hasDiscount(ride) ? formatFare(ride.discount) : null;

  const run = () => {
    if (!next) return;
    const go = () =>
      action.mutate(
        { id: ride.id, action: next },
        {
          onSuccess: (updated) => {
            confirmHaptic();
            if (next === 'complete' && hasDiscount(updated)) {
              showToast(t('drive.promo.creditedToast', { discount: formatFare(updated.discount) }), 'success');
            }
          },
          onError: (e) => showToast(apiErrorMessage(e), 'danger'),
        },
      );
    if (next === 'complete') {
      Alert.alert(t('drive.completeConfirmTitle'), t(credit ? 'drive.completeConfirmBodyPromo' : 'drive.completeConfirmBody', {
          fare: collect,
          method: t(`payment.${ride.payment_method}`),
          discount: credit,
        }), [
        { text: t('common.back'), style: 'cancel' },
        { text: t('drive.action.complete'), onPress: go },
      ]);
    } else go();
  };

  const title =
    ride.status === 'driver_assigned'
      ? t('drive.stage.toPickup', { name: ride.passenger.first_name })
      : ride.status === 'driver_arrived'
        ? t('drive.stage.waiting', { name: ride.passenger.first_name })
        : ride.status === 'in_progress'
          ? t('drive.stage.toDropoff', { name: ride.passenger.first_name })
          : t(`ride.status.${ride.status}`);

  return (
    <MapSheetLayout
      tabBar={false}
      maxSheetRatio={0.6}
      map={(insets) => (
        <RideMap
          insets={insets}
          pickup={ride.status === 'in_progress' ? null : ride.pickup}
          dropoff={ride.dropoff}
          route={ride.status === 'in_progress' ? route : undefined}
          showUser
          fitKey={`${ride.status}-${route.length}`}
        />
      )}
      topBar={
        <View style={styles.topBar}>
          <IconButton icon={ChevronDown} label={t('ride.minimize')} onPress={() => (router.canGoBack() ? router.back() : goHome())} />
          <StatusPill label={t(`ride.status.${ride.status}`)} tone={ride.status === 'driver_arrived' ? 'accent' : 'primary'} dot />
        </View>
      }
      footer={
        ended ? (
          <Button title={t('ride.backHome')} onPress={goHome} />
        ) : (
          <Button
            title={t(`drive.action.${next}`)}
            size="lg"
            icon={next === 'arrive' ? MapPin : next === 'start' ? Power : Flag}
            variant={next === 'complete' ? 'accent' : 'primary'}
            loading={action.isPending}
            onPress={run}
          />
        )
      }>
      <ProgressSteps total={3} current={ride.status === 'driver_assigned' ? 1 : ride.status === 'driver_arrived' ? 2 : 3} />
      <View style={{ gap: 2 }}>
        <Txt variant="heading" accessibilityRole="header">
          {title}
        </Txt>
        {!ended ? (
          <Txt variant="bodyStrong" numberOfLines={2}>
            {target.address}
          </Txt>
        ) : null}
        {!ended && distance != null && ride.status !== 'driver_arrived' ? (
          <Txt color="muted">
            {t('drive.distanceEta', {
              distance: formatDistance(distance, i18n.language),
              time: formatDuration(me ? estimateEtaSeconds(me, target) : 0),
            })}
          </Txt>
        ) : null}
      </View>

      {!ended && ride.status !== 'driver_arrived' ? (
        <View style={styles.navRow}>
          <NavButton label="Google Maps" onPress={() => void openNavigation('google', target)} />
          <NavButton label="Waze" onPress={() => void openNavigation('waze', target)} />
        </View>
      ) : null}

      <View style={[styles.passenger, { backgroundColor: theme.background }]}>
        <Avatar name={ride.passenger.first_name} size={52} />
        <View style={{ flex: 1, gap: 4 }}>
          <Txt variant="subtitle" numberOfLines={1}>
            {ride.passenger.first_name}
          </Txt>
          <RatingBadge rating={ride.passenger.rating} />
        </View>
        {!ended ? (
          <RoundAction
            icon={MessageCircle}
            label={t('ride.chat')}
            badge={unread}
            onPress={() => router.push({ pathname: '/ride/chat', params: { id: ride.id } })}
          />
        ) : null}
      </View>

      <View style={[styles.collectBox, { backgroundColor: theme.surfaceAlt }]}>
        <View style={styles.collect}>
          {PaymentIcon ? <PaymentIcon size={22} color={theme.scheme === 'dark' ? theme.primary : theme.primaryPressed} /> : null}
          <View style={{ flex: 1 }}>
            <Txt variant="micro" color="muted">
              {t('drive.collect')}
            </Txt>
            <Txt variant="bodyStrong">{t(`payment.${ride.payment_method}`)}</Txt>
          </View>
          <Txt style={{ fontFamily: fonts.extrabold, fontSize: 28, color: theme.text }} tabular>
            {collect}
          </Txt>
        </View>
        <VesLine ves={ride.total_ves} align="right" />
        {credit ? (
          <View style={[styles.credit, { backgroundColor: theme.accentSoft }]}>
            <HandCoins size={18} color={theme.onAccentSoft} strokeWidth={2.2} />
            <Txt variant="label" style={{ color: theme.onAccentSoft, flex: 1 }}>
              {ride.status === 'completed'
                ? t('drive.promo.credited', { discount: credit })
                : t('drive.promo.willCredit', { discount: credit })}
            </Txt>
          </View>
        ) : null}
      </View>

      {canDriverCancel(ride.status) ? (
        <Button title={t('ride.cancel')} variant="danger" size="sm" loading={cancel.isPending} onPress={() => setCancelOpen(true)} />
      ) : null}
      <CancelSheet
        visible={cancelOpen}
        role="driver"
        onClose={() => setCancelOpen(false)}
        onCancel={(reason) =>
          cancel.mutate(
            { id: ride.id, reason },
            {
              onSuccess: () => {
                showToast(t('ride.cancelled'));
                goHome();
              },
              onError: (e) => showToast(apiErrorMessage(e), 'danger'),
            },
          )
        }
      />
    </MapSheetLayout>
  );
}

function NavButton({ label, onPress }: { label: string; onPress: () => void }) {
  const theme = useTheme();
  const { t } = useTranslation();
  return (
    <Pressable
      accessibilityRole="button"
      accessibilityLabel={t('drive.navigateWith', { app: label })}
      onPress={onPress}
      style={({ pressed }) => [styles.navButton, { borderColor: theme.border, backgroundColor: pressed ? theme.surfaceAlt : theme.surface }]}>
      <Navigation size={18} color={theme.primary} strokeWidth={2.4} />
      <Txt variant="bodyStrong">{label}</Txt>
    </Pressable>
  );
}

const styles = StyleSheet.create({
  center: { flex: 1, alignItems: 'center', justifyContent: 'center', padding: space.lg, gap: space.md },
  topBar: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between' },
  navRow: { flexDirection: 'row', gap: space.sm },
  navButton: {
    flex: 1,
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: space.xs,
    height: 52,
    borderRadius: radius.pill,
    borderWidth: 1.5,
  },
  passenger: { flexDirection: 'row', alignItems: 'center', gap: space.md, borderRadius: radius.card, padding: space.md },
  collectBox: { gap: space.xs, borderRadius: radius.tile, padding: space.md },
  collect: { flexDirection: 'row', alignItems: 'center', gap: space.sm },
  credit: { flexDirection: 'row', alignItems: 'center', gap: space.xs, borderRadius: radius.field, paddingHorizontal: space.sm, paddingVertical: space.xs },
});
