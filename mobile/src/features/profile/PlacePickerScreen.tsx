import { router, useLocalSearchParams } from 'expo-router';
import { useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { ActivityIndicator, FlatList, Pressable, StyleSheet, View } from 'react-native';

import {
  Briefcase,
  Check,
  ChevronLeft,
  Dumbbell,
  Heart,
  Hospital,
  House,
  LocateFixed,
  MapPin,
  MapPinned,
  School,
  Search,
  SearchX,
  Star,
  Store,
  Users,
  Utensils,
} from '@/components/icons';
import { showToast } from '@/components/Toast';
import { Button, Card, Field, IconButton, IconTile, ListRow, Row, Screen, Txt } from '@/components/ui';
import { useSavedPlaces, useSavePlace } from '@/hooks/useAccount';
import { useUserLocation } from '@/hooks/useLocation';
import { reverseGeocode, useGeoSearch } from '@/hooks/useRides';
import { apiErrorMessage } from '@/i18n';
import { placeFromGeo, shortAddress } from '@/lib/ride';
import { pinnedPlace } from '@/features/ride/store';
import { useStore } from '@/lib/store';
import type { GeoResult, Place, PlaceIcon, PlaceKind, SavedPlace } from '@/lib/types';
import { radius, space, useTheme } from '@/theme';

export const PLACE_ICONS = { home: House, work: Briefcase, other: Star } as const;

/** Doc 23: icons an "other" place can have (the API keeps the key). */
export const OTHER_ICONS = {
  star: Star,
  heart: Heart,
  dumbbell: Dumbbell,
  school: School,
  store: Store,
  users: Users,
  utensils: Utensils,
  hospital: Hospital,
} as const satisfies Record<PlaceIcon, unknown>;

/** The icon of a saved place: home, work, or the one chosen for an "other" place. */
export function placeIcon(place: Pick<SavedPlace, 'kind' | 'icon'>) {
  return place.kind === 'other' ? OTHER_ICONS[place.icon ?? 'star'] ?? Star : PLACE_ICONS[place.kind];
}

const back = () => (router.canGoBack() ? router.back() : router.replace('/profile'));

/** Save or change Casa, Trabajo or another place: search an address (or use the current location). */
export function PlacePickerScreen() {
  const { t } = useTranslation();
  const theme = useTheme();
  // `lat`, `lng` and `address` (doc 23): save a place from a ride in the history.
  const params = useLocalSearchParams<{ kind?: PlaceKind; id?: string; lat?: string; lng?: string; address?: string }>();
  const kind: PlaceKind = params.kind === 'home' || params.kind === 'work' ? params.kind : 'other';
  const places = useSavedPlaces();
  const editing = places.data?.find((p) => p.id === params.id);
  const save = useSavePlace();
  const { position, permission } = useUserLocation();

  // Null until typed, so the label of a place loaded after mount still shows.
  const [typedLabel, setLabel] = useState<string | null>(null);
  const label = typedLabel ?? editing?.label ?? '';
  const [pickedIcon, setIcon] = useState<PlaceIcon | null>(null);
  const icon: PlaceIcon = pickedIcon ?? editing?.icon ?? 'star';
  const pinned = useStore(pinnedPlace);
  const given = params.address && params.lat && params.lng ? { address: params.address, lat: Number(params.lat), lng: Number(params.lng) } : null;
  const ready = pinned ?? (given && Number.isFinite(given.lat) && Number.isFinite(given.lng) ? given : null);
  useEffect(() => () => pinnedPlace.set(null), []);
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
    await saveAt(placeFromGeo(result));
  }

  async function saveAt(place: Place) {
    try {
      await save.mutateAsync({ id: editing?.id, kind, label: label.trim(), ...(kind === 'other' ? { icon } : {}), ...place });
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

  const HeaderIcon = kind === 'other' ? OTHER_ICONS[icon] : PLACE_ICONS[kind];
  const title = kind === 'other' ? (editing ? t('profile.saved.editOther') : t('profile.saved.addOther')) : t(`profile.saved.set_${kind}`);

  return (
    <Screen
      scroll={false}
      header={
        <View style={{ gap: space.md, paddingTop: space.xs, paddingBottom: space.sm }}>
          <Row>
            <IconButton icon={ChevronLeft} label={t('common.back')} onPress={back} />
            <IconTile icon={HeaderIcon} tone="accent" size={40} />
            <Txt variant="subtitle" accessibilityRole="header" style={{ flex: 1 }} numberOfLines={1}>
              {title}
            </Txt>
            {save.isPending || locating ? <ActivityIndicator color={theme.primary} /> : null}
          </Row>
          {kind === 'other' ? (
            <>
              <Field label={t('profile.saved.label')} value={label} onChangeText={setLabel} maxLength={40} placeholder={t('profile.saved.labelPlaceholder')} />
              <IconChoice value={icon} onChange={setIcon} />
            </>
          ) : null}
          {ready ? (
            <Card tone="tint" style={{ gap: space.sm }}>
              <Row>
                <MapPin size={20} color={theme.primary} />
                <View style={{ flex: 1 }}>
                  <Txt variant="bodyStrong" numberOfLines={1}>
                    {shortAddress(ready.address)}
                  </Txt>
                  <Txt variant="caption" color="muted" numberOfLines={2}>
                    {ready.address}
                  </Txt>
                </View>
              </Row>
              <Button title={t('profile.saved.saveHere')} size="sm" loading={save.isPending} onPress={() => void saveAt(ready)} />
            </Card>
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
          <View>
            {permission === 'granted' && position ? (
              <ListRow
                icon={LocateFixed}
                title={t('profile.saved.useCurrent')}
                subtitle={t('profile.saved.useCurrentHint')}
                onPress={() => void saveCurrentLocation()}
                chevron={false}
                divider
              />
            ) : null}
            <ListRow
              icon={MapPinned}
              iconTone="accent"
              title={t('search.pinOnMap')}
              subtitle={t('profile.saved.pinHint')}
              onPress={() => router.push({ pathname: '/ride/pin', params: { save: '1' } })}
              chevron={false}
              divider={results.length > 0}
            />
          </View>
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
          ) : undefined
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

/** Doc 23: the icon of an "other" place, as a row of round buttons. */
function IconChoice({ value, onChange }: { value: PlaceIcon; onChange: (icon: PlaceIcon) => void }) {
  const { t } = useTranslation();
  const theme = useTheme();
  return (
    <View style={{ gap: 6 }}>
      <Txt variant="label" color="muted">
        {t('profile.saved.icon')}
      </Txt>
      <View style={styles.icons} accessibilityRole="radiogroup">
        {(Object.keys(OTHER_ICONS) as PlaceIcon[]).map((key) => {
          const Glyph = OTHER_ICONS[key];
          const selected = key === value;
          return (
            <Pressable
              key={key}
              accessibilityRole="radio"
              accessibilityState={{ selected }}
              accessibilityLabel={t(`profile.saved.icons.${key}`)}
              onPress={() => onChange(key)}
              style={({ pressed }) => [
                styles.icon,
                {
                  backgroundColor: selected ? theme.accentSoft : theme.surface,
                  borderColor: selected ? theme.primary : theme.border,
                  opacity: pressed ? 0.7 : 1,
                },
              ]}>
              <Glyph size={20} color={selected ? theme.onAccentSoft : theme.text} strokeWidth={2.2} />
              {selected ? (
                <View style={[styles.check, { backgroundColor: theme.primary }]}>
                  <Check size={10} color={theme.onPrimary} strokeWidth={3} />
                </View>
              ) : null}
            </Pressable>
          );
        })}
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  icons: { flexDirection: 'row', flexWrap: 'wrap', gap: space.xs },
  icon: { width: 44, height: 44, borderRadius: radius.pill, borderWidth: 1.5, alignItems: 'center', justifyContent: 'center' },
  check: { position: 'absolute', right: -2, top: -2, width: 16, height: 16, borderRadius: 8, alignItems: 'center', justifyContent: 'center' },
});
