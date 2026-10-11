import { router } from 'expo-router';
import { useEffect } from 'react';
import { useTranslation } from 'react-i18next';
import { View } from 'react-native';

import { History, MapPinned } from '@/components/icons';
import { Card, ListRow, Skeleton, Txt } from '@/components/ui';
import { PaymentChips } from '@/features/ride/components';
import { loadSavedPayment, rideDraft, setDraftPayment } from '@/features/ride/store';
import { useSavedPlaces } from '@/hooks/useAccount';
import { useAppConfig } from '@/hooks/useDriver';
import { DEFAULT_PAYMENT_METHODS, shortAddress } from '@/lib/ride';
import { useStore } from '@/lib/store';
import type { PassengerStats } from '@/lib/types';
import { radius, space } from '@/theme';

import { Section } from './components';
import { rideTo, SavedPlacesCard } from './SavedPlaces';

/** Within ~150 m: a frequent place that is already saved is not listed twice. */
const near = (a: { lat: number; lng: number }, b: { lat: number; lng: number }) => Math.abs(a.lat - b.lat) < 0.0015 && Math.abs(a.lng - b.lng) < 0.0015;

export function PassengerProfile({ stats, loading }: { stats: PassengerStats | null | undefined; loading: boolean }) {
  const { t } = useTranslation();
  const { config } = useAppConfig();
  const draft = useStore(rideDraft);
  const methods = config.payment_methods?.length ? config.payment_methods : DEFAULT_PAYMENT_METHODS;

  useEffect(() => {
    void loadSavedPayment();
  }, []);

  const saved = useSavedPlaces().data ?? [];
  const places = (stats?.frequent_places ?? []).filter((place) => !saved.some((s) => near(s, place)));

  return (
    <>
      <Section title={t('profile.saved.title')}>
        <SavedPlacesCard />
      </Section>

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
