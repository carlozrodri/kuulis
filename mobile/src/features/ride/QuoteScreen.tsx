import { useQueryClient } from '@tanstack/react-query';
import { router } from 'expo-router';
import { useEffect, useMemo, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { StyleSheet, View } from 'react-native';

import { Bike, ChevronLeft, CircleX, Clock, Zap } from '@/components/icons';
import { RideMap } from '@/components/map/RideMap';
import { MapSheetLayout } from '@/components/MapSheetLayout';
import { showToast } from '@/components/Toast';
import { Button, Card, IconButton, Notice, Skeleton, Txt } from '@/components/ui';
import { useAppConfig } from '@/hooks/useDriver';
import { rideKeys, useQuote, useRequestRide } from '@/hooks/useRides';
import { apiErrorMessage } from '@/i18n';
import { ApiError } from '@/lib/api';
import { confirmHaptic, selectionHaptic } from '@/lib/feedback';
import {
  decodePolyline,
  DEFAULT_PAYMENT_METHODS,
  formatArrival,
  formatDistance,
  formatDuration,
  formatFare,
  formatSurge,
  hasSurge,
  secondsUntil,
} from '@/lib/ride';
import { useStore } from '@/lib/store';
import { fonts, radius, space, useTheme } from '@/theme';

import { PaymentChips, PlaceRows } from './components';
import { loadSavedPayment, rideDraft, routedRides, setDraftPayment } from './store';

/** Route and price before confirming: big fare, surge badge, payment method and "PEDIR MOTO · $x". */
export function QuoteScreen() {
  const { t, i18n } = useTranslation();
  const theme = useTheme();
  const queryClient = useQueryClient();
  const draft = useStore(rideDraft);
  const { config } = useAppConfig();
  const quote = useQuote(draft.pickup, draft.dropoff);
  const request = useRequestRide();
  const [now, setNow] = useState(() => Date.now());

  const methods = config.payment_methods?.length ? config.payment_methods : DEFAULT_PAYMENT_METHODS;
  // Last used method, else the first one (cash): asking every time would add a tap.
  const payment = draft.paymentMethod && methods.includes(draft.paymentMethod) ? draft.paymentMethod : (methods[0] ?? null);

  useEffect(() => {
    void loadSavedPayment();
  }, []);

  // Refresh the price shortly before the quote expires (quote_ttl_seconds).
  useEffect(() => {
    const timer = setInterval(() => setNow(Date.now()), 5000);
    return () => clearInterval(timer);
  }, []);
  const expired = !!quote.data && secondsUntil(quote.data.expires_at, now) <= 5;
  useEffect(() => {
    if (expired && !request.isPending) void quote.refetch();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [expired]);

  const route = useMemo(() => decodePolyline(quote.data?.polyline), [quote.data?.polyline]);

  const submit = async () => {
    if (!quote.data || !payment) return;
    try {
      let current = quote.data;
      if (secondsUntil(current.expires_at) <= 3) current = (await quote.refetch()).data ?? current;
      const ride = await request.mutateAsync({ quote_id: current.quote_id, payment_method: payment });
      routedRides.add(ride.id);
      confirmHaptic();
      rideDraft.set((d) => ({ ...d, dropoff: null }));
      router.replace({ pathname: '/ride', params: { id: ride.id } });
    } catch (error) {
      if (error instanceof ApiError) {
        if (error.code === 'quote_expired') {
          await quote.refetch();
          showToast(t('quote.priceUpdated'));
          return;
        }
        if (error.code === 'rating_required' || error.code === 'ride_already_active') {
          // The ride navigator takes the user to the pending rating / active ride.
          void queryClient.invalidateQueries({ queryKey: rideKeys.pendingRating });
          void queryClient.invalidateQueries({ queryKey: rideKeys.active });
        }
      }
      showToast(apiErrorMessage(error), 'danger');
    }
  };

  const fare = quote.data ? formatFare(quote.data.fare) : '';
  const quoteError = quote.isError ? quote.error : null;
  const outside = quoteError instanceof ApiError && quoteError.code === 'outside_service_area';

  return (
    <MapSheetLayout
      tabBar={false}
      map={(insets) => (
        <RideMap
          insets={insets}
          pickup={draft.pickup}
          dropoff={draft.dropoff}
          route={route}
          showUser={false}
          fitKey={`${quote.data?.quote_id ?? ''}-${route.length}`}
        />
      )}
      topBar={
        <View style={{ flexDirection: 'row' }}>
          <IconButton icon={ChevronLeft} label={t('common.back')} onPress={() => router.back()} />
        </View>
      }
      footer={
        quoteError ? (
          <Button title={t('quote.changeDestination')} variant="secondary" onPress={() => router.back()} />
        ) : (
          <Button
            title={quote.data ? t('quote.request', { fare }) : t('quote.request', { fare: '…' })}
            icon={Bike}
            loading={request.isPending}
            disabled={!quote.data || !payment || quote.isFetching}
            accessibilityHint={!payment ? t('quote.choosePayment') : undefined}
            onPress={() => void submit()}
          />
        )
      }>
      <PlaceRows
        pickup={draft.pickup}
        dropoff={draft.dropoff}
        compact
        onPressPickup={() => router.push({ pathname: '/ride/search', params: { field: 'pickup' } })}
        onPressDropoff={() => router.push({ pathname: '/ride/search', params: { field: 'dropoff' } })}
      />

      {quoteError ? (
        <Notice tone={outside ? 'warning' : 'danger'} icon={CircleX} title={outside ? t('quote.outsideTitle') : t('common.error')}>
          <Txt variant="caption" style={{ fontSize: 14, lineHeight: 20 }}>
            {apiErrorMessage(quoteError)}
          </Txt>
          {!outside ? (
            <Button title={t('common.retry')} variant="secondary" size="sm" style={{ alignSelf: 'flex-start' }} onPress={() => void quote.refetch()} />
          ) : null}
        </Notice>
      ) : (
        <Card selected style={styles.vehicle} accessibilityLabel={t('quote.vehicleA11y', { fare })}>
          <View style={[styles.vehicleIcon, { backgroundColor: theme.surface }]}>
            <Bike size={30} color={theme.primary} strokeWidth={2} />
          </View>
          <View style={{ flex: 1, gap: 2 }}>
            <Txt variant="subtitle">{t('quote.moto')}</Txt>
            {quote.data ? (
              <>
                <Txt variant="caption" color="muted">
                  {t('quote.meta', {
                    distance: formatDistance(quote.data.distance_m, i18n.language),
                    time: formatDuration(quote.data.duration_s),
                  })}
                </Txt>
                <View style={styles.eta}>
                  <Clock size={13} color={theme.muted} strokeWidth={2.4} />
                  <Txt variant="caption" color="muted">
                    {t('quote.arrival', { time: formatArrival(quote.data.duration_s, new Date(), i18n.language) })}
                  </Txt>
                </View>
              </>
            ) : (
              <Skeleton height={14} width="70%" />
            )}
          </View>
          <View style={{ alignItems: 'flex-end', gap: 4 }}>
            {quote.data ? (
              <Txt style={[styles.fare, { color: theme.scheme === 'dark' ? theme.primary : theme.primaryPressed }]} tabular>
                {fare}
              </Txt>
            ) : (
              <Skeleton height={32} width={80} />
            )}
            {quote.data && hasSurge(quote.data.surge_multiplier) ? (
              <View style={[styles.surge, { backgroundColor: theme.accent }]} accessibilityLabel={t('quote.surgeA11y', { value: formatSurge(quote.data.surge_multiplier) })}>
                <Zap size={12} color={theme.onAccent} fill={theme.onAccent} />
                <Txt variant="micro" style={{ color: theme.onAccent }}>
                  {t('quote.surge', { value: formatSurge(quote.data.surge_multiplier) })}
                </Txt>
              </View>
            ) : null}
          </View>
        </Card>
      )}

      {!quoteError ? (
        <View style={{ gap: space.xs }}>
          <Txt variant="overline" color="muted">
            {t('ride.paymentMethod')}
          </Txt>
          <PaymentChips
            methods={methods}
            value={payment}
            onChange={(method) => {
              selectionHaptic();
              setDraftPayment(method);
            }}
          />
          <Txt variant="caption" color="muted">
            {payment ? t('quote.payDriver') : t('quote.choosePayment')}
          </Txt>
        </View>
      ) : null}
    </MapSheetLayout>
  );
}

const styles = StyleSheet.create({
  vehicle: { flexDirection: 'row', alignItems: 'center', gap: space.sm, padding: space.md },
  vehicleIcon: { width: 56, height: 56, borderRadius: radius.tile, alignItems: 'center', justifyContent: 'center' },
  eta: { flexDirection: 'row', alignItems: 'center', gap: 4 },
  fare: { fontFamily: fonts.extrabold, fontSize: 30, lineHeight: 36, letterSpacing: -0.8 },
  surge: { flexDirection: 'row', alignItems: 'center', gap: 3, borderRadius: radius.pill, paddingHorizontal: 8, paddingVertical: 3 },
});
