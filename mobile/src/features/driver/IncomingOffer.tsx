import { router } from 'expo-router';
import { useEffect, useRef, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Modal, Pressable, ScrollView, StyleSheet, Text, View } from 'react-native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';

import { Navigation, Route } from '@/components/icons';
import { showToast } from '@/components/Toast';
import { Txt } from '@/components/ui';
import { CountdownRing, PAYMENT_ICONS, RatingBadge } from '@/features/ride/components';
import { routedRides } from '@/features/ride/store';
import { useAppConfig } from '@/hooks/useDriver';
import { useOfferResponse } from '@/hooks/useRides';
import { apiErrorMessage } from '@/i18n';
import { ApiError } from '@/lib/api';
import { confirmHaptic, playOfferAlert, tick } from '@/lib/feedback';
import { formatDistance, formatDuration, formatFare, secondsUntil } from '@/lib/ride';
import type { Offer } from '@/lib/types';
import { fonts, palette, radius, space } from '@/theme';

// The offer screen is always dark (high contrast in the sun, matches the design canvas).
const c = palette.dark;

/** Full-screen incoming ride request with a countdown, big ACEPTAR and a smaller "Rechazar". */
export function IncomingOffer({ offer }: { offer: Offer | null }) {
  const { t, i18n } = useTranslation();
  const insets = useSafeAreaInsets();
  const { config } = useAppConfig();
  const respond = useOfferResponse();
  const [now, setNow] = useState(() => Date.now());
  const [dismissed, setDismissed] = useState<string | null>(null);
  const alerted = useRef<string | null>(null);

  const left = offer ? secondsUntil(offer.expires_at, now) : 0;
  const visible = !!offer && left > 0 && dismissed !== offer.ride_id;
  const total = Math.max(left, config.offer_timeout_seconds ?? 15);

  useEffect(() => {
    if (!visible) return;
    const timer = setInterval(() => setNow(Date.now()), 250);
    return () => clearInterval(timer);
  }, [visible]);

  // Alert once per offer: sound + haptic.
  useEffect(() => {
    if (visible && offer && alerted.current !== offer.ride_id) {
      alerted.current = offer.ride_id;
      void playOfferAlert();
    }
  }, [visible, offer]);

  // A tick each second for the last five seconds.
  useEffect(() => {
    if (visible && left > 0 && left <= 5) tick();
  }, [visible, left]);

  // Expired without an answer: the server moves on to the next driver.
  useEffect(() => {
    if (offer && left === 0 && alerted.current === offer.ride_id && dismissed !== offer.ride_id) {
      setDismissed(offer.ride_id);
      showToast(t('drive.toast.offerExpired'));
    }
  }, [offer, left, dismissed, t]);

  if (!offer) return null;
  const PaymentIcon = PAYMENT_ICONS[offer.payment_method];

  const answer = (accept: boolean) => {
    if (respond.isPending) return;
    if (accept) {
      confirmHaptic();
      routedRides.add(offer.ride_id);
    }
    respond.mutate(
      { rideId: offer.ride_id, accept },
      {
        onSuccess: () => {
          setDismissed(offer.ride_id);
          if (accept) router.push({ pathname: '/drive', params: { id: offer.ride_id } });
        },
        onError: (error) => {
          setDismissed(offer.ride_id);
          const gone = error instanceof ApiError && (error.code === 'offer_expired' || error.code === 'ride_taken');
          showToast(apiErrorMessage(error), gone ? 'info' : 'danger');
        },
      },
    );
  };

  return (
    <Modal visible={visible} animationType="fade" presentationStyle="fullScreen" statusBarTranslucent onRequestClose={() => answer(false)}>
      <View style={[styles.screen, { paddingTop: insets.top + space.md, paddingBottom: Math.max(insets.bottom, space.md) }]}>
        <ScrollView contentContainerStyle={styles.body} showsVerticalScrollIndicator={false}>
          <Text style={styles.overline}>{t('drive.offer.title')}</Text>

          <CountdownRing progress={left / total} color={left <= 5 ? c.accent : c.primary} track={c.border}>
            <Text style={styles.seconds} accessibilityLabel={t('drive.offer.secondsLeft', { count: left })}>
              {left}
            </Text>
            <Text style={styles.secondsLabel}>{t('drive.offer.seconds')}</Text>
          </CountdownRing>

          <View style={{ alignItems: 'center', gap: space.xs }}>
            <Text style={styles.fare} accessibilityLabel={t('drive.offer.fareA11y', { fare: formatFare(offer.fare) })}>
              {formatFare(offer.fare)}
            </Text>
            <View style={styles.payment}>
              {PaymentIcon ? <PaymentIcon size={16} color={c.text} strokeWidth={2.2} /> : null}
              <Text style={styles.paymentText}>{t(`payment.${offer.payment_method}`)}</Text>
            </View>
          </View>

          <View style={styles.card}>
            <View style={styles.passenger}>
              <Txt variant="subtitle" style={{ color: c.text, flex: 1 }} numberOfLines={1}>
                {offer.passenger.first_name}
              </Txt>
              <RatingBadge rating={offer.passenger.rating} />
            </View>
            <View style={styles.metaRow}>
              <Navigation size={16} color={c.primary} strokeWidth={2.4} />
              <Text style={styles.meta}>
                {t('drive.offer.toPickup', {
                  distance: formatDistance(offer.pickup_distance_m, i18n.language),
                  time: formatDuration(offer.pickup_eta_s),
                })}
              </Text>
            </View>
            <View style={styles.metaRow}>
              <Route size={16} color={c.accent} strokeWidth={2.4} />
              <Text style={styles.meta}>
                {t('drive.offer.trip', {
                  distance: formatDistance(offer.distance_m, i18n.language),
                  time: formatDuration(offer.duration_s),
                })}
              </Text>
            </View>
            <View style={styles.divider} />
            <PlaceRowsDark pickup={offer.pickup.address} dropoff={offer.dropoff.address} />
          </View>
        </ScrollView>

        <View style={styles.actions}>
          <Pressable
            accessibilityRole="button"
            accessibilityLabel={t('drive.offer.accept')}
            accessibilityState={{ busy: respond.isPending }}
            onPress={() => answer(true)}
            style={({ pressed }) => [styles.accept, { backgroundColor: pressed ? c.primaryPressed : c.primary, transform: [{ scale: pressed ? 0.98 : 1 }] }]}>
            <Text style={styles.acceptText}>{t('drive.offer.accept').toLocaleUpperCase()}</Text>
          </Pressable>
          <Pressable
            accessibilityRole="button"
            accessibilityLabel={t('drive.offer.decline')}
            onPress={() => answer(false)}
            hitSlop={8}
            style={({ pressed }) => [styles.decline, { opacity: pressed ? 0.6 : 1 }]}>
            <Text style={styles.declineText}>{t('drive.offer.decline')}</Text>
          </Pressable>
        </View>
      </View>
    </Modal>
  );
}

