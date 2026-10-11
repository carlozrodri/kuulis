import { useTranslation } from 'react-i18next';
import { type StyleProp, StyleSheet, View, type ViewStyle } from 'react-native';

import { Download, X } from '@/components/icons';
import { Card, IconButton, IconTile, Txt } from '@/components/ui';
import { useAppUpdate } from '@/hooks/useAppUpdate';
import { formatMegabytes } from '@/lib/appVersion';
import { space } from '@/theme';

import { InstallControls } from './UpdateControls';

/**
 * "Nueva versión disponible" card on the passenger and driver homes. Optional updates can be dismissed
 * for that build; a mandatory one postponed by a ride in progress cannot.
 */
export function UpdateBanner({ style }: { style?: StyleProp<ViewStyle> }) {
  const { t } = useTranslation();
  const { latest, available, required, dismissed, dismiss } = useAppUpdate();
  if (!available || !latest || (!required && dismissed)) return null;
  return (
    <Card tone="tint" style={[styles.card, style]}>
      <View style={styles.row}>
        <IconTile icon={Download} tone={required ? 'warning' : 'primary'} size={40} />
        <View style={{ flex: 1, gap: 2 }}>
          <Txt variant="bodyStrong">{required ? t('update.banner.requiredTitle') : t('update.banner.title')}</Txt>
          <Txt variant="caption" color="muted">
            {required
              ? t('update.banner.requiredBody', { version: latest.version })
              : t('update.banner.body', { version: latest.version, size: formatMegabytes(latest.size) })}
          </Txt>
        </View>
        {!required ? <IconButton icon={X} label={t('update.banner.dismiss')} tone="plain" size={36} onPress={dismiss} /> : null}
      </View>
      <InstallControls size="sm" />
    </Card>
  );
}

const styles = StyleSheet.create({
  card: { gap: space.sm, padding: space.md },
  row: { flexDirection: 'row', alignItems: 'center', gap: space.sm },
});
