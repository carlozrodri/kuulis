import { router, useLocalSearchParams } from 'expo-router';
import { useEffect, useRef, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { ActivityIndicator, Animated, StyleSheet, View } from 'react-native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';

import { ChevronLeft } from '@/components/icons';
import { RideMap } from '@/components/map/RideMap';
import { Button, IconButton, Notice, Txt } from '@/components/ui';
import { useAppConfig } from '@/hooks/useDriver';
import { getLastPosition } from '@/hooks/useLocation';
import { reverseGeocode } from '@/hooks/useRides';
import { inServiceArea, placeFromGeo, shortAddress } from '@/lib/ride';
import type { LatLng, Place } from '@/lib/types';
import { radius, space, useTheme } from '@/theme';

import { type DraftField, rideDraft, setDraftPlace } from './store';

/** Move the map under a fixed centre pin to choose the pickup or destination precisely. */
export function PinScreen() {
  const { t } = useTranslation();
  const theme = useTheme();
  const insets = useSafeAreaInsets();
  const { config } = useAppConfig();
  const params = useLocalSearchParams<{ field?: DraftField }>();
  const field: DraftField = params.field === 'pickup' ? 'pickup' : 'dropoff';
  const [initial] = useState<LatLng | null>(() => rideDraft.get()[field] ?? getLastPosition() ?? rideDraft.get().pickup);
  const [center, setCenter] = useState<LatLng | null>(initial);
  const [place, setPlace] = useState<Place | null>(null);
  const [resolved, setResolved] = useState<LatLng | null>(null);
  const [lift] = useState(() => new Animated.Value(0));
  const request = useRef(0);

  useEffect(() => {
    if (!center) return;
    const id = ++request.current;
    const timer = setTimeout(() => {
      reverseGeocode(center.lat, center.lng)
        .then((result) => {
          if (id === request.current) setPlace(placeFromGeo({ ...result, lat: center.lat, lng: center.lng }));
        })
        .catch(() => {
          if (id === request.current) setPlace({ ...center, address: `${center.lat.toFixed(5)}, ${center.lng.toFixed(5)}` });
        })
        .finally(() => {
          if (id === request.current) setResolved(center);
        });
    }, 300);
    return () => clearTimeout(timer);
  }, [center]);

  const loading = !!center && resolved !== center;
  const inside = center ? inServiceArea(center, config.service_area) : true;

  const confirm = () => {
    if (!place) return;
    setDraftPlace(field, place);
    const draft = rideDraft.get();
    if (draft.pickup && draft.dropoff) router.replace('/ride/quote');
    else router.back();
  };

  return (
    <View style={{ flex: 1, backgroundColor: theme.background }}>
      <View style={{ flex: 1 }}>
        <RideMap
          initialCenter={initial}
          showUser
          recenterBottom={radius.sheet + space.sm}
          onDragStart={() => Animated.spring(lift, { toValue: 1, useNativeDriver: true }).start()}
          onCenterChange={(next) => {
            Animated.spring(lift, { toValue: 0, useNativeDriver: true }).start();
            setCenter(next);
          }}>
          <View pointerEvents="none" style={styles.pinWrap}>
            <View style={styles.pinAnchor}>
              <View style={[styles.pinShadow, { backgroundColor: theme.shadow }]} />
              <Animated.View
                style={[styles.pin, { transform: [{ translateY: lift.interpolate({ inputRange: [0, 1], outputRange: [0, -14] }) }] }]}>
                <View style={[styles.pinHead, { backgroundColor: field === 'pickup' ? theme.primary : theme.accent, borderColor: theme.nav }]}>
                  <View style={[styles.pinCore, { backgroundColor: theme.surface }]} />
                </View>
                <View style={[styles.pinStem, { backgroundColor: theme.nav }]} />
              </Animated.View>
            </View>
          </View>
        </RideMap>
        <View style={[styles.back, { top: insets.top + space.sm }]}>
          <IconButton icon={ChevronLeft} label={t('common.back')} onPress={() => router.back()} />
        </View>
      </View>

      <View style={[styles.panel, { backgroundColor: theme.surface, paddingBottom: Math.max(insets.bottom, space.md) + space.xs }]}>
        <Txt variant="overline" color="muted">
          {field === 'pickup' ? t('pin.pickupTitle') : t('pin.dropoffTitle')}
        </Txt>
        <View style={styles.addressRow}>
          <Txt variant="subtitle" numberOfLines={2} style={{ flex: 1 }}>
            {place ? shortAddress(place.address) : t('pin.moveMap')}
          </Txt>
          {loading ? <ActivityIndicator color={theme.primary} /> : null}
        </View>
        {place && shortAddress(place.address) !== place.address ? (
          <Txt variant="caption" color="muted" numberOfLines={2}>
            {place.address}
          </Txt>
        ) : null}
        {!inside ? <Notice tone="warning">{t('errors.outside_service_area')}</Notice> : null}
        <Button
          title={field === 'pickup' ? t('pin.confirmPickup') : t('pin.confirmDropoff')}
          disabled={!place || loading || !inside}
          onPress={confirm}
        />
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  pinWrap: { position: 'absolute', top: 0, left: 0, right: 0, bottom: 0, alignItems: 'center', justifyContent: 'center' },
  // Zero-height anchor at the exact map centre: the stem tip touches it.
  pinAnchor: { width: 40, height: 0 },
  pin: { position: 'absolute', bottom: 0, left: 0, right: 0, alignItems: 'center' },
  pinHead: { width: 34, height: 34, borderRadius: 17, borderWidth: 3, alignItems: 'center', justifyContent: 'center' },
  pinCore: { width: 10, height: 10, borderRadius: 5 },
  pinStem: { width: 3, height: 14, borderRadius: 2 },
  pinShadow: { position: 'absolute', top: -2, left: 15, width: 10, height: 4, borderRadius: 5, opacity: 0.25 },
  back: { position: 'absolute', left: space.md },
  panel: {
    marginTop: -radius.sheet,
    borderTopLeftRadius: radius.sheet,
    borderTopRightRadius: radius.sheet,
    paddingHorizontal: space.lg,
    paddingTop: space.lg,
    gap: space.xs,
  },
  addressRow: { flexDirection: 'row', alignItems: 'center', gap: space.sm, minHeight: 28 },
});
