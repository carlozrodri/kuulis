import { useTranslation } from 'react-i18next';
import { StyleSheet, View } from 'react-native';

import { Lock } from '@/components/icons';
import { Txt } from '@/components/ui';
import { spacedPin } from '@/lib/safety';
import { fonts, radius, space, useTheme } from '@/theme';

/** Passenger: the 4-digit code the driver must type to start the ride (doc 11). */
export function PinCard({ pin }: { pin: string }) {
  const { t } = useTranslation();
  const theme = useTheme();
  return (
    <View
      style={[styles.card, { backgroundColor: theme.accentSoft }]}
      accessible
      accessibilityLabel={`${t('safety.pin.title')}: ${spacedPin(pin)}. ${t('safety.pin.body')}`}>
      <View style={{ flex: 1, gap: 2 }}>
        <View style={styles.row}>
          <Lock size={16} color={theme.onAccentSoft} strokeWidth={2.4} />
          <Txt variant="label" style={{ color: theme.onAccentSoft }}>
            {t('safety.pin.title')}
          </Txt>
        </View>
        <Txt variant="caption" style={{ color: theme.onAccentSoft }}>
          {t('safety.pin.body')}
        </Txt>
      </View>
      <Txt style={[styles.pin, { color: theme.text }]} tabular>
        {spacedPin(pin)}
      </Txt>
    </View>
  );
}

const styles = StyleSheet.create({
  card: { flexDirection: 'row', alignItems: 'center', gap: space.md, borderRadius: radius.tile, padding: space.md },
  row: { flexDirection: 'row', alignItems: 'center', gap: space.xs },
  pin: { fontFamily: fonts.extrabold, fontSize: 34, letterSpacing: 2 },
});
