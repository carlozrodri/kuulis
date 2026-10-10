import { router } from 'expo-router';
import { useEffect } from 'react';
import { useTranslation } from 'react-i18next';
import { View } from 'react-native';

import { History, MapPinned } from '@/components/icons';
import { Card, ListRow, Skeleton, Txt } from '@/components/ui';
import { PaymentChips } from '@/features/ride/components';
import { loadSavedPayment, rideDraft, setDraftPayment, setDraftPlace } from '@/features/ride/store';
import { useAppConfig } from '@/hooks/useDriver';
import { DEFAULT_PAYMENT_METHODS, shortAddress } from '@/lib/ride';
import { useStore } from '@/lib/store';
import type { FrequentPlace, PassengerStats } from '@/lib/types';
import { radius, space } from '@/theme';

import { Section } from './components';

/** Frequent destination: straight to the price (pickup = where the passenger is), or search if unknown. */
function rideTo(place: FrequentPlace) {
  setDraftPlace('dropoff', { lat: place.lat, lng: place.lng, address: place.address });
  router.push(rideDraft.get().pickup ? '/ride/quote' : '/ride/search');
}

export function PassengerProfile({ stats, loading }: { stats: PassengerStats | null | undefined; loading: boolean }) {
  const { t } = useTranslation();
  const { config } = useAppConfig();
  const draft = useStore(rideDraft);
  const methods = config.payment_methods?.length ? config.payment_methods : DEFAULT_PAYMENT_METHODS;

  useEffect(() => {
    void loadSavedPayment();
  }, []);

  const places = stats?.frequent_places ?? [];

  return (
    <>
      <Section title={t('profile.places.title')}>
        <Card style={{ paddingVertical: space.xxs }}>
          {loading && !stats ? (
            <View style={{ gap: space.xs, paddingVertical: space.sm }}>
              <Skeleton height={44} radius={radius.tile} />
              <Skeleton height={44} radius={radius.tile} />
            </View>
          ) : places.length ? (
            places.map((place, index) => (
              <ListRow
                key={place.address}
                icon={MapPinned}
                iconTone={index === 0 ? 'accent' : 'primary'}
                title={shortAddress(place.address)}
                subtitle={t('profile.places.visits', { count: place.rides })}
                accessibilityHint={t('profile.places.goHint')}
                divider={index < places.length - 1}
                onPress={() => rideTo(place)}
              />
            ))
          ) : (
            <ListRow icon={MapPinned} iconTone="neutral" title={t('profile.places.empty')} subtitle={t('profile.places.emptyBody')} />
          )}
        </Card>
      </Section>

      <Section title={t('profile.payment.title')}>
        <Card style={{ gap: space.sm }}>
          <Txt variant="caption" color="muted">
            {t('profile.payment.body')}
          </Txt>
          <PaymentChips methods={methods} value={draft.paymentMethod} onChange={setDraftPayment} />
        </Card>
      </Section>

      <Section title={t('profile.activity')}>
        <Card style={{ paddingVertical: space.xxs }}>
          <ListRow
            icon={History}
            title={t('profile.history')}
            subtitle={stats ? t('stats.total', { count: stats.rides }) : t('profile.historyHint')}
            onPress={() => router.push('/rides')}
          />
        </Card>
      </Section>
    </>
  );
}
