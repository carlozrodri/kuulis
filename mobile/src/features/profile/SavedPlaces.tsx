import { router } from 'expo-router';
import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { View } from 'react-native';

import { Ellipsis, Pencil, Plus, Trash } from '@/components/icons';
import { showToast } from '@/components/Toast';
import { Card, IconButton, ListRow, Sheet, Skeleton } from '@/components/ui';
import { rideDraft, setDraftPlace } from '@/features/ride/store';
import { useDeletePlace, useSavedPlaces } from '@/hooks/useAccount';
import { apiErrorMessage } from '@/i18n';
import { shortAddress } from '@/lib/ride';
import type { Place, PlaceKind, SavedPlace } from '@/lib/types';
import { radius, space } from '@/theme';

import { PLACE_ICONS, placeIcon } from './PlacePickerScreen';

/** A saved or frequent place: straight to the price (pickup = where the passenger is), or search. */
export function rideTo(place: Place) {
  setDraftPlace('dropoff', { lat: place.lat, lng: place.lng, address: place.address });
  router.push(rideDraft.get().pickup ? '/ride/quote' : '/ride/search');
}

const pick = (kind: PlaceKind, id?: string) => router.push({ pathname: '/profile/place', params: id ? { kind, id } : { kind } });

/** Name shown for a saved place: "Casa", "Trabajo", its label, or the start of the address. */
export function usePlaceName() {
  const { t } = useTranslation();
  return (place: SavedPlace) => (place.kind === 'other' ? place.label || shortAddress(place.address) : t(`profile.saved.${place.kind}`));
}

/** Casa and Trabajo always shown (empty ones invite to add them), then the other saved places. */
export function SavedPlacesCard() {
  const { t } = useTranslation();
  const places = useSavedPlaces();
  const remove = useDeletePlace();
  const name = usePlaceName();
  const [menu, setMenu] = useState<SavedPlace | null>(null);

  if (places.isPending) {
    return (
      <Card style={{ gap: space.xs }}>
        <Skeleton height={44} radius={radius.tile} />
        <Skeleton height={44} radius={radius.tile} />
      </Card>
    );
  }

  const list = places.data ?? [];
  const home = list.find((p) => p.kind === 'home');
  const work = list.find((p) => p.kind === 'work');
  const others = list.filter((p) => p.kind === 'other');

  const row = (place: SavedPlace | undefined, kind: PlaceKind, divider: boolean) =>
    place ? (
      <ListRow
        key={place.id}
        icon={placeIcon(place)}
        iconTone={kind === 'other' ? 'primary' : 'accent'}
        title={name(place)}
        subtitle={shortAddress(place.address)}
        accessibilityHint={t('profile.places.goHint')}
        onPress={() => rideTo(place)}
        chevron={false}
        divider={divider}
        right={<IconButton icon={Ellipsis} label={t('profile.saved.options', { name: name(place) })} tone="plain" size={36} onPress={() => setMenu(place)} />}
      />
    ) : (
      <ListRow
        key={kind}
        icon={PLACE_ICONS[kind]}
        iconTone="neutral"
        title={t(`profile.saved.add_${kind}`)}
        subtitle={t(`profile.saved.add_${kind}Hint`)}
        onPress={() => pick(kind)}
        divider={divider}
      />
    );

  return (
    <Card style={{ paddingVertical: space.xxs }}>
      {row(home, 'home', true)}
      {row(work, 'work', true)}
      {others.map((place) => row(place, 'other', true))}
      <ListRow icon={Plus} iconTone="neutral" title={t('profile.saved.addOther')} onPress={() => pick('other')} chevron={false} />
      <View />
      <Sheet
        visible={menu !== null}
        title={menu ? name(menu) : ''}
        subtitle={menu?.address}
        onClose={() => setMenu(null)}
        options={
          menu
            ? [
                { label: t('profile.saved.change'), icon: Pencil, onPress: () => pick(menu.kind, menu.id) },
                {
                  label: t('profile.saved.remove'),
                  icon: Trash,
                  destructive: true,
                  onPress: () => remove.mutate(menu.id, { onError: (error) => showToast(apiErrorMessage(error), 'danger') }),
                },
              ]
            : []
        }
      />
    </Card>
  );
}
