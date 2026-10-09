import { router, useLocalSearchParams } from 'expo-router';
import { useMemo } from 'react';
import { useTranslation } from 'react-i18next';
import { ActivityIndicator, StyleSheet, View } from 'react-native';

import { ChevronLeft, Star } from '@/components/icons';
import { RideMap } from '@/components/map/RideMap';
import { MapSheetLayout } from '@/components/MapSheetLayout';
import { Button, IconButton, StatusPill, Txt } from '@/components/ui';
import { useRide } from '@/hooks/useRides';
import { decodePolyline, formatDistance, formatDuration, formatFare, isActiveStatus, rideRole } from '@/lib/ride';
import { useAuth } from '@/providers/AuthProvider';
import { useMode } from '@/providers/ModeProvider';
import { space, useTheme } from '@/theme';

import { Avatar, PAYMENT_ICONS, PlaceRows, RatingBadge } from './components';
import { STATUS_TONE } from './HistoryScreen';

/** A past ride from the history: route, price, the other person and my rating. */
export function RideDetailScreen() {
  const { t, i18n } = useTranslation();
  const theme = useTheme();
  const { user } = useAuth();
  const { mode } = useMode();
  const { id } = useLocalSearchParams<{ id: string }>();
  const { data: ride } = useRide(id);
  const route = useMemo(() => decodePolyline(ride?.polyline), [ride?.polyline]);

  if (!ride) {
    return (
      <View style={[styles.center, { backgroundColor: theme.background }]}>
        <ActivityIndicator color={theme.primary} size="large" />
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

      <View style={[styles.row, { backgroundColor: theme.background }]}>
        {PaymentIcon ? <PaymentIcon size={20} color={theme.muted} /> : null}
        <Txt variant="bodyStrong" style={{ flex: 1 }}>
          {t(`payment.${ride.payment_method}`)}
        </Txt>
        <Txt variant="heading" tabular>
          {formatFare(ride.fare)}
        </Txt>
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

      {isActiveStatus(ride.status) ? (
        <Button
          title={t('home.activeRide')}
          onPress={() => router.replace({ pathname: role === 'driver' ? '/drive' : '/ride', params: { id: ride.id } })}
        />
      ) : null}
      {ride.cancel_reason ? (
        <Txt variant="caption" color="muted">
          {t('cancel.reasonLabel', {
            reason: t(`cancel.reason.${ride.cancel_reason}`, { defaultValue: ride.cancel_reason }),
          })}
        </Txt>
      ) : null}
      <View style={{ height: space.xs }} />
    </MapSheetLayout>
  );
}

const styles = StyleSheet.create({
  center: { flex: 1, alignItems: 'center', justifyContent: 'center' },
  row: { flexDirection: 'row', alignItems: 'center', gap: space.sm, borderRadius: 16, padding: space.md },
  myRating: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between' },
});
