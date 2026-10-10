import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Platform, StyleSheet, View } from 'react-native';
import MapView, { Marker, Polyline, type Region } from 'react-native-maps';

import { Bike, LocateFixed } from '@/components/icons';
import { IconButton } from '@/components/ui';
import { getLastPosition, useUserLocation } from '@/hooks/useLocation';
import { CARACAS, type Coordinate, toCoordinate } from '@/lib/ride';
import { useTheme } from '@/theme';

import { darkMapStyle, lightMapStyle } from './mapStyle';
import type { RideMapProps } from './RideMap.types';

export type { RideMapProps } from './RideMap.types';

const EDGE = 56;

/** Custom marker views must be redrawn once after mount on Android, then frozen for performance. */
function useTracksViewChanges(...deps: unknown[]) {
  const key = deps.map(String).join('|');
  const [frozen, setFrozen] = useState<string | null>(null);
  useEffect(() => {
    const timer = setTimeout(() => setFrozen(key), 800);
    return () => clearTimeout(timer);
  }, [key]);
  return frozen !== key;
}

/**
 * The brand map: Google Maps with the Verde Ávila style on Android, Apple Maps (light/dark) on iOS.
 * Draws the pickup (green dot), the destination (yellow square), the moto and the route.
 */
export function RideMap({
  pickup,
  dropoff,
  driver,
  route,
  showUser = true,
  insets = { top: 0, bottom: 0 },
  fitKey,
  followUser = false,
  initialCenter,
  onCenterChange,
  onDragStart,
  recenterButton = true,
  recenterBottom,
  children,
}: RideMapProps) {
  const theme = useTheme();
  const { t } = useTranslation();
  const mapRef = useRef<MapView>(null);
  const [ready, setReady] = useState(false);
  const userMoved = useRef(false);
  const followed = useRef(false);
  const { permission, position } = useUserLocation({ watch: showUser || followUser });
  const dark = theme.scheme === 'dark';
  const tracks = useTracksViewChanges(theme.scheme, !!pickup, !!dropoff, !!driver);

  const initialRegion = useMemo<Region>(() => {
    const start = initialCenter ?? pickup ?? getLastPosition();
    const center = start ? toCoordinate(start) : CARACAS;
    return { ...center, latitudeDelta: start ? 0.012 : 0.08, longitudeDelta: start ? 0.012 : 0.08 };
    // Only the first render matters.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const points = useMemo(() => {
    const list: Coordinate[] = [];
    if (pickup) list.push(toCoordinate(pickup));
    if (dropoff) list.push(toCoordinate(dropoff));
    if (driver) list.push(toCoordinate(driver));
    if (route?.length) list.push(...route.filter((_, i) => i % Math.ceil(route.length / 40) === 0));
    return list;
  }, [pickup, dropoff, driver, route]);

  const frame = useCallback(
    (animated = true) => {
      const map = mapRef.current;
      if (!map) return;
      if (points.length >= 2) {
        map.fitToCoordinates(points, { edgePadding: { top: EDGE, bottom: EDGE, left: EDGE, right: EDGE }, animated });
      } else if (points.length === 1) {
        map.animateCamera({ center: points[0], zoom: 16 }, { duration: animated ? 450 : 0 });
      } else {
        const me = getLastPosition();
        if (me) map.animateCamera({ center: toCoordinate(me), zoom: 16 }, { duration: animated ? 450 : 0 });
      }
    },
    [points],
  );

  // Re-frame when the caller says the scene changed (route loaded, status changed, sheet resized).
  useEffect(() => {
    if (!ready || points.length === 0) return;
    userMoved.current = false;
    const timer = setTimeout(() => frame(true), 120);
    return () => clearTimeout(timer);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [ready, fitKey, insets.bottom, insets.top]);

  // Follow the user until they pan the map themselves.
  useEffect(() => {
    if (!ready || !followUser || !position || userMoved.current) return;
    const first = !followed.current;
    followed.current = true;
    mapRef.current?.animateCamera(first ? { center: toCoordinate(position), zoom: 16 } : { center: toCoordinate(position) }, {
      duration: 600,
    });
  }, [ready, followUser, position]);

  const recenter = () => {
    userMoved.current = false;
    if (followUser && position) {
      mapRef.current?.animateCamera({ center: toCoordinate(position), zoom: 16 }, { duration: 450 });
    } else frame(true);
  };

  return (
    <View style={StyleSheet.absoluteFill}>
      <MapView
        ref={mapRef}
        style={StyleSheet.absoluteFill}
        initialRegion={initialRegion}
        customMapStyle={Platform.OS === 'android' ? (dark ? darkMapStyle : lightMapStyle) : undefined}
        userInterfaceStyle={dark ? 'dark' : 'light'}
        // Only once the map is ready: react-native-maps on Android crashes (GoogleMap.setPadding on null) when the
        // padding changes after layout but before Google Maps finished loading, e.g. when the sheet resizes.
        mapPadding={ready ? { top: insets.top, bottom: insets.bottom, left: 0, right: 0 } : undefined}
        showsUserLocation={showUser && permission === 'granted'}
        showsMyLocationButton={false}
        showsCompass={false}
        showsPointsOfInterests={false}
        showsBuildings={false}
        showsTraffic={false}
        showsIndoors={false}
        toolbarEnabled={false}
        pitchEnabled={false}
        moveOnMarkerPress={false}
        loadingEnabled
        loadingBackgroundColor={theme.background}
        loadingIndicatorColor={theme.primary}
        accessibilityElementsHidden
        importantForAccessibility="no-hide-descendants"
        onMapReady={() => setReady(true)}
        onPanDrag={() => {
          if (!userMoved.current) onDragStart?.();
          userMoved.current = true;
        }}
        onRegionChangeComplete={(region) => onCenterChange?.({ lat: region.latitude, lng: region.longitude })}>
        {route && route.length > 1 ? (
          <>
            <Polyline coordinates={route} strokeColor={dark ? '#04140D' : '#0B6A4C'} strokeWidth={9} lineCap="round" lineJoin="round" zIndex={1} />
            <Polyline coordinates={route} strokeColor={theme.primary} strokeWidth={5} lineCap="round" lineJoin="round" zIndex={2} />
          </>
        ) : null}
        {pickup ? (
          <Marker coordinate={toCoordinate(pickup)} anchor={{ x: 0.5, y: 0.5 }} tracksViewChanges={tracks} zIndex={3}>
            <View style={[styles.pickup, { backgroundColor: theme.primary, borderColor: theme.surface }]} />
          </Marker>
        ) : null}
        {dropoff ? (
          <Marker coordinate={toCoordinate(dropoff)} anchor={{ x: 0.5, y: 0.5 }} tracksViewChanges={tracks} zIndex={3}>
            <View style={[styles.dropoff, { backgroundColor: theme.accent, borderColor: theme.nav }]} />
          </Marker>
        ) : null}
        {driver ? (
          <Marker coordinate={toCoordinate(driver)} anchor={{ x: 0.5, y: 0.5 }} tracksViewChanges={tracks} zIndex={4}>
            <View style={[styles.moto, { backgroundColor: theme.nav, borderColor: theme.primary }]}>
              <Bike size={20} color="#FFFFFF" strokeWidth={2.2} />
            </View>
          </Marker>
        ) : null}
      </MapView>
      {children}
      {recenterButton ? (
        <View pointerEvents="box-none" style={[styles.recenter, { bottom: recenterBottom ?? insets.bottom + 12 }]}>
          <IconButton icon={LocateFixed} label={t('map.recenter')} onPress={recenter} />
        </View>
      ) : null}
    </View>
  );
}

const styles = StyleSheet.create({
  pickup: { width: 22, height: 22, borderRadius: 11, borderWidth: 5 },
  dropoff: { width: 20, height: 20, borderRadius: 6, borderWidth: 4 },
  moto: {
    width: 40,
    height: 40,
    borderRadius: 20,
    borderWidth: 3,
    alignItems: 'center',
    justifyContent: 'center',
  },
  recenter: { position: 'absolute', right: 16 },
});
