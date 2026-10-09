import { useNetInfo } from '@react-native-community/netinfo';
import { useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { ActivityIndicator, StyleSheet, View } from 'react-native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';

import { WifiOff } from '@/components/icons';
import { Txt } from '@/components/ui';
import { useRealtime } from '@/hooks/useRealtime';
import { radius, space, useTheme } from '@/theme';

/**
 * Small pill at the top when the phone is offline, or when the realtime channel has been down for a while
 * (poor connection). Waits a few seconds before showing so short blips do not flicker.
 */
export function ConnectionBanner() {
  const { t } = useTranslation();
  const theme = useTheme();
  const insets = useSafeAreaInsets();
  const net = useNetInfo();
  const realtime = useRealtime();
  const offline = net.isConnected === false || net.isInternetReachable === false;
  const degraded = !offline && realtime !== 'open';
  const [visible, setVisible] = useState<'offline' | 'degraded' | null>(null);

  const next = offline ? 'offline' : degraded ? 'degraded' : null;
  useEffect(() => {
    // Hide right away, show after a grace period so short blips do not flicker.
    const timer = setTimeout(() => setVisible(next), next === 'offline' ? 1500 : next ? 8000 : 0);
    return () => clearTimeout(timer);
  }, [next]);

  if (!visible || !next) return null;
  const isOffline = visible === 'offline';
  return (
    <View pointerEvents="none" style={[styles.wrap, { top: insets.top + 4 }]}>
      <View
        accessibilityRole="alert"
        accessibilityLiveRegion="polite"
        style={[styles.pill, { backgroundColor: isOffline ? theme.danger : theme.nav }]}>
        {isOffline ? <WifiOff size={16} color="#FFFFFF" strokeWidth={2.4} /> : <ActivityIndicator size="small" color="#FFFFFF" />}
        <Txt variant="micro" style={{ color: '#FFFFFF' }}>
          {isOffline ? t('connection.offline') : t('connection.reconnecting')}
        </Txt>
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  wrap: { position: 'absolute', left: 0, right: 0, alignItems: 'center', zIndex: 90 },
  pill: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: space.xs,
    borderRadius: radius.pill,
    paddingHorizontal: 14,
    paddingVertical: 8,
  },
});
