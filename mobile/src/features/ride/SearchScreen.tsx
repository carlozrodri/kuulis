import { router, useLocalSearchParams } from 'expo-router';
import { useEffect, useRef, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { ActivityIndicator, FlatList, Pressable, StyleSheet, TextInput, View } from 'react-native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';

import { ArrowUpDown, ChevronLeft, LocateFixed, MapPin, MapPinned, SearchX, X } from '@/components/icons';
import { IconButton, ListRow, Txt } from '@/components/ui';
import { useUserLocation } from '@/hooks/useLocation';
import { useGeoSearch } from '@/hooks/useRides';
import { apiErrorMessage } from '@/i18n';
import { placeFromGeo, shortAddress } from '@/lib/ride';
import { useStore } from '@/lib/store';
import type { GeoResult } from '@/lib/types';
import { elevation, fonts, radius, space, useTheme } from '@/theme';

import { type DraftField, rideDraft, setDraftPlace } from './store';
import { useCurrentPickup } from './useCurrentPickup';

/** Destination search (GET /geo/search, debounced) with an editable pickup and pin-on-map. */
export function SearchScreen() {
  const { t } = useTranslation();
  const theme = useTheme();
  const insets = useSafeAreaInsets();
  const params = useLocalSearchParams<{ field?: DraftField }>();
  const draft = useStore(rideDraft);
  const { position, permission } = useUserLocation();
  useCurrentPickup();

  const [field, setField] = useState<DraftField>(params.field === 'pickup' ? 'pickup' : 'dropoff');
  const [texts, setTexts] = useState<Record<DraftField, string>>({ pickup: '', dropoff: '' });
  const [debounced, setDebounced] = useState('');
  const inputs = { pickup: useRef<TextInput>(null), dropoff: useRef<TextInput>(null) };
  const query = texts[field];

  useEffect(() => {
    const timer = setTimeout(() => setDebounced(query), 350);
    return () => clearTimeout(timer);
  }, [query]);

  const near = position ?? draft.pickup;
  const search = useGeoSearch(debounced, near ? { lat: near.lat, lng: near.lng } : null);
  const searching = query.trim().length >= 3;
  const results = searching ? (search.data ?? []) : [];

  const proceed = (nextDraft = rideDraft.get()) => {
    if (nextDraft.pickup && nextDraft.dropoff) router.replace('/ride/quote');
  };

  const choose = (result: GeoResult) => {
    setDraftPlace(field, placeFromGeo(result));
    setTexts((prev) => ({ ...prev, [field]: '' }));
    const next = rideDraft.get();
    if (field === 'pickup' && !next.dropoff) {
      setField('dropoff');
      inputs.dropoff.current?.focus();
    } else proceed(next);
  };

  const pickMyLocation = () => {
    rideDraft.set((d) => ({ ...d, pickupIsCurrent: true, pickup: position ? { lat: position.lat, lng: position.lng, address: t('ride.currentLocation') } : d.pickup }));
    setTexts((prev) => ({ ...prev, pickup: '' }));
    setField('dropoff');
    inputs.dropoff.current?.focus();
  };

  const swap = () => {
    if (!draft.pickup || !draft.dropoff) return;
    rideDraft.set((d) => ({ ...d, pickup: d.dropoff, dropoff: d.pickup, pickupIsCurrent: false }));
  };

  const input = (kind: DraftField) => {
    const place = draft[kind];
    const placeholder =
      kind === 'pickup'
        ? draft.pickupIsCurrent
          ? t('search.currentLocation', { address: place ? shortAddress(place.address) : '…' })
          : place
            ? shortAddress(place.address)
            : t('search.pickupPlaceholder')
        : place
          ? shortAddress(place.address)
          : t('home.whereTo');
    const focused = field === kind;
    return (
      <View style={[styles.inputRow, { backgroundColor: focused ? theme.surface : theme.background, borderColor: focused ? theme.primary : 'transparent' }]}>
        {kind === 'pickup' ? (
          <View style={[styles.dot, { backgroundColor: theme.primary, borderColor: theme.surfaceAlt }]} />
        ) : (
          <View style={[styles.square, { backgroundColor: theme.accent, borderColor: theme.nav }]} />
        )}
        <TextInput
          ref={inputs[kind]}
          value={texts[kind]}
          onChangeText={(text) => setTexts((prev) => ({ ...prev, [kind]: text }))}
          onFocus={() => setField(kind)}
          placeholder={placeholder}
          placeholderTextColor={place && kind === 'dropoff' ? theme.text : theme.muted}
          accessibilityLabel={kind === 'pickup' ? t('ride.pickup') : t('ride.dropoff')}
          autoFocus={kind === field}
          autoCorrect={false}
          returnKeyType="search"
          selectionColor={theme.primary}
          cursorColor={theme.primary}
          maxFontSizeMultiplier={1.5}
          style={[styles.input, { color: theme.text }]}
        />
        {focused && searching && search.isFetching ? <ActivityIndicator size="small" color={theme.primary} /> : null}
        {focused && texts[kind] ? (
          <Pressable accessibilityRole="button" accessibilityLabel={t('search.clear')} hitSlop={10} onPress={() => setTexts((prev) => ({ ...prev, [kind]: '' }))}>
            <X size={18} color={theme.muted} />
          </Pressable>
        ) : null}
      </View>
    );
  };

  return (
    <View style={{ flex: 1, backgroundColor: theme.background, paddingTop: insets.top }}>
      <View style={styles.header}>
        <IconButton icon={ChevronLeft} label={t('common.back')} onPress={() => router.back()} />
        <Txt variant="subtitle" accessibilityRole="header">
          {t('search.title')}
        </Txt>
      </View>

      <View style={[styles.card, { backgroundColor: theme.surface }, elevation(theme)]}>
        <View style={{ flex: 1, gap: space.xs }}>
          {input('pickup')}
          {input('dropoff')}
        </View>
        <IconButton icon={ArrowUpDown} label={t('search.swap')} tone="plain" onPress={swap} />
      </View>

      <FlatList
        data={results}
        keyExtractor={(item, index) => `${item.lat},${item.lng},${index}`}
        keyboardShouldPersistTaps="handled"
        keyboardDismissMode="on-drag"
        contentContainerStyle={{ paddingHorizontal: space.lg, paddingBottom: insets.bottom + space.xl }}
        ListHeaderComponent={
          <View>
            {field === 'pickup' && permission === 'granted' && !draft.pickupIsCurrent ? (
              <ListRow icon={LocateFixed} title={t('search.useMyLocation')} onPress={pickMyLocation} chevron={false} divider />
            ) : null}
            <ListRow
              icon={MapPinned}
              iconTone="accent"
              title={t('search.pinOnMap')}
              subtitle={field === 'pickup' ? t('search.pinPickupHint') : t('search.pinDropoffHint')}
              onPress={() => router.push({ pathname: '/ride/pin', params: { field } })}
              chevron={false}
              divider={results.length > 0}
            />
          </View>
        }
        ListEmptyComponent={
          searching && !search.isFetching && debounced === query ? (
            <View style={styles.empty}>
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
            title={item.name || shortAddress(item.address)}
            subtitle={item.address}
            onPress={() => choose(item)}
            chevron={false}
            divider={index < results.length - 1}
          />
        )}
      />
    </View>
  );
}

const styles = StyleSheet.create({
  header: { flexDirection: 'row', alignItems: 'center', gap: space.sm, paddingHorizontal: space.md, paddingVertical: space.sm },
  card: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: space.xs,
    marginHorizontal: space.md,
    marginBottom: space.sm,
    padding: space.sm,
    borderRadius: radius.card,
  },
  inputRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: space.sm,
    minHeight: 52,
    borderRadius: radius.field,
    borderWidth: 1.5,
    paddingHorizontal: space.sm,
  },
  input: { flex: 1, fontFamily: fonts.semibold, fontSize: 16, paddingVertical: 12 },
  dot: { width: 16, height: 16, borderRadius: 8, borderWidth: 4 },
  square: { width: 15, height: 15, borderRadius: 4, borderWidth: 3 },
  empty: { alignItems: 'center', gap: space.sm, paddingVertical: space.xxl },
});
