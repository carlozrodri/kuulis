import { router, usePathname } from 'expo-router';
import { useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Animated, Easing, StyleSheet, View } from 'react-native';

import { Clock, Cog, History, RotateCcw, User, Wrench } from '@/components/icons';
import { Button, Card, Screen, Txt } from '@/components/ui';
import { requestBootstrapRefresh, useBootstrap } from '@/hooks/useBootstrap';
import { useActiveRide } from '@/hooks/useRides';
import { localize, formatEta, maintenanceNotice, type Notice } from '@/lib/bootstrap';
import { isActiveStatus } from '@/lib/ride';
import { elevation, radius, space, useTheme } from '@/theme';

/** Screens still open during maintenance: account, ride history, notifications, help and legal texts. */
const OPEN_DURING_MAINTENANCE = ['/rides', '/profile', '/notifications', '/reports', '/report', '/legal', '/ride/detail', '/wallet'];

export function isOpenDuringMaintenance(pathname: string) {
  return OPEN_DURING_MAINTENANCE.some((prefix) => pathname === prefix || pathname.startsWith(`${prefix}/`));
}

/**
 * Maintenance (doc 10), global or in the user's city: covers home and the ride request screens with the
 * message and the estimated time. A ride in progress is never interrupted, and the account and ride history
 * stay reachable. The bootstrap is read again every 30 s while it shows, so it lifts by itself.
 */
export function MaintenanceGate() {
  const pathname = usePathname();
  const { data, fresh, failed } = useBootstrap();
  // A maintenance remembered from an earlier session only shows once the server cannot be reached.
  const notice = fresh || failed ? maintenanceNotice(data) : null;
  const active = useActiveRide(!!notice);
  const inRide = !!active.data && isActiveStatus(active.data.status);
  if (!notice || inRide || active.isPending || isOpenDuringMaintenance(pathname)) return null;
  return (
    <View style={StyleSheet.absoluteFill}>
      <MaintenanceScreen notice={notice} />
    </View>
  );
}

function MaintenanceScreen({ notice }: { notice: Notice }) {
  const { t, i18n } = useTranslation();
  const theme = useTheme();
  const [retrying, setRetrying] = useState(false);
  const message =
    localize(notice.message, i18n.language) ||
    t(notice.kind === 'maintenance' ? 'control.maintenance.defaultBody' : 'control.pause.defaultBody');
  const eta = formatEta(notice.eta, i18n.language);

  const retry = () => {
    setRetrying(true);
    requestBootstrapRefresh();
    setTimeout(() => setRetrying(false), 1500);
  };

  return (
    <Screen
      edges={['top', 'bottom', 'left', 'right']}
      footer={
        <View style={{ gap: space.xs }}>
          <Button title={t('control.maintenance.retry')} icon={RotateCcw} loading={retrying} onPress={retry} />
          <View style={styles.links}>
            <Button
              title={t('control.maintenance.history')}
              variant="ghost"
              size="sm"
              icon={History}
              style={{ flex: 1 }}
              onPress={() => router.push('/rides')}
            />
            <Button
              title={t('control.maintenance.account')}
              variant="ghost"
              size="sm"
              icon={User}
              style={{ flex: 1 }}
              onPress={() => router.push('/profile')}
            />
          </View>
        </View>
      }>
      <View style={styles.body}>
        <MaintenanceIllustration />
        <Txt variant="title" align="center" accessibilityRole="header">
          {notice.area ? t('control.maintenance.titleArea', { area: notice.area }) : t('control.maintenance.title')}
        </Txt>
        <Txt color="muted" align="center">
          {message}
        </Txt>
        {eta ? (
          <Card tone="tint" style={styles.eta}>
            <Clock size={18} color={theme.scheme === 'dark' ? theme.primary : theme.primaryPressed} strokeWidth={2.2} />
            <Txt variant="bodyStrong">{t('control.maintenance.eta', { time: eta })}</Txt>
          </Card>
        ) : null}
        <Txt variant="caption" color="muted" align="center">
          {t('control.maintenance.auto')}
        </Txt>
      </View>
    </Screen>
  );
}

/** A wrench in a soft ring with two slowly turning cogs around it, drawn from the app's own icons. */
function MaintenanceIllustration() {
  const theme = useTheme();
  const [spin] = useState(() => new Animated.Value(0));
  useEffect(() => {
    const loop = Animated.loop(Animated.timing(spin, { toValue: 1, duration: 8000, easing: Easing.linear, useNativeDriver: true }));
    loop.start();
    return () => loop.stop();
  }, [spin]);
  const rotate = spin.interpolate({ inputRange: [0, 1], outputRange: ['0deg', '360deg'] });
  const counter = spin.interpolate({ inputRange: [0, 1], outputRange: ['360deg', '0deg'] });
  const green = theme.scheme === 'dark' ? theme.primary : theme.primaryPressed;
  return (
    <View style={styles.art} accessible={false} importantForAccessibility="no-hide-descendants">
      <View style={[styles.ringOuter, { backgroundColor: theme.surfaceAlt }]}>
        <View style={[styles.ringInner, { backgroundColor: theme.accentSoft }]}>
          <View style={[styles.core, { backgroundColor: theme.surface }, elevation(theme)]}>
            <Wrench size={46} color={green} strokeWidth={2} />
          </View>
        </View>
      </View>
      <Animated.View style={[styles.cogBig, { backgroundColor: theme.surface, transform: [{ rotate }] }, elevation(theme)]}>
        <Cog size={30} color={theme.warning} strokeWidth={2} />
      </Animated.View>
      <Animated.View style={[styles.cogSmall, { backgroundColor: theme.accent, transform: [{ rotate: counter }] }]}>
        <Cog size={20} color={theme.onAccent} strokeWidth={2.2} />
      </Animated.View>
    </View>
  );
}

const styles = StyleSheet.create({
  body: { flex: 1, alignItems: 'center', justifyContent: 'center', gap: space.md, paddingVertical: space.xl },
  art: { width: 200, height: 200, alignItems: 'center', justifyContent: 'center', marginBottom: space.sm },
  ringOuter: { width: 184, height: 184, borderRadius: 92, alignItems: 'center', justifyContent: 'center' },
  ringInner: { width: 136, height: 136, borderRadius: 68, alignItems: 'center', justifyContent: 'center' },
  core: { width: 92, height: 92, borderRadius: 46, alignItems: 'center', justifyContent: 'center' },
  cogBig: {
    position: 'absolute',
    top: 6,
    right: 4,
    width: 52,
    height: 52,
    borderRadius: 26,
    alignItems: 'center',
    justifyContent: 'center',
  },
  cogSmall: {
    position: 'absolute',
    bottom: 18,
    left: 10,
    width: 36,
    height: 36,
    borderRadius: 18,
    alignItems: 'center',
    justifyContent: 'center',
  },
  eta: { flexDirection: 'row', alignItems: 'center', gap: space.xs, paddingVertical: space.sm, paddingHorizontal: space.md, borderRadius: radius.pill },
  links: { flexDirection: 'row', gap: space.xs },
});
