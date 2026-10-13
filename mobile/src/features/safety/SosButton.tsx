import { useRef, useState } from 'react';
import { useTranslation } from 'react-i18next';
import {
  Animated,
  Easing,
  Linking,
  Pressable,
  StyleSheet,
  View,
} from 'react-native';

import { Siren } from '@/components/icons';
import { showToast } from '@/components/Toast';
import { Txt } from '@/components/ui';
import { useAppLinks } from '@/hooks/useBootstrap';
import { triggerSos } from '@/hooks/useSafety';
import { apiErrorMessage } from '@/i18n';
import { heavyHaptic, tick } from '@/lib/feedback';
import { SOS_HOLD_MS } from '@/lib/safety';
import type { Ride } from '@/lib/types';
import { radius, space, useTheme } from '@/theme';

import { sosSheetOpen, sosShare } from './store';

/**
 * SOS (doc 11): hold for two seconds → calls the emergency number and opens an alert for the Kuulis team with
 * the live position; then offers to send the live link to the trusted contacts (SosContactsSheet).
 */
export function SosButton({ ride }: { ride: Ride }) {
  const { t } = useTranslation();
  const theme = useTheme();
  const { emergency } = useAppLinks();
  const [progress] = useState(() => new Animated.Value(0));
  const fired = useRef(false);

  const fire = () => {
    fired.current = true;
    heavyHaptic();
    // The call comes first; the alert goes out at the same time.
    void Linking.openURL(`tel:${emergency}`).catch(() => undefined);
    triggerSos(ride.id)
      .then((sos) => {
        showToast(t('safety.sos.sent'), 'success');
        if (sos.share_url) {
          sosShare.set({ ride, url: sos.share_url });
          sosSheetOpen.set(true);
        }
      })
      .catch((error) => showToast(apiErrorMessage(error), 'danger'));
  };

  const pressIn = () => {
    fired.current = false;
    tick();
    Animated.timing(progress, {
      toValue: 1,
      duration: SOS_HOLD_MS,
      easing: Easing.linear,
      useNativeDriver: false,
    }).start(({ finished }) => {
      if (finished && !fired.current) fire();
    });
  };

  const pressOut = () => {
    progress.stopAnimation();
    if (!fired.current) showToast(t('safety.sos.holdHint'));
    Animated.timing(progress, {
      toValue: 0,
      duration: 150,
      useNativeDriver: false,
    }).start();
  };

  const width = progress.interpolate({
    inputRange: [0, 1],
    outputRange: ['0%', '100%'],
  });

  return (
    <Pressable
      accessibilityRole='button'
      accessibilityLabel={t('safety.sos.label')}
      accessibilityHint={t('safety.sos.holdHint')}
      onPressIn={pressIn}
      onPressOut={pressOut}
      hitSlop={8}
      style={[styles.button, { backgroundColor: theme.danger }]}
    >
      <Animated.View style={[styles.fill, { width }]} />
      <View style={styles.content}>
        <Siren size={18} color='#FFFFFF' strokeWidth={2.4} />
        <Txt variant='label' style={{ color: '#FFFFFF' }}>
          {t('safety.sos.short')}
        </Txt>
      </View>
    </Pressable>
  );
}

const styles = StyleSheet.create({
  button: {
    height: 44,
    minWidth: 88,
    borderRadius: radius.pill,
    overflow: 'hidden',
    justifyContent: 'center',
  },
  fill: {
    position: 'absolute',
    left: 0,
    top: 0,
    bottom: 0,
    backgroundColor: 'rgba(0, 0, 0, 0.28)',
  },
  content: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: space.xs,
    paddingHorizontal: space.md,
  },
});
