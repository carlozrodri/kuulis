import { router, useLocalSearchParams } from 'expo-router';
import { useMemo, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { ActivityIndicator, StyleSheet, View } from 'react-native';

import { ErrorState } from '@/components/ErrorState';
import { Backpack, Banknote, ChevronLeft, CircleEllipsis, LifeBuoy, MessageCircle, Star, UserX } from '@/components/icons';
import { RideMap } from '@/components/map/RideMap';
import { MapSheetLayout } from '@/components/MapSheetLayout';
import { DiscountNote, VesLine } from '@/components/Money';
import { Button, IconButton, type SheetOption, Sheet, StatusPill, Txt } from '@/components/ui';
import { useAppConfig } from '@/hooks/useDriver';
import { useLostItem, useRide } from '@/hooks/useRides';
import { isNotFound } from '@/lib/errorKind';
import { amountToPay, hasDiscount } from '@/lib/money';
import { decodePolyline, formatDistance, formatDuration, formatFare, isActiveStatus, rideRole } from '@/lib/ride';
import { lostItemState, type RideHelpOption, rideHelpOptions } from '@/lib/support';
import type { LostItem, Ride } from '@/lib/types';
import { useAuth } from '@/providers/AuthProvider';
import { useMode } from '@/providers/ModeProvider';
import { space, useTheme } from '@/theme';

import { Avatar, PAYMENT_ICONS, PlaceRows, RatingBadge, RideNote } from './components';
import { RideActions } from './RideActions';
import { STATUS_TONE } from './HistoryScreen';

/**
 * A past ride from the history: route, price, the other person and my rating. Doc 13: "Necesito ayuda con
 * este viaje" opens the guided flows (lost item, different fare, no show, other) and a lost item shows here.
 */
export function RideDetailScreen() {
  const { t, i18n } = useTranslation();
  const theme = useTheme();
  const { user } = useAuth();
  const { mode } = useMode();
  const { id } = useLocalSearchParams<{ id: string }>();
  const rideQuery = useRide(id);
  const ride = rideQuery.data;
  const route = useMemo(() => decodePolyline(ride?.polyline), [ride?.polyline]);
  const { config } = useAppConfig();
  const [helpOpen, setHelpOpen] = useState(false);
  const lostItem = useLostItem(id, ride?.status === 'completed' && !!ride?.driver);

  if (!ride) {
    return (
      <View style={[styles.center, { backgroundColor: theme.background }]}>
        {rideQuery.isError ? (
          <>
            <ErrorState
              error={rideQuery.error}
              title={isNotFound(rideQuery.error) ? t('ride.notFound') : undefined}
              onRetry={() => rideQuery.refetch()}
              style={{ alignSelf: 'stretch' }}
            />
            <Button title={t('common.back')} variant="ghost" onPress={() => router.back()} />
          </>
        ) : (
          <ActivityIndicator color={theme.primary} size="large" />
        )}
      </View>
    );
  }

  const role = rideRole(ride, user?.id, mode ?? 'passenger');
  const other = role === 'passenger' ? ride.driver : ride.passenger;
  const PaymentIcon = PAYMENT_ICONS[ride.payment_method];
  const date = new Date(ride.requested_at);

  return (
    <MapSheetLayout
      tabBar={false}
      map={(insets) => (
        <RideMap insets={insets} pickup={ride.pickup} dropoff={ride.dropoff} route={route} showUser={false} fitKey={`${ride.id}-${route.length}`} />
      )}
      topBar={
        <View style={{ flexDirection: 'row' }}>
          <IconButton icon={ChevronLeft} label={t('common.back')} onPress={() => router.back()} />
        </View>
      }>
      <View style={{ gap: 4 }}>
        <StatusPill label={t(`ride.status.${ride.status}`)} tone={STATUS_TONE[ride.status] ?? 'neutral'} />
        <Txt variant="heading" accessibilityRole="header">
          {date.toLocaleDateString(i18n.language, { weekday: 'long', day: 'numeric', month: 'long' })}
        </Txt>
        <Txt color="muted">
          {date.toLocaleTimeString(i18n.language, { hour: '2-digit', minute: '2-digit' })} ·{' '}
          {t('quote.meta', { distance: formatDistance(ride.distance_m, i18n.language), time: formatDuration(ride.duration_s) })}
        </Txt>
      </View>

      <PlaceRows pickup={ride.pickup} dropoff={ride.dropoff} />

      <View style={[styles.priceBox, { backgroundColor: theme.background }]}>
        <View style={styles.priceRow}>
          {PaymentIcon ? <PaymentIcon size={20} color={theme.muted} /> : null}
          <Txt variant="bodyStrong" style={{ flex: 1 }}>
            {t(`payment.${ride.payment_method}`)}
          </Txt>
          {hasDiscount(ride) ? (
            <Txt variant="caption" color="muted" tabular style={{ textDecorationLine: 'line-through' }}>
              {formatFare(ride.fare)}
            </Txt>
          ) : null}
          <Txt variant="heading" tabular>
            {formatFare(amountToPay(ride))}
          </Txt>
        </View>
        <VesLine ves={ride.total_ves} align="right" />
        {role === 'driver' && hasDiscount(ride) ? (
          <Txt variant="caption" color="success">
            {ride.status === 'completed'
              ? t('drive.promo.credited', { discount: formatFare(ride.discount) })
              : t('drive.promo.willCredit', { discount: formatFare(ride.discount) })}
          </Txt>
        ) : (
          <DiscountNote item={ride} />
        )}
      </View>

      {other ? (
        <View style={[styles.row, { backgroundColor: theme.background }]}>
          <Avatar name={other.first_name} photoUrl={role === 'passenger' ? ride.driver?.photo_url : null} size={44} />
          <View style={{ flex: 1, gap: 2 }}>
            <Txt variant="bodyStrong">{other.first_name}</Txt>
            <Txt variant="caption" color="muted">
              {role === 'passenger' ? t('chat.yourDriver') : t('chat.yourPassenger')}
            </Txt>
          </View>
          <RatingBadge rating={other.rating} />
        </View>
      ) : null}

      {ride.my_rating ? (
        <View style={styles.myRating} accessibilityLabel={t('rating.yourRating', { count: ride.my_rating.stars })}>
          <Txt variant="label" color="muted">
            {t('rating.yourRatingLabel')}
          </Txt>
          <View style={{ flexDirection: 'row', gap: 2 }}>
            {[1, 2, 3, 4, 5].map((n) => (
              <Star key={n} size={18} color={theme.accent} fill={n <= ride.my_rating!.stars ? theme.accent : 'transparent'} />
            ))}
          </View>
        </View>
      ) : null}

      {ride.rider_name || ride.note ? <RideNote ride={ride} /> : null}

      {!isActiveStatus(ride.status) ? <RideActions ride={ride} role={role} /> : null}

      {isActiveStatus(ride.status) ? (
        <Button
          title={t('home.activeRide')}
          onPress={() => router.replace({ pathname: role === 'driver' ? '/drive' : '/ride', params: { id: ride.id } })}
        />
      ) : null}
      {lostItem.data ? <LostItemCard item={lostItem.data} ride={ride} role={role} /> : null}
      {ride.driver ? (
        // Only rides that had a driver can be reported (409 ride_without_driver otherwise).
        <Button
          title={t('rideHelp.button')}
          variant="secondary"
          icon={LifeBuoy}
          onPress={() => setHelpOpen(true)}
        />
      ) : null}
      <Sheet
        visible={helpOpen}
        title={t('rideHelp.title')}
        subtitle={t('rideHelp.subtitle')}
        options={rideHelpOptions(ride, role, config).map((option) => helpOption(option, ride, role, t, !!lostItem.data))}
        onClose={() => setHelpOpen(false)}
      />
      {ride.cancel_reason_code || ride.cancel_reason ? (
        <Txt variant="caption" color="muted">
          {t('cancel.reasonLabel', {
            // Doc 15: the code says why; older rides kept a code (or free text) in `cancel_reason`.
            reason: ride.cancel_reason_code
              ? [t(`cancel.reason.${ride.cancel_reason_code}`, { defaultValue: ride.cancel_reason_code }), ride.cancel_reason]
                  .filter(Boolean)
                  .join(': ')
              : t(`cancel.reason.${ride.cancel_reason}`, { defaultValue: ride.cancel_reason }),
          })}
        </Txt>
      ) : null}
      <View style={{ height: space.xs }} />
    </MapSheetLayout>
  );
}

const HELP_ICONS = { lost_item: Backpack, fare: Banknote, no_show: UserX, other: CircleEllipsis } as const;

function helpOption(
  option: RideHelpOption,
  ride: Ride,
  role: 'passenger' | 'driver',
  t: (key: string, options?: Record<string, unknown>) => string,
  lostItemAsked: boolean,
): SheetOption {
  const report = (category?: 'fare' | 'no_show') =>
    router.push({ pathname: '/report', params: category ? { ride_id: ride.id, category, direct: '1' } : { ride_id: ride.id } });
  switch (option) {
    case 'lost_item':
      return {
        label: t('rideHelp.lostItem'),
        hint: lostItemAsked ? t('rideHelp.lostItemAsked') : t('rideHelp.lostItemHint'),
        icon: HELP_ICONS.lost_item,
        onPress: () => router.push({ pathname: '/ride/lost-item', params: { id: ride.id } }),
      };
    case 'fare':
      return {
        label: t('rideHelp.fare'),
        hint: t('rideHelp.fareHint', { fare: formatFare(amountToPay(ride)) }),
        icon: HELP_ICONS.fare,
        onPress: () => report('fare'),
      };
    case 'no_show':
      return {
        label: role === 'passenger' ? t('rideHelp.noShowDriver') : t('rideHelp.noShowPassenger'),
        hint: t('rideHelp.noShowHint'),
        icon: HELP_ICONS.no_show,
        onPress: () => report('no_show'),
      };
    default:
      return { label: t('rideHelp.other'), hint: t('rideHelp.otherHint'), icon: HELP_ICONS.other, onPress: () => report() };
  }
}

/** The lost item asked about this ride: its state, the chat while it is open, the driver's answer. */
function LostItemCard({ item, ride, role }: { item: LostItem; ride: Ride; role: 'passenger' | 'driver' }) {
  const { t } = useTranslation();
  const theme = useTheme();
  const state = lostItemState(item);
  const open = () => router.push({ pathname: '/ride/lost-item', params: { id: ride.id } });
  const name = (role === 'passenger' ? ride.driver?.first_name : ride.passenger?.first_name) ?? '';
  return (
    <View style={[styles.lostItem, { backgroundColor: theme.background }]}>
      <View style={styles.priceRow}>
        <Backpack size={20} color={theme.primary} strokeWidth={2.2} />
        <Txt variant="bodyStrong" style={{ flex: 1 }}>
          {role === 'driver' && state === 'waiting' ? t('lostItem.driver.title') : t(`lostItem.state.${state}.title`, { name })}
        </Txt>
      </View>
      <Txt variant="caption" color="muted" numberOfLines={2}>
        {item.description}
      </Txt>
      {state === 'chat' ? (
        <Button
          title={t('lostItem.openChatShort')}
          size="sm"
          icon={MessageCircle}
          style={{ alignSelf: 'flex-start' }}
          onPress={() => router.push({ pathname: '/ride/chat', params: { id: ride.id } })}
        />
      ) : (
        <Button
          title={role === 'driver' && state === 'waiting' ? t('lostItem.driver.answer') : t('lostItem.view')}
          size="sm"
          variant={role === 'driver' && state === 'waiting' ? 'primary' : 'secondary'}
          style={{ alignSelf: 'flex-start' }}
          onPress={open}
        />
      )}
    </View>
  );
}

const styles = StyleSheet.create({
  lostItem: { gap: space.xs, borderRadius: 16, padding: space.md },
  center: { flex: 1, alignItems: 'center', justifyContent: 'center', padding: space.lg, gap: space.md },
  row: { flexDirection: 'row', alignItems: 'center', gap: space.sm, borderRadius: 16, padding: space.md },
  priceBox: { gap: 4, borderRadius: 16, padding: space.md },
  priceRow: { flexDirection: 'row', alignItems: 'center', gap: space.sm },
  myRating: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between' },
});
