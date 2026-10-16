import { useNetInfo } from '@react-native-community/netinfo';
import { useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { StyleSheet, View } from 'react-native';

import { MapPin, Wifi, WifiOff } from '@/components/icons';
import { toneColors, Txt } from '@/components/ui';
import { useUserLocation } from '@/hooks/useLocation';
import { useRealtime } from '@/hooks/useRealtime';
import { gpsLevel, type Level, signalLevel } from '@/lib/signal';
import { radius, space, useTheme } from '@/theme';

/** Two small chips on the drive screen (doc 20): data signal and GPS, each good / weak / none. */
export function SignalIndicator() {
  const { t } = useTranslation();
  const net = useNetInfo();
  const realtime = useRealtime();
  const { position } = useUserLocation();
  // Re-check the GPS age every few seconds even when no new fix arrives.
  const [now, setNow] = useState(() => Date.now());
  useEffect(() => {
    const timer = setInterval(() => setNow(Date.now()), 5000);
    return () => clearInterval(timer);
  }, []);
  const signal = signalLevel(net, realtime);
  const gps = gpsLevel(position, now);
  return (
    <View style={styles.row} accessible accessibilityLabel={`${t(`signal.data.${signal}`)}. ${t(`signal.gps.${gps}`)}`}>
      <Chip level={signal} icon={signal === 'none' ? WifiOff : Wifi} label={t(`signal.data.${signal}`)} />
      <Chip level={gps} icon={MapPin} label={t(`signal.gps.${gps}`)} />
    </View>
  );
}

function Chip({ level, icon: Icon, label }: { level: Level; icon: typeof Wifi; label: string }) {
  const theme = useTheme();
  const colors = toneColors(theme, level === 'good' ? 'success' : level === 'weak' ? 'warning' : 'danger');
  return (
    <View style={[styles.chip, { backgroundColor: colors.bg }]}>
      <Icon size={14} color={colors.fg} strokeWidth={2.4} />
      <Txt variant="micro" style={{ color: colors.fg }} numberOfLines={1}>
        {label}
      </Txt>
    </View>
  );
}

const styles = StyleSheet.create({
  row: { flexDirection: 'row', flexWrap: 'wrap', gap: space.xs },
  chip: { flexDirection: 'row', alignItems: 'center', gap: 4, borderRadius: radius.pill, paddingHorizontal: 10, paddingVertical: 4 },
});
