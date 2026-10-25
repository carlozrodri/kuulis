import type { ReactNode } from 'react';
import { Pressable, StyleSheet, View } from 'react-native';

import { Check } from '@/components/icons';
import { Txt } from '@/components/ui';
import { radius, space, useTheme } from '@/theme';

/** A checkbox with its label; the label may hold links (nested Txt with onPress). */
export function CheckRow({ checked, onChange, children }: { checked: boolean; onChange: (value: boolean) => void; children: ReactNode }) {
  const theme = useTheme();
  return (
    <Pressable
      accessibilityRole="checkbox"
      accessibilityState={{ checked }}
      onPress={() => onChange(!checked)}
      hitSlop={6}
      style={styles.row}>
      <View
        style={[
          styles.box,
          { borderColor: checked ? theme.primary : theme.muted, backgroundColor: checked ? theme.primary : theme.surface },
        ]}>
        {checked ? <Check size={16} color={theme.onPrimary} strokeWidth={3} /> : null}
      </View>
      <Txt variant="caption" style={styles.label}>
        {children}
      </Txt>
    </Pressable>
  );
}

const styles = StyleSheet.create({
  row: { flexDirection: 'row', alignItems: 'flex-start', gap: space.sm, paddingVertical: space.xs },
  box: { width: 24, height: 24, borderRadius: radius.field / 2, borderWidth: 2, alignItems: 'center', justifyContent: 'center' },
  label: { flex: 1, paddingTop: 2 },
});