function PlaceRowsDark({ pickup, dropoff }: { pickup: string; dropoff: string }) {
  const { t } = useTranslation();
  return (
    <View style={{ gap: 2 }}>
      <View style={styles.placeRow}>
        <View style={[styles.dot, { backgroundColor: c.primary }]} />
        <View style={{ flex: 1 }}>
          <Text style={styles.placeLabel}>{t('ride.pickup')}</Text>
          <Text style={styles.placeText} numberOfLines={2}>
            {pickup}
          </Text>
        </View>
      </View>
      <View style={styles.connector} />
      <View style={styles.placeRow}>
        <View style={[styles.square, { backgroundColor: c.accent }]} />
        <View style={{ flex: 1 }}>
          <Text style={styles.placeLabel}>{t('ride.dropoff')}</Text>
          <Text style={styles.placeText} numberOfLines={2}>
            {dropoff}
          </Text>
        </View>
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  screen: { flex: 1, backgroundColor: c.background, paddingHorizontal: space.lg },
  body: { alignItems: 'center', gap: space.lg, paddingBottom: space.lg },
  overline: { fontFamily: fonts.bold, fontSize: 13, letterSpacing: 1.6, color: c.primary, textTransform: 'uppercase' },
  seconds: { fontFamily: fonts.extrabold, fontSize: 52, color: c.text, fontVariant: ['tabular-nums'] },
  secondsLabel: { fontFamily: fonts.semibold, fontSize: 13, color: c.muted, marginTop: -6 },
  fare: { fontFamily: fonts.extrabold, fontSize: 56, letterSpacing: -1.5, color: c.text, fontVariant: ['tabular-nums'] },
  payment: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 6,
    backgroundColor: c.surfaceAlt,
    borderRadius: radius.pill,
    paddingHorizontal: 12,
    paddingVertical: 6,
  },
  paymentText: { fontFamily: fonts.bold, fontSize: 14, color: c.text },
  card: { alignSelf: 'stretch', backgroundColor: c.surface, borderRadius: radius.card, padding: space.lg, gap: space.sm },
  passenger: { flexDirection: 'row', alignItems: 'center', gap: space.sm },
  metaRow: { flexDirection: 'row', alignItems: 'center', gap: space.xs },
  meta: { fontFamily: fonts.semibold, fontSize: 15, color: c.text },
  divider: { height: 1, backgroundColor: c.border, marginVertical: space.xs },
  placeRow: { flexDirection: 'row', alignItems: 'flex-start', gap: space.sm },
  dot: { width: 14, height: 14, borderRadius: 7, marginTop: 4 },
  square: { width: 14, height: 14, borderRadius: 4, marginTop: 4 },
  connector: { width: 2, height: 12, backgroundColor: c.border, marginLeft: 6 },
  placeLabel: { fontFamily: fonts.bold, fontSize: 12, color: c.muted },
  placeText: { fontFamily: fonts.bold, fontSize: 15, color: c.text, lineHeight: 21 },
  actions: { gap: space.xs, paddingTop: space.sm },
  accept: { height: 76, borderRadius: radius.pill, alignItems: 'center', justifyContent: 'center' },
  acceptText: { fontFamily: fonts.extrabold, fontSize: 22, letterSpacing: 2, color: c.onPrimary },
  decline: { height: 52, alignItems: 'center', justifyContent: 'center' },
  declineText: { fontFamily: fonts.bold, fontSize: 16, color: c.muted },
});
