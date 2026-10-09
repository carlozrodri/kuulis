import { router, useFocusEffect } from 'expo-router';
import { useCallback, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { ActivityIndicator, BackHandler, StyleSheet, View } from 'react-native';

import { CircleCheck } from '@/components/icons';
import { showToast } from '@/components/Toast';
import { Button, Card, Chip, EmptyState, Field, Screen, Txt } from '@/components/ui';
import { usePendingRating, useRateRide } from '@/hooks/useRides';
import { apiErrorMessage } from '@/i18n';
import { ApiError } from '@/lib/api';
import { confirmHaptic, selectionHaptic } from '@/lib/feedback';
import { formatDistance, formatDuration, formatFare, RATING_TAGS, rideRole } from '@/lib/ride';
import { useAuth } from '@/providers/AuthProvider';
import { useMode } from '@/providers/ModeProvider';
import { fonts, space, useTheme } from '@/theme';

import { Avatar, PAYMENT_ICONS, PlaceRows, StarInput } from './components';

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
        onSuccess: () => {
          confirmHaptic();
          showToast(t('rating.thanks'), 'success');
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
    <Screen
      footer={
        <Button title={t('rating.submit')} disabled={stars === 0} loading={rate.isPending} onPress={submit} />
      }>
      <View style={styles.hero}>
        <Avatar name={other?.first_name} photoUrl={role === 'passenger' ? ride.driver?.photo_url : null} size={84} />
        <Txt variant="title" align="center" accessibilityRole="header">
          {role === 'passenger' ? t('rating.titlePassenger', { name: other?.first_name ?? '' }) : t('rating.titleDriver', { name: other?.first_name ?? '' })}
        </Txt>
        <Txt color="muted" align="center">
          {t('rating.subtitle')}
        </Txt>
      </View>

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
            {formatFare(ride.fare)}
          </Txt>
        </View>
        <Txt variant="caption" color="muted">
          {t('quote.meta', { distance: formatDistance(ride.distance_m, i18n.language), time: formatDuration(ride.duration_s) })}
        </Txt>
        <PlaceRows pickup={ride.pickup} dropoff={ride.dropoff} compact />
      </Card>
    </Screen>
  );
}

const styles = StyleSheet.create({
  center: { flex: 1, alignItems: 'center', justifyContent: 'center', gap: space.md },
  hero: { alignItems: 'center', gap: space.xs, paddingTop: space.xl, paddingBottom: space.lg },
  tags: { flexDirection: 'row', flexWrap: 'wrap', gap: space.xs },
  summary: { flexDirection: 'row', alignItems: 'center', gap: space.sm },
});
