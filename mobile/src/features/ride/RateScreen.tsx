import { router, useFocusEffect } from 'expo-router';
import { useCallback, useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { ActivityIndicator, BackHandler, Pressable, StyleSheet, View } from 'react-native';

import { CircleCheck, Flag, HandCoins } from '@/components/icons';
import { DiscountNote, VesLine } from '@/components/Money';
import { showToast } from '@/components/Toast';
import { Confetti, CountUp, Pop } from '@/components/motion';
import { Button, Card, Chip, EmptyState, Field, Notice, Screen, Txt } from '@/components/ui';
import { usePendingRating, useRateRide } from '@/hooks/useRides';
import { apiErrorMessage } from '@/i18n';
import { ApiError } from '@/lib/api';
import { confirmHaptic, playRideSound, selectionHaptic } from '@/lib/feedback';
import { formatDistance, formatDuration, formatFare, RATING_TAGS, rideRole } from '@/lib/ride';
import { amountToPay, hasDiscount } from '@/lib/money';
import type { Ride } from '@/lib/types';
import { useAuth } from '@/providers/AuthProvider';
import { useMode } from '@/providers/ModeProvider';
import { fonts, space, useTheme } from '@/theme';
import { track } from '@/lib/analytics';

import { Avatar, PAYMENT_ICONS, PlaceRows, StarInput } from './components';

const firstName = (fullName: string | null | undefined) => fullName?.trim().split(/\s+/)[0] ?? '';

/**
 * The end of the ride is a small celebration (docs/product/wow/03): confetti once, "¡Llegaste fino!" for the
 * passenger with the reminder of what to pay, and the earnings counting up for the driver ("100 % tuyo").
 */
function Arrival({ ride, role, firstName: name }: { ride: Ride; role: 'passenger' | 'driver'; firstName: string }) {
  const { t } = useTranslation();
  const theme = useTheme();
  const amount = Number.parseFloat(amountToPay(ride));
  const driverName = ride.driver?.first_name ?? '';
  useEffect(() => {
    void playRideSound(role === 'driver' ? 'earned' : 'completed');
    confirmHaptic();
  }, [role]);
  return (
    <>
      <Pop style={[styles.arrival, { backgroundColor: role === 'driver' ? theme.successSoft : theme.surfaceAlt }]}>
        {role === 'driver' ? (
          <>
            <Txt variant="overline" style={{ color: theme.success }}>
              {t('rating.arrival.driverLabel')}
            </Txt>
            <CountUp value={Number.isFinite(amount) ? amount : 0} duration={900}>
              {(value) => (
                <Txt style={[styles.earned, { color: theme.success }]} tabular accessibilityRole="header">
                  +{formatFare(value)}
                </Txt>
              )}
            </CountUp>
            <Txt variant="bodyStrong" align="center">
              {t('rating.arrival.driverBody')}
            </Txt>
          </>
        ) : (
          <>
            <Txt variant="title" align="center" accessibilityRole="header">
              {name ? t('rating.arrival.passengerTitleName', { name }) : t('rating.arrival.passengerTitle')}
            </Txt>
            <Txt align="center">
              {driverName
                ? t('rating.arrival.passengerPay', { fare: formatFare(amountToPay(ride)), name: driverName })
                : t('rating.arrival.passengerPayNoName', { fare: formatFare(amountToPay(ride)) })}
            </Txt>
          </>
        )}
      </Pop>
    </>
  );
}

/** Mandatory rating after a completed ride. There is no skip: new rides/offers are blocked until rated. */
export function RateScreen() {
  const { t, i18n } = useTranslation();
  const theme = useTheme();
  const { user } = useAuth();
  const { mode } = useMode();
  const pending = usePendingRating();
  const rate = useRateRide();
  const [stars, setStars] = useState(0);
  const [tags, setTags] = useState<string[]>([]);
  const [comment, setComment] = useState('');

  // Android back button does nothing here.
  useFocusEffect(
    useCallback(() => {
      const sub = BackHandler.addEventListener('hardwareBackPress', () => true);
      return () => sub.remove();
    }, []),
  );

  const ride = pending.data;
  const leave = () => router.dismissTo('/');

  if (!ride) {
    return (
      <Screen>
        <View style={styles.center}>
          {pending.isPending || pending.isFetching ? (
            <ActivityIndicator color={theme.primary} size="large" />
          ) : (
            <>
              <EmptyState icon={CircleCheck} title={t('rating.nothingPending')} />
              <Button title={t('ride.backHome')} onPress={leave} />
            </>
          )}
        </View>
      </Screen>
    );
  }

  const role = rideRole(ride, user?.id, mode ?? 'passenger');
  const other = role === 'passenger' ? ride.driver : ride.passenger;
  const tagOptions = RATING_TAGS[role];
  const PaymentIcon = PAYMENT_ICONS[ride.payment_method];

  const submit = () => {
    rate.mutate(
      { id: ride.id, stars, tags, comment: comment.trim() || undefined },
      {
        onSuccess: (result) => {
          track('rating_submitted', { role, stars });
          confirmHaptic();
          // Doc 20: without signal it stays queued and is sent when the network comes back.
          showToast(result.status === 'queued' ? t('offline.ratingQueued') : t('rating.thanks'), 'success');
          leave();
        },
        onError: (error) => {
          // Already rated (another device, or a retried request): just move on.
          if (error instanceof ApiError && error.code === 'rating_already_submitted') {
            void pending.refetch();
            leave();
            return;
          }
          showToast(apiErrorMessage(error), 'danger');
        },
      },
    );
  };

  return (
    <View style={{ flex: 1 }}>
      <Screen
        footer={
          <Button title={t('rating.submit')} disabled={stars === 0} loading={rate.isPending} onPress={submit} />
        }>
        <Arrival ride={ride} role={role} firstName={firstName(user?.full_name)} />

        <View style={styles.hero}>
          <Avatar name={other?.first_name} photoUrl={role === 'passenger' ? ride.driver?.photo_url : null} size={72} />
          <Txt variant="heading" align="center" accessibilityRole="header">
            {role === 'passenger' ? t('rating.titlePassenger', { name: other?.first_name ?? '' }) : t('rating.titleDriver', { name: other?.first_name ?? '' })}
          </Txt>
          <Txt color="muted" align="center">
            {t('rating.subtitle')}
          </Txt>
        </View>

        {role === 'driver' && hasDiscount(ride) ? (
          <Notice
            tone="success"
            icon={HandCoins}
            title={t('drive.promo.creditedTitle', { discount: formatFare(ride.discount) })}
            style={{ marginBottom: space.lg }}>
            {t('drive.promo.creditedBody', {
              name: ride.promotion?.name ?? t('quote.promo.promotion'),
              total: formatFare(amountToPay(ride)),
            })}
          </Notice>
        ) : null}

        <StarInput
          value={stars}
          onChange={(value) => {
            selectionHaptic();
            setStars(value);
          }}
        />
        <Txt variant="label" color="muted" align="center" style={{ marginTop: space.xs, minHeight: 18 }}>
          {stars ? t(`rating.level.${stars}`) : ''}
        </Txt>

        {stars ? (
          <View style={{ marginTop: space.lg, gap: space.sm }}>
            <Txt variant="overline" color="muted">
              {stars >= 4 ? t('rating.whatWentWell') : t('rating.whatToImprove')}
            </Txt>
            <View style={styles.tags}>
              {tagOptions.map((tag) => (
                <Chip
                  key={tag}
                  label={t(`rating.tag.${tag}`)}
                  selected={tags.includes(tag)}
                  onPress={() => setTags((prev) => (prev.includes(tag) ? prev.filter((x) => x !== tag) : [...prev, tag]))}
                />
              ))}
            </View>
            <Field
              label={t('rating.comment')}
              value={comment}
              onChangeText={setComment}
              placeholder={t('rating.commentPlaceholder')}
              multiline
              maxLength={500}
              style={{ minHeight: 72, textAlignVertical: 'top' }}
            />
          </View>
        ) : null}

        <Card tone="tint" style={{ marginTop: space.lg, gap: space.sm }}>
          <View style={styles.summary}>
            {PaymentIcon ? <PaymentIcon size={20} color={theme.muted} /> : null}
            <Txt variant="bodyStrong" style={{ flex: 1 }}>
              {t(`payment.${ride.payment_method}`)}
            </Txt>
            <Txt style={{ fontFamily: fonts.extrabold, fontSize: 22, color: theme.text }} tabular>
              {formatFare(amountToPay(ride))}
            </Txt>
          </View>
          <VesLine ves={ride.total_ves} align="right" />
          {role === 'passenger' ? <DiscountNote item={ride} /> : null}
          <Txt variant="caption" color="muted">
            {t('quote.meta', { distance: formatDistance(ride.distance_m, i18n.language), time: formatDuration(ride.duration_s) })}
          </Txt>
          <PlaceRows pickup={ride.pickup} dropoff={ride.dropoff} compact />
        </Card>

        {/* Discreet way out to report the ride; the report flow comes back here (rating is still mandatory). */}
        <Pressable
          accessibilityRole="link"
          hitSlop={8}
          onPress={() => router.push({ pathname: '/report', params: { ride_id: ride.id } })}
          style={({ pressed }) => [styles.reportLink, { opacity: pressed ? 0.6 : 1 }]}>
          <Flag size={14} color={theme.muted} strokeWidth={2.2} />
          <Txt variant="label" color="muted" style={{ textDecorationLine: 'underline' }}>
            {t('rating.reportLink')}
          </Txt>
        </Pressable>
      </Screen>
      {/* Over everything, once: the ride is over. */}
      <Confetti />
    </View>
  );
}

const styles = StyleSheet.create({
  center: { flex: 1, alignItems: 'center', justifyContent: 'center', gap: space.md },
  hero: { alignItems: 'center', gap: space.xs, paddingTop: space.lg, paddingBottom: space.lg },
  arrival: { alignItems: 'center', gap: space.xs, borderRadius: 24, padding: space.lg, marginTop: space.md },
  earned: { fontFamily: fonts.extrabold, fontSize: 48, lineHeight: 56 },
  tags: { flexDirection: 'row', flexWrap: 'wrap', gap: space.xs },
  summary: { flexDirection: 'row', alignItems: 'center', gap: space.sm },
  reportLink: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: 6,
    alignSelf: 'center',
    minHeight: 44,
    paddingHorizontal: space.md,
    marginTop: space.sm,
  },
});
