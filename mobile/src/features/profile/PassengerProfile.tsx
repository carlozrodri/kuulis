import { router } from 'expo-router';
import { useEffect } from 'react';
import { useTranslation } from 'react-i18next';

import { History, MapPinned, Wallet } from '@/components/icons';
import { Card, ListRow } from '@/components/ui';
import { loadSavedPayment, rideDraft } from '@/features/ride/store';
import { useStore } from '@/lib/store';
import type { PassengerStats } from '@/lib/types';
import { space } from '@/theme';

import { Section } from './components';
import { SavedPlacesCard } from './SavedPlaces';

/** Passenger side of the profile: saved places up front; history, frequent places and payment one tap away. */
export function PassengerProfile({ stats }: { stats: PassengerStats | null | undefined; loading: boolean }) {
  const { t } = useTranslation();
  const draft = useStore(rideDraft);
  const frequent = stats?.frequent_places?.length ?? 0;

  useEffect(() => {
    void loadSavedPayment();
  }, []);

  return (
    <>
      <Section title={t('profile.saved.title')}>
        <SavedPlacesCard />
      </Section>

      <Section title={t('profile.activity')}>
        <Card style={{ paddingVertical: space.xxs }}>
          <ListRow
            icon={History}
            title={t('profile.history')}
            subtitle={stats ? t('stats.total', { count: stats.rides }) : t('profile.historyHint')}
            divider
            onPress={() => router.push('/rides')}
          />
          <ListRow
            icon={MapPinned}
            iconTone="accent"
            title={t('profile.places.title')}
            subtitle={frequent ? t('profile.menu.frequentCount', { count: frequent }) : t('profile.places.empty')}
            divider
            onPress={() => router.push('/profile/frequent')}
          />
          <ListRow
            icon={Wallet}
            title={t('profile.payment.title')}
            subtitle={draft.paymentMethod ? t(`payment.${draft.paymentMethod}`) : t('profile.menu.paymentHint')}
            onPress={() => router.push('/profile/payment')}
          />
        </Card>
      </Section>
    </>
  );
}
