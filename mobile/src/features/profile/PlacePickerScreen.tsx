import { router, useLocalSearchParams } from 'expo-router';
import { useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { ActivityIndicator, FlatList, View } from 'react-native';

import { Briefcase, ChevronLeft, House, LocateFixed, MapPin, Search, SearchX, Star } from '@/components/icons';
import { showToast } from '@/components/Toast';
import { Field, IconButton, IconTile, ListRow, Row, Screen, Txt } from '@/components/ui';
import { useSavedPlaces, useSavePlace } from '@/hooks/useAccount';
import { useUserLocation } from '@/hooks/useLocation';
import { reverseGeocode, useGeoSearch } from '@/hooks/useRides';
import { apiErrorMessage } from '@/i18n';
import { placeFromGeo } from '@/lib/ride';
import type { GeoResult, PlaceKind } from '@/lib/types';
import { space, useTheme } from '@/theme';

export const PLACE_ICONS = { home: House, work: Briefcase, other: Star } as const;

const back = () => (router.canGoBack() ? router.back() : router.replace('/profile'));

/** Save or change Casa, Trabajo or another place: search an address (or use the current location). */
export function PlacePickerScreen() {
  const { t } = useTranslation();
  const theme = useTheme();
  const params = useLocalSearchParams<{ kind?: PlaceKind; id?: string }>();
  const kind: PlaceKind = params.kind === 'home' || params.kind === 'work' ? params.kind : 'other';
  const places = useSavedPlaces();
  const editing = places.data?.find((p) => p.id === params.id);
  const save = useSavePlace();
  const { position, permission } = useUserLocation();

  // Null until typed, so the label of a place loaded after mount still shows.
  const [typedLabel, setLabel] = useState<string | null>(null);
  const label = typedLabel ?? editing?.label ?? '';
  const [query, setQuery] = useState('');
  const [debounced, setDebounced] = useState('');
  const [locating, setLocating] = useState(false);
  useEffect(() => {
    const timer = setTimeout(() => setDebounced(query), 350);
    return () => clearTimeout(timer);
  }, [query]);

  const search = useGeoSearch(debounced, position ? { lat: position.lat, lng: position.lng } : null);
  const searching = query.trim().length >= 3;
  const results = searching ? (search.data ?? []) : [];

  async function choose(result: GeoResult) {
    const place = placeFromGeo(result);
    try {
      await save.mutateAsync({ id: editing?.id, kind, label: label.trim(), ...place });
      showToast(t('profile.saved.savedToast', { name: kind === 'other' ? label.trim() || place.address : t(`profile.saved.${kind}`) }), 'success');
      back();
    } catch (error) {
      showToast(apiErrorMessage(error), 'danger');
    }
  }

  async function saveCurrentLocation() {
    if (!position) return;
    setLocating(true);
    try {
      await choose(await reverseGeocode(position.lat, position.lng));
    } catch (error) {
      showToast(apiErrorMessage(error), 'danger');
    } finally {
      setLocating(false);
    }
  }

  const title = kind === 'other' ? (editing ? t('profile.saved.editOther') : t('profile.saved.addOther')) : t(`profile.saved.set_${kind}`);

  return (
    <Screen
      scroll={false}
      header={
        <View style={{ gap: space.md, paddingTop: space.xs, paddingBottom: space.sm }}>
          <Row>
            <IconButton icon={ChevronLeft} label={t('common.back')} onPress={back} />
            <IconTile icon={PLACE_ICONS[kind]} tone="accent" size={40} />
            <Txt variant="subtitle" accessibilityRole="header" style={{ flex: 1 }} numberOfLines={1}>
              {title}
            </Txt>
            {save.isPending || locating ? <ActivityIndicator color={theme.primary} /> : null}
          </Row>
          {kind === 'other' ? (
            <Field label={t('profile.saved.label')} value={label} onChangeText={setLabel} maxLength={40} placeholder={t('profile.saved.labelPlaceholder')} />
          ) : null}
          <Field
            label={t('profile.saved.address')}
            icon={Search}
            value={query}
            onChangeText={setQuery}
            placeholder={editing?.address ?? t('profile.saved.searchPlaceholder')}
            autoFocus={kind !== 'other'}
            autoCorrect={false}
            returnKeyType="search"
          />
        </View>
      }>
      <FlatList
        data={results}
        keyExtractor={(item, index) => `${item.lat},${item.lng},${index}`}
        keyboardShouldPersistTaps="handled"
        keyboardDismissMode="on-drag"
        ListHeaderComponent={
          permission === 'granted' && position ? (
            <ListRow
              icon={LocateFixed}
              title={t('profile.saved.useCurrent')}
              subtitle={t('profile.saved.useCurrentHint')}
              onPress={() => void saveCurrentLocation()}
              chevron={false}
              divider={results.length > 0}
            />
          ) : null
        }
        ListEmptyComponent={
          searching && !search.isFetching && debounced === query ? (
            <View style={{ alignItems: 'center', gap: space.sm, paddingVertical: space.xxl }}>
              <SearchX size={28} color={theme.muted} />
              <Txt color="muted" align="center">
                {search.isError ? apiErrorMessage(search.error) : t('search.noResults')}
              </Txt>
            </View>
          ) : !searching ? (
            <Txt variant="caption" color="muted" align="center" style={{ marginTop: space.lg }}>
              {t('search.hint')}
            </Txt>
          ) : null
        }
        renderItem={({ item, index }) => (
          <ListRow
            icon={MapPin}
            iconTone="neutral"
            title={item.name || item.address}
            subtitle={item.address}
            onPress={() => void choose(item)}
            chevron={false}
            divider={index < results.length - 1}
          />
        )}
      />
    </Screen>
  );
}
