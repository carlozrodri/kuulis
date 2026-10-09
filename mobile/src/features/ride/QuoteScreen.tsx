import { useQueryClient } from '@tanstack/react-query';
import { router } from 'expo-router';
import { useEffect, useMemo, useRef, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Pressable, StyleSheet, TextInput, View } from 'react-native';

import { BadgePercent, Bike, ChevronLeft, CircleX, Clock, TicketPercent, X, Zap } from '@/components/icons';
import { RideMap } from '@/components/map/RideMap';
import { MapSheetLayout } from '@/components/MapSheetLayout';
import { VesTiles } from '@/components/Money';
import { showToast } from '@/components/Toast';
import { Button, Card, IconButton, Notice, Skeleton, Txt } from '@/components/ui';
import { useAppConfig } from '@/hooks/useDriver';
import { fetchQuote, quoteKey, rideKeys, useQuote, useRequestRide } from '@/hooks/useRides';
import { apiErrorMessage } from '@/i18n';
import { ApiError } from '@/lib/api';
import { confirmHaptic, selectionHaptic } from '@/lib/feedback';
import { amountToPay, hasDiscount, normalizePromoCode, promotionInvalidReason } from '@/lib/money';
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
import { loadSavedPayment, rideDraft, routedRides, setDraftPayment, setDraftPromoCode } from './store';

const isPromoInvalid = (error: unknown) => error instanceof ApiError && error.code === 'promotion_invalid';

/**
 * Route and price before confirming: big price (the total after any promotion, with the original fare struck
 * through), surge badge, bolívar equivalents, promo code, payment method and "PEDIR MOTO · $x".
 */
