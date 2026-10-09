import { router } from 'expo-router';
import { useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Animated, StyleSheet, View } from 'react-native';

import { Bike, ChevronRight, Info, Power } from '@/components/icons';
import { RideMap } from '@/components/map/RideMap';
import { MapSheetLayout } from '@/components/MapSheetLayout';
import { showToast } from '@/components/Toast';
import { Button, Card, IconTile, Notice, Skeleton, StatusPill, Txt } from '@/components/ui';
import { LocationPrompt } from '@/features/ride/LocationPrompt';
import { getFreshPosition, requestLocationPermission, useUserLocation } from '@/hooks/useLocation';
import { useActiveRide, useDriverState, useGoOffline, useGoOnline } from '@/hooks/useRides';
import { apiErrorMessage } from '@/i18n';
import { confirmHaptic, heavyHaptic } from '@/lib/feedback';
import { isActiveStatus } from '@/lib/ride';
import { elevation, radius, space, useTheme } from '@/theme';

/** Breathing green dot while online. */
function LiveDot({ online }: { online: boolean }) {
  const theme = useTheme();
  const [pulse] = useState(() => new Animated.Value(0));
  useEffect(() => {
    if (!online) return;
    const loop = Animated.loop(Animated.timing(pulse, { toValue: 1, duration: 1600, useNativeDriver: true }));
    loop.start();
    return () => loop.stop();
  }, [online, pulse]);
  const color = online ? theme.success : theme.muted;
  return (
    <View style={styles.liveWrap}>
      {online ? (
        <Animated.View
          style={[
            styles.liveHalo,
            {
              backgroundColor: color,
              opacity: pulse.interpolate({ inputRange: [0, 1], outputRange: [0.45, 0] }),
              transform: [{ scale: pulse.interpolate({ inputRange: [0, 1], outputRange: [1, 2.6] }) }],
            },
          ]}
        />
      ) : null}
      <View style={[styles.liveDot, { backgroundColor: color }]} />
    </View>
  );
}

/**
 * Approved driver's home: huge CONECTARME / DESCONECTARME over the map. Going online sends the current
 * position (POST /drivers/me/online); the DriverController then streams it every ~4 s over the socket.
 */
export function DriverDashboard() {
  const { t } = useTranslation();
  const theme = useTheme();
  const state = useDriverState(true);
  const active = useActiveRide();
  const goOnline = useGoOnline();
  const goOffline = useGoOffline();
  const { permission } = useUserLocation();
  const [locating, setLocating] = useState(false);

  const online = !!state.data?.online;
  const activeRide = active.data && isActiveStatus(active.data.status) ? active.data : null;

  const connect = async () => {
    setLocating(true);
    try {
      if (permission !== 'granted' && !(await requestLocationPermission())) {
        showToast(t('location.requiredToConnect'), 'danger');
        return;
      }
      const position = await getFreshPosition();
      if (!position) {
        showToast(t('location.unavailable'), 'danger');
        return;
      }
      await goOnline.mutateAsync({ lat: position.lat, lng: position.lng });
      confirmHaptic();
    } catch (error) {
      showToast(apiErrorMessage(error), 'danger');
    } finally {
      setLocating(false);
    }
  };

  const disconnect = () => {
    heavyHaptic();
    goOffline.mutate(undefined, { onError: (error) => showToast(apiErrorMessage(error), 'danger') });
  };

  return (
    <MapSheetLayout
      map={(insets) => <RideMap insets={insets} followUser showUser />}
      topBar={
        <View style={styles.topRow}>
          <View style={[styles.statusChip, { backgroundColor: theme.surface }, elevation(theme)]}>
            <LiveDot online={online} />
            <Txt variant="bodyStrong">{online ? t('drive.home.onlineChip') : t('drive.home.offlineChip')}</Txt>
          </View>
        </View>
      }>
      {state.isPending ? (
        <View style={{ gap: space.sm }}>
          <Skeleton height={28} width="60%" />
          <Skeleton height={68} radius={radius.pill} />
        </View>
      ) : (
        <>
          <View style={{ gap: 4 }}>
            <Txt variant="heading" accessibilityRole="header">
              {online ? t('drive.home.online') : t('driver.home.offline')}
            </Txt>
            <Txt color="muted">{online ? t('drive.home.onlineBody') : t('driver.home.offlineBody')}</Txt>
          </View>

          {activeRide ? (
            <Card tone="tint" onPress={() => router.push({ pathname: '/drive', params: { id: activeRide.id } })} style={styles.activeCard}>
              <IconTile icon={Bike} />
              <View style={{ flex: 1 }}>
                <Txt variant="bodyStrong">{t('home.activeRide')}</Txt>
                <Txt variant="caption" color="muted">
                  {t(`ride.status.${activeRide.status}`)}
                </Txt>
              </View>
              <ChevronRight size={20} color={theme.muted} />
            </Card>
          ) : null}

          {permission !== 'granted' ? <LocationPrompt variant="driver" /> : null}

          {online ? (
            <Button
              title={t('drive.home.disconnect')}
              size="lg"
              variant="danger"
              icon={Power}
              loading={goOffline.isPending}
              disabled={!!activeRide}
              onPress={disconnect}
            />
          ) : (
            <Button
              title={t('driver.home.connect')}
              size="lg"
              icon={Power}
              loading={locating || goOnline.isPending}
              onPress={() => void connect()}
            />
          )}

          {online ? (
            <Notice tone="info" icon={Info}>
              {t('drive.home.foregroundOnly')}
            </Notice>
          ) : (
            <View style={{ alignItems: 'center' }}>
              <StatusPill label={t('driver.home.freeMonths')} tone="accent" />
            </View>
          )}
        </>
      )}
    </MapSheetLayout>
  );
}

const styles = StyleSheet.create({
  topRow: { flexDirection: 'row' },
  statusChip: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: space.xs,
    borderRadius: radius.pill,
    paddingHorizontal: space.md,
    paddingVertical: 10,
  },
  liveWrap: { width: 14, height: 14, alignItems: 'center', justifyContent: 'center' },
  liveHalo: { position: 'absolute', width: 14, height: 14, borderRadius: 7 },
  liveDot: { width: 12, height: 12, borderRadius: 6 },
  activeCard: { flexDirection: 'row', alignItems: 'center', gap: space.sm, padding: space.md },
});
