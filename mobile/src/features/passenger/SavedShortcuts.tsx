import { router } from 'expo-router';
import { useTranslation } from 'react-i18next';
import { Pressable, ScrollView, StyleSheet, View } from 'react-native';

import { type Icon, Plus } from '@/components/icons';
import { Txt } from '@/components/ui';
import { PLACE_ICONS, placeIcon } from '@/features/profile/PlacePickerScreen';
import { rideTo, usePlaceName } from '@/features/profile/SavedPlaces';
import { useSavedPlaces } from '@/hooks/useAccount';
import { selectionHaptic } from '@/lib/feedback';
import type { PlaceKind, SavedPlace } from '@/lib/types';
import { radius, space, useTheme } from '@/theme';

/**
 * Doc 23: Casa, Trabajo and the other saved places as one-tap shortcuts under "¿A dónde vamos?". A tap goes
 * straight to the price from where the passenger is (then "Pedir" confirms). Casa and Trabajo not saved yet
 * show as "Agregar casa/trabajo".
 */
export function SavedShortcuts() {
  const { t } = useTranslation();
  const places = useSavedPlaces();
  const name = usePlaceName();
  if (places.isPending) return null;
  const list = places.data ?? [];
  const missing = (['home', 'work'] as PlaceKind[]).filter((kind) => !list.some((p) => p.kind === kind));

  const go = (place: SavedPlace) => {
    selectionHaptic();
    rideTo(place);
  };

  return (
    <ScrollView
      horizontal
      showsHorizontalScrollIndicator={false}
      contentContainerStyle={styles.row}
      accessibilityLabel={t('home.shortcuts')}>
      {list.map((place) => (
        <Shortcut
          key={place.id}
          icon={placeIcon(place)}
          label={name(place)}
          hint={t('home.shortcutHint', { name: name(place) })}
          onPress={() => go(place)}
        />
      ))}
      {missing.map((kind) => (
        <Shortcut
          key={kind}
          icon={PLACE_ICONS[kind]}
          label={t(`profile.saved.add_${kind}`)}
          muted
          onPress={() => router.push({ pathname: '/profile/place', params: { kind } })}
        />
      ))}
      {list.length > 0 && missing.length === 0 ? (
        <Shortcut icon={Plus} label={t('home.addPlace')} muted onPress={() => router.push({ pathname: '/profile/place', params: { kind: 'other' } })} />
      ) : null}
    </ScrollView>
  );
}

function Shortcut({ icon: Glyph, label, hint, muted, onPress }: { icon: Icon; label: string; hint?: string; muted?: boolean; onPress: () => void }) {
  const theme = useTheme();
  return (
    <Pressable
      accessibilityRole="button"
      accessibilityLabel={label}
      accessibilityHint={hint}
      onPress={onPress}
      style={({ pressed }) => [
        styles.pill,
        { backgroundColor: muted ? theme.background : theme.surfaceAlt, borderColor: muted ? theme.border : 'transparent', opacity: pressed ? 0.75 : 1 },
      ]}>
      <View style={[styles.icon, { backgroundColor: muted ? theme.surface : theme.accentSoft }]}>
        <Glyph size={16} color={muted ? theme.muted : theme.onAccentSoft} strokeWidth={2.4} />
      </View>
      <Txt variant="label" style={{ color: muted ? theme.muted : theme.text }} numberOfLines={1}>
        {label}
      </Txt>
    </Pressable>
  );
}

const styles = StyleSheet.create({
  row: { gap: space.xs, paddingVertical: 2 },
  pill: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: space.xs,
    minHeight: 44,
    maxWidth: 200,
    borderRadius: radius.pill,
    borderWidth: 1,
    paddingLeft: 6,
    paddingRight: space.md,
  },
  icon: { width: 30, height: 30, borderRadius: 15, alignItems: 'center', justifyContent: 'center' },
});
