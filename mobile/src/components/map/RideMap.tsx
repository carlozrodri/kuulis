import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Image, Platform, StyleSheet, View } from 'react-native';
import MapView, { Circle, Marker, Polygon, Polyline, type Region } from 'react-native-maps';
import { useReducedMotion } from 'react-native-reanimated';

import { LocateFixed } from '@/components/icons';
import { IconButton } from '@/components/ui';
import { getLastPosition, useUserLocation } from '@/hooks/useLocation';
import { CARACAS, type Coordinate, toCoordinate } from '@/lib/ride';
import type { DriverLocation } from '@/lib/types';
import { useTheme } from '@/theme';

import { distanceM, lerpAngle, lerpCoordinate, MAX_GLIDE_M, nextRotation } from './glide';
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

const MOTO_TOP = require('../../../assets/illustrations/moto-kuulis-top.png');
/** About 30 frames per second is smooth for a marker and keeps the JS thread free. */
const FRAME_MS = 33;

/**
 * The moto on the map. Between two GPS updates it glides from where it is to the new point over roughly
 * the time the update took to arrive, and turns the shortest way. Only this marker re-renders while it
 * moves, not the map. With "Reduce motion" it jumps, as before.
 */
function DriverMarker({
  driver,
  size = 46,
  zIndex = 4,
  onPress,
}: {
  driver: DriverLocation;
  size?: number;
  zIndex?: number;
  onPress?: () => void;
}) {
  const reduce = useReducedMotion();
  const target = toCoordinate(driver);
  const [shown, setShown] = useState({ point: target, rotation: driver.heading ?? 0 });
  const current = useRef(shown);
  const lastUpdate = useRef(0);
  const tracks = useTracksViewChanges();

  useEffect(() => {
    const from = current.current;
    const now = Date.now();
    const gap = lastUpdate.current ? now - lastUpdate.current : 1500;
    lastUpdate.current = now;
    const rotation = nextRotation(from.point, target, driver.heading, from.rotation);
    const apply = (next: typeof from) => {
      current.current = next;
      setShown(next);
    };
    if (reduce || distanceM(from.point, target) > MAX_GLIDE_M) {
      apply({ point: target, rotation });
      return;
    }
    const duration = Math.min(4500, Math.max(600, gap));
    let timer: ReturnType<typeof setTimeout> | undefined;
    const step = () => {
      const t = Math.min(1, (Date.now() - now) / duration);
      // Turning is quicker than moving: the moto points the new way in the first third of the glide.
      apply({ point: lerpCoordinate(from.point, target, t), rotation: lerpAngle(from.rotation, rotation, Math.min(1, t * 3)) });
      if (t < 1) timer = setTimeout(step, FRAME_MS);
    };
    step();
    return () => clearTimeout(timer);
    // A new GPS point (or heading) starts a new glide from wherever the moto is now.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [target.latitude, target.longitude, driver.heading, reduce]);

  return (
    <Marker
      coordinate={shown.point}
      anchor={{ x: 0.5, y: 0.5 }}
      rotation={shown.rotation}
      flat
      tracksViewChanges={tracks}
      zIndex={zIndex}
      onPress={onPress}>
      <Image source={MOTO_TOP} style={{ width: size, height: size }} resizeMode="contain" accessibilityIgnoresInvertColors />
    </Marker>
  );
}

/** A soft ring that grows from the pickup point while the moto is on its way (doc 01-A). */
function PickupPulse({ center, color }: { center: Coordinate; color: string }) {
  const reduce = useReducedMotion();
  const [t, setT] = useState(0);
  useEffect(() => {
    if (reduce) return;
    const began = Date.now();
    // 12 fps is plenty for a ring that is only a hint, and cheap for the native map.
    const timer = setInterval(() => setT(((Date.now() - began) % 1800) / 1800), 83);
    return () => clearInterval(timer);
  }, [reduce]);
  if (reduce) return null;
  const alpha = Math.round((1 - t) * 0.35 * 255)
    .toString(16)
    .padStart(2, '0');
  return <Circle center={center} radius={15 + 70 * t} fillColor={`${color}${alpha}`} strokeColor="transparent" strokeWidth={0} zIndex={2} />;
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
  areas,
  focus,
  pulsePickup = false,
  activity,
  onActivityPress,
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

  // Doc 01-A: keep the moving moto (and what it is heading to) in view until the user pans the map. At most
  // every 4 s, so the camera drifts calmly instead of chasing every GPS point.
  const lastFollow = useRef(0);
  useEffect(() => {
    if (!ready || !driver || userMoved.current || Date.now() - lastFollow.current < 4000) return;
    lastFollow.current = Date.now();
    frame(true);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [ready, driver?.lat, driver?.lng]);

  // Follow the user until they pan the map themselves.
  useEffect(() => {
    if (!ready || !followUser || !position || userMoved.current) return;
    const first = !followed.current;
    followed.current = true;
    mapRef.current?.animateCamera(first ? { center: toCoordinate(position), zoom: 16 } : { center: toCoordinate(position) }, {
      duration: 600,
    });
  }, [ready, followUser, position]);

  // Doc 21: "Ver en el mapa" on a demand banner. The user looking elsewhere stops the follow mode.
  const focusKey = focus?.key;
  useEffect(() => {
    if (!ready || !focus) return;
    userMoved.current = true;
    mapRef.current?.animateCamera({ center: toCoordinate(focus.point), zoom: 14 }, { duration: 600 });
    // Only a new key moves the camera.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [ready, focusKey]);

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
        {areas?.map((area) => (
          <Polygon
            key={area.id}
            coordinates={area.coordinates.map(toCoordinate)}
            fillColor={area.fill}
            strokeColor={area.stroke}
            strokeWidth={1.5}
            tappable={false}
            zIndex={0}
          />
        ))}
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
        {pickup && pulsePickup ? <PickupPulse center={toCoordinate(pickup)} color={theme.primary} /> : null}
        {activity?.map((trip) => (
          <DriverMarker key={trip.id} driver={trip} size={34} zIndex={3} onPress={() => onActivityPress?.(trip)} />
        ))}
        {driver ? <DriverMarker driver={driver} /> : null}
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
  recenter: { position: 'absolute', right: 16 },
});
