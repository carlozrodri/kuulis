import { useEffect, useMemo, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Pressable, StyleSheet, View } from 'react-native';

import { Flame } from '@/components/icons';
import type { MapArea } from '@/components/map/RideMap.types';
import { MIN_TOUCH, Txt } from '@/components/ui';
import { demandFocusRequest, useDemand, useDemandLayer } from '@/hooks/useDemand';
import { selectionHaptic } from '@/lib/feedback';
import { formatDistance } from '@/lib/ride';
import { useStore } from '@/lib/store';
import type { LatLng } from '@/lib/types';
import { DEMAND_LEVELS, type DemandLevel, demandAreas, demandColors, demandHotSpot } from '@/lib/zones';
import { elevation, radius, space, useTheme } from '@/theme';

/**
 * Doc 21: everything the driver home needs for the "Demanda" layer: the polygons for the map, the nearest
 * hot spot and the camera target when the driver asks to see it (or opened a demand push).
 */
export function useDemandMap(position: LatLng | null | undefined) {
  const theme = useTheme();
  const [on, setOn] = useDemandLayer();
  const demand = useDemand(position, on);
  const [focus, setFocus] = useState<{ point: LatLng; key: number } | null>(null);

  const areas = useMemo<MapArea[]>(
    () =>
      on
        ? demandAreas(demand.data).map((area) => ({ id: area.id, coordinates: area.coordinates, ...demandColors(area.level, theme) }))
        : [],
    [on, demand.data, theme],
  );
  const hot = on ? demandHotSpot(demand.data) : null;

  // A demand push was tapped (the opener already turned the layer on): show that point once.
  const request = useStore(demandFocusRequest);
  const [seen, setSeen] = useState<number | null>(null);
  if (request && request.at !== seen) {
    setSeen(request.at);
    setFocus({ point: { lat: request.lat, lng: request.lng }, key: request.at });
  }
  useEffect(() => {
    if (request) demandFocusRequest.set(null);
  }, [request]);

  return {
    on,
    setOn,
    /** Known to be on (cells and legend can show). */
    enabled: demand.enabled === true,
    /** Show the switch: demand is on, or the driver left the layer on (then off by the admin: shown disabled). */
    showToggle: demand.enabled === true || on,
    /** False only when the server said demand is switched off. */
    available: demand.enabled !== false,
    areas,
    hot,
    focus,
    showOnMap: (point: LatLng) => setFocus({ point, key: Date.now() }),
  };
}

/** "Demanda" on/off chip over the map. Disabled (and explained) when demand is switched off. */
export function DemandToggle({ on, onChange, available }: { on: boolean; onChange: (on: boolean) => void; available: boolean }) {
  const { t } = useTranslation();
  const theme = useTheme();
  const active = on && available;
  const fg = !available ? theme.onDisabled : active ? theme.onPrimary : theme.text;
  return (
    <Pressable
      accessibilityRole="switch"
      accessibilityLabel={t('demand.layer')}
      accessibilityHint={available ? t('demand.layerHint') : t('demand.unavailable')}
      accessibilityState={{ checked: active, disabled: !available }}
      disabled={!available}
      onPress={() => {
        selectionHaptic();
        onChange(!on);
      }}
      style={({ pressed }) => [
        styles.toggle,
        { backgroundColor: !available ? theme.disabled : active ? theme.primary : theme.surface, opacity: pressed ? 0.8 : 1 },
        elevation(theme),
      ]}>
      <Flame size={18} color={fg} strokeWidth={2.4} />
      <Txt variant="bodyStrong" style={{ color: fg }}>
        {t('demand.layer')}
      </Txt>
    </Pressable>
  );
}

/** The three levels, from "algo" to "mucha" demand. */
export function DemandLegend() {
  const { t } = useTranslation();
  const theme = useTheme();
  return (
    <View
      accessible
      accessibilityLabel={`${t('demand.legendTitle')}: ${DEMAND_LEVELS.map((level) => t(`demand.level.${level}`)).join(', ')}`}
      style={[styles.legend, { backgroundColor: theme.surface }, elevation(theme)]}>
      {DEMAND_LEVELS.map((level: DemandLevel) => {
        const colors = demandColors(level, theme);
        return (
          <View key={level} style={styles.legendItem}>
            <View style={[styles.swatch, { backgroundColor: colors.fill, borderColor: colors.stroke }]} />
            <Txt variant="caption" style={{ color: theme.text }} numberOfLines={1}>
              {t(`demand.level.${level}`)}
            </Txt>
          </View>
        );
      })}
    </View>
  );
}

/** "Mucha demanda en Chacao · a 1,2 km": tapping it centres the map there. */
export function DemandBanner({ name, distance, onPress }: { name: string; distance: number; onPress: () => void }) {
  const { t, i18n } = useTranslation();
  const theme = useTheme();
  const title = t('demand.hot', { name });
  const away = t('demand.away', { distance: formatDistance(distance, i18n.language) });
  return (
    <Pressable
      accessibilityRole="button"
      accessibilityLabel={`${title}, ${away}`}
      accessibilityHint={t('demand.showOnMap')}
      onPress={onPress}
      style={({ pressed }) => [styles.banner, { backgroundColor: theme.dangerSoft, opacity: pressed ? 0.75 : 1 }]}>
      <Flame size={22} color={theme.danger} strokeWidth={2.2} />
      <View style={{ flex: 1, gap: 1 }}>
        <Txt variant="bodyStrong" style={{ color: theme.danger }} numberOfLines={2}>
          {title}
        </Txt>
        <Txt variant="caption" style={{ color: theme.text }}>
          {away}
        </Txt>
      </View>
      <Txt variant="label" style={{ color: theme.danger }}>
        {t('demand.see')}
      </Txt>
    </Pressable>
  );
}

const styles = StyleSheet.create({
  toggle: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: space.xs,
    minHeight: MIN_TOUCH,
    borderRadius: radius.pill,
    paddingHorizontal: space.md,
  },
  legend: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    alignSelf: 'flex-end',
    gap: space.sm,
    borderRadius: radius.pill,
    paddingHorizontal: space.md,
    paddingVertical: space.xs,
  },
  legendItem: { flexDirection: 'row', alignItems: 'center', gap: 6 },
  swatch: { width: 14, height: 14, borderRadius: 4, borderWidth: 1.5 },
  banner: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: space.sm,
    minHeight: MIN_TOUCH,
    borderRadius: radius.tile,
    paddingHorizontal: 14,
    paddingVertical: space.sm,
  },
});
