import { useEffect } from 'react';
import { useTranslation } from 'react-i18next';
import { Modal, Pressable, StyleSheet, View } from 'react-native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';

import { HardHat, type Icon, Lock, Share2, ShieldCheck, Siren } from '@/components/icons';
import { Button, IconTile, type Tone, Txt } from '@/components/ui';
import { secureStorage } from '@/lib/storage';
import { createStore, useStore } from '@/lib/store';
import { radius, space, useTheme } from '@/theme';

type Role = 'passenger' | 'driver';

const tipsStore = createStore<Role | null>(null);
const seenKey = (role: Role) => `kuulis.safety_tips.${role}`;

export const openSafetyTips = (role: Role) => tipsStore.set(role);
/** Other sheets wait while the tips show (iOS presents one modal at a time). */
export const useTipsOpen = () => useStore(tipsStore) !== null;

const TIPS: Record<Role, { key: string; icon: Icon; tone: Tone }[]> = {
  passenger: [
    { key: 'plate', icon: ShieldCheck, tone: 'primary' },
    { key: 'pin', icon: Lock, tone: 'accent' },
    { key: 'share', icon: Share2, tone: 'info' },
    { key: 'sos', icon: Siren, tone: 'danger' },
  ],
  driver: [
    { key: 'helmet', icon: HardHat, tone: 'accent' },
    { key: 'pin', icon: Lock, tone: 'primary' },
    { key: 'share', icon: Share2, tone: 'info' },
    { key: 'sos', icon: Siren, tone: 'danger' },
  ],
};

/** Shows the tips once, the first time this person has a ride in this role (doc 11). */
export function useFirstRideTips(role: Role, active: boolean) {
  useEffect(() => {
    if (!active) return;
    let cancelled = false;
    secureStorage
      .get(seenKey(role))
      .then((seen) => {
        if (seen || cancelled) return;
        tipsStore.set(role);
        return secureStorage.set(seenKey(role), '1');
      })
      .catch(() => undefined);
    return () => {
      cancelled = true;
    };
  }, [role, active]);
}

export function SafetyTips() {
  const { t } = useTranslation();
  const theme = useTheme();
  const insets = useSafeAreaInsets();
  const role = useStore(tipsStore);
  const close = () => tipsStore.set(null);
  return (
    <Modal visible={!!role} transparent animationType="slide" onRequestClose={close} statusBarTranslucent>
      <Pressable accessibilityRole="button" accessibilityLabel={t('common.close')} style={[StyleSheet.absoluteFill, { backgroundColor: theme.backdrop }]} onPress={close} />
      <View style={[styles.sheet, { backgroundColor: theme.surface, paddingBottom: Math.max(insets.bottom, space.md) + space.xs }]}>
        <Txt variant="heading" accessibilityRole="header">
          {t('safety.tips.title')}
        </Txt>
        {(role ? TIPS[role] : []).map((tip) => (
          <View key={tip.key} style={styles.tip}>
            <IconTile icon={tip.icon} tone={tip.tone} size={44} />
            <View style={{ flex: 1, gap: 2 }}>
              <Txt variant="bodyStrong">{t(`safety.tips.${role}.${tip.key}.title`)}</Txt>
              <Txt variant="caption" color="muted">
                {t(`safety.tips.${role}.${tip.key}.body`)}
              </Txt>
            </View>
          </View>
        ))}
        <Button title={t('safety.tips.done')} onPress={close} />
      </View>
    </Modal>
  );
}

const styles = StyleSheet.create({
  sheet: {
    position: 'absolute',
    left: 0,
    right: 0,
    bottom: 0,
    borderTopLeftRadius: radius.sheet,
    borderTopRightRadius: radius.sheet,
    padding: space.lg,
    gap: space.md,
  },
  tip: { flexDirection: 'row', alignItems: 'center', gap: space.md },
});