export function QuoteScreen() {
  const { t, i18n } = useTranslation();
  const theme = useTheme();
  const queryClient = useQueryClient();
  const draft = useStore(rideDraft);
  const { config } = useAppConfig();
  const quote = useQuote(draft.pickup, draft.dropoff, 'moto', draft.promoCode);
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

  // A code that stops applying on a later re-quote (expired, exhausted…) is dropped so the price still shows.
  const droppedFor = useRef<unknown>(null);
  useEffect(() => {
    const code = draft.promoCode;
    if (!code || !quote.isError || !isPromoInvalid(quote.error) || droppedFor.current === quote.error) return;
    droppedFor.current = quote.error;
    setDraftPromoCode(null);
    showToast(
      t('quote.promo.dropped', { code, reason: t(`quote.promo.invalid.${promotionInvalidReason((quote.error as ApiError).details)}`) }),
      'danger',
    );
  }, [draft.promoCode, quote.isError, quote.error, t]);

  const route = useMemo(() => decodePolyline(quote.data?.polyline), [quote.data?.polyline]);

  const submit = async () => {
    if (!quote.data || !payment) return;
    try {
      let current = quote.data;
      if (secondsUntil(current.expires_at) <= 3) current = (await quote.refetch()).data ?? current;
      const ride = await request.mutateAsync({ quote_id: current.quote_id, payment_method: payment });
      routedRides.add(ride.id);
      confirmHaptic();
      rideDraft.set((d) => ({ ...d, dropoff: null, promoCode: null }));
      router.replace({ pathname: '/ride', params: { id: ride.id } });
    } catch (error) {
      if (error instanceof ApiError) {
        if (error.code === 'quote_expired') {
          await quote.refetch();
          showToast(t('quote.priceUpdated'));
          return;
        }
        if (error.code === 'promotion_unavailable') {
          // The promotion ran out between the quote and the request: quote again (without the code, if any).
          if (draft.promoCode) setDraftPromoCode(null);
          else await quote.refetch();
          showToast(t('quote.promo.unavailable'), 'danger');
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

  const fare = quote.data ? formatFare(amountToPay(quote.data)) : '';
  const discounted = !!quote.data && hasDiscount(quote.data);
  // A promotion_invalid while a code is applied is handled above (the code is dropped and the price re-quoted).
  const quoteError = quote.isError && !(draft.promoCode && isPromoInvalid(quote.error)) ? quote.error : null;
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
        <Card
          selected
          style={styles.vehicle}
          accessibilityLabel={
            discounted && quote.data
              ? t('quote.vehicleA11yDiscount', {
                  fare,
                  original: formatFare(quote.data.fare),
                  name: quote.data.promotion?.name ?? t('quote.promo.promotion'),
                })
              : t('quote.vehicleA11y', { fare })
          }>
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
            {quote.data && discounted ? (
              <Txt variant="caption" color="muted" tabular style={styles.strike}>
                {formatFare(quote.data.fare)}
              </Txt>
            ) : null}
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
            {quote.data && discounted ? (
              <View style={[styles.surge, { backgroundColor: theme.accent }]}>
                <Txt variant="micro" style={{ color: theme.onAccent }} tabular>
                  −{formatFare(quote.data.discount)}
                </Txt>
              </View>
            ) : null}
          </View>
        </Card>
      )}

      {!quoteError && quote.data ? (
        <>
          {discounted || draft.promoCode ? (
            <PromotionBanner
              name={quote.data.promotion?.name ?? null}
              discount={discounted ? formatFare(quote.data.discount) : null}
              code={draft.promoCode}
              onRemove={() => {
                selectionHaptic();
                setDraftPromoCode(null);
                showToast(t('quote.promo.removed'));
              }}
            />
          ) : null}
          <VesTiles ves={quote.data.total_ves} />
          {!draft.promoCode ? <PromoCodeEntry /> : null}
        </>
      ) : null}

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

/** Applied promotion: name, savings and (for a code) a button to remove it. */
function PromotionBanner({
  name,
  discount,
  code,
  onRemove,
}: {
  name: string | null;
  discount: string | null;
  code: string | null;
  onRemove: () => void;
}) {
  const { t } = useTranslation();
  const theme = useTheme();
  const title = name ? t('quote.promo.appliedNamed', { name }) : code ? t('quote.promo.applied', { code }) : t('quote.promo.promotion');
  return (
    <View style={[styles.banner, { backgroundColor: theme.accentSoft }]}>
      <BadgePercent size={22} color={theme.onAccentSoft} strokeWidth={2.2} />
      <View style={{ flex: 1, gap: 1 }}>
        <Txt variant="bodyStrong" style={{ color: theme.onAccentSoft }} numberOfLines={1}>
          {title}
        </Txt>
        <Txt variant="caption" style={{ color: theme.text }}>
          {discount
            ? code
              ? t('quote.promo.savingsCode', { discount, code })
              : t('quote.promo.savings', { discount })
            : t('quote.promo.noSavings')}
        </Txt>
      </View>
      {code ? (
        <Pressable
          accessibilityRole="button"
          accessibilityLabel={t('quote.promo.remove')}
          hitSlop={10}
          onPress={onRemove}
          style={({ pressed }) => [styles.bannerRemove, { backgroundColor: theme.surface, opacity: pressed ? 0.7 : 1 }]}>
          <X size={18} color={theme.text} strokeWidth={2.4} />
        </Pressable>
      ) : null}
    </View>
  );
}

/** "¿Tienes un código?": expands into a field that re-quotes with the code and explains why one does not apply. */
function PromoCodeEntry() {
  const { t } = useTranslation();
  const theme = useTheme();
  const queryClient = useQueryClient();
  const draft = useStore(rideDraft);
  const [open, setOpen] = useState(false);
  const [value, setValue] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [applying, setApplying] = useState(false);
  const [focused, setFocused] = useState(false);

  const apply = async () => {
    const code = normalizePromoCode(value);
    if (!code) {
      setError(t('quote.promo.empty'));
      return;
    }
    if (!draft.pickup || !draft.dropoff || applying) return;
    setApplying(true);
    setError(null);
    try {
      const quote = await fetchQuote(draft.pickup, draft.dropoff, 'moto', code);
      queryClient.setQueryData(quoteKey(draft.pickup, draft.dropoff, 'moto', code), quote);
      confirmHaptic();
      setDraftPromoCode(code);
      showToast(
        hasDiscount(quote) ? t('quote.promo.appliedToast', { discount: formatFare(quote.discount) }) : t('quote.promo.applied', { code }),
        'success',
      );
    } catch (e) {
      setError(isPromoInvalid(e) ? t(`quote.promo.invalid.${promotionInvalidReason((e as ApiError).details)}`) : apiErrorMessage(e));
    } finally {
      setApplying(false);
    }
  };

  if (!open) {
    return (
      <Pressable
        accessibilityRole="button"
        onPress={() => setOpen(true)}
        hitSlop={6}
        style={({ pressed }) => [styles.promoLink, { opacity: pressed ? 0.6 : 1 }]}>
        <TicketPercent size={20} color={theme.scheme === 'dark' ? theme.primary : theme.primaryPressed} strokeWidth={2.2} />
        <Txt variant="bodyStrong" style={{ color: theme.scheme === 'dark' ? theme.primary : theme.primaryPressed }}>
          {t('quote.promo.have')}
        </Txt>
      </Pressable>
    );
  }

  const borderColor = error ? theme.danger : focused ? theme.primary : theme.border;
  return (
    <View style={{ gap: 6 }}>
      <Txt variant="label" color="muted">
        {t('quote.promo.label')}
      </Txt>
      <View style={styles.promoRow}>
        <View style={[styles.promoInput, { borderColor, backgroundColor: theme.surface }]}>
          <TicketPercent size={20} color={focused ? theme.primary : theme.muted} strokeWidth={2} />
          <TextInput
            accessibilityLabel={t('quote.promo.label')}
            value={value}
            onChangeText={(text) => {
              setValue(text.toUpperCase());
              if (error) setError(null);
            }}
            placeholder={t('quote.promo.placeholder')}
            placeholderTextColor={theme.muted}
            selectionColor={theme.primary}
            cursorColor={theme.primary}
            autoCapitalize="characters"
            autoCorrect={false}
            autoComplete="off"
            autoFocus
            maxLength={32}
            returnKeyType="done"
            onSubmitEditing={() => void apply()}
            onFocus={() => setFocused(true)}
            onBlur={() => setFocused(false)}
            maxFontSizeMultiplier={1.4}
            style={[styles.promoText, { color: theme.text }]}
          />
          <Pressable
            accessibilityRole="button"
            accessibilityLabel={t('quote.promo.cancel')}
            hitSlop={10}
            onPress={() => {
              setOpen(false);
              setValue('');
              setError(null);
            }}>
            <X size={18} color={theme.muted} strokeWidth={2.4} />
          </Pressable>
        </View>
        <Button
          title={t('quote.promo.apply')}
          variant="secondary"
          loading={applying}
          disabled={!value.trim()}
          onPress={() => void apply()}
          style={styles.promoApply}
        />
      </View>
      {error ? (
        <Txt variant="caption" color="danger" accessibilityRole="alert">
          {error}
        </Txt>
      ) : null}
    </View>
  );
}

const styles = StyleSheet.create({
  vehicle: { flexDirection: 'row', alignItems: 'center', gap: space.sm, padding: space.md },
  vehicleIcon: { width: 56, height: 56, borderRadius: radius.tile, alignItems: 'center', justifyContent: 'center' },
  eta: { flexDirection: 'row', alignItems: 'center', gap: 4 },
  strike: { textDecorationLine: 'line-through' },
  banner: { flexDirection: 'row', alignItems: 'center', gap: space.sm, borderRadius: radius.tile, paddingHorizontal: 14, paddingVertical: space.sm },
  bannerRemove: { width: 32, height: 32, borderRadius: 16, alignItems: 'center', justifyContent: 'center' },
  promoLink: { flexDirection: 'row', alignItems: 'center', gap: space.xs, alignSelf: 'flex-start', minHeight: 44 },
  promoRow: { flexDirection: 'row', alignItems: 'center', gap: space.xs },
  promoInput: {
    flex: 1,
    flexDirection: 'row',
    alignItems: 'center',
    gap: space.xs,
    height: 52,
    borderWidth: 1.5,
    borderRadius: radius.field,
    paddingHorizontal: 12,
  },
  promoText: { flex: 1, fontFamily: fonts.bold, fontSize: 16, letterSpacing: 1, paddingVertical: 0 },
  promoApply: { marginTop: 0, height: 52, paddingHorizontal: space.md },
  fare: { fontFamily: fonts.extrabold, fontSize: 30, lineHeight: 36, letterSpacing: -0.8 },
  surge: { flexDirection: 'row', alignItems: 'center', gap: 3, borderRadius: radius.pill, paddingHorizontal: 8, paddingVertical: 3 },
});
