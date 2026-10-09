import { type PropsWithChildren, type ReactElement, type ReactNode } from 'react';
import { type RefreshControlProps, ScrollView, StyleSheet, View } from 'react-native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';

import { MapBackdrop } from '@/components/MapBackdrop';
import { TAB_BAR_SPACE } from '@/components/ui';
import { radius, space, useTheme } from '@/theme';

const MAP_HEIGHT = 380;
const SHEET_TOP = 250;

/** "The map is the screen": a map backdrop with a rounded bottom sheet over it and room for the tab bar. */
export function MapSheetLayout({
  variant,
  topBar,
  refreshControl,
  children,
}: PropsWithChildren<{ variant: 'passenger' | 'driver'; topBar?: ReactNode; refreshControl?: ReactElement<RefreshControlProps> }>) {
  const theme = useTheme();
  const insets = useSafeAreaInsets();
  return (
    <View style={{ flex: 1, backgroundColor: theme.surface }}>
      <MapBackdrop height={MAP_HEIGHT + insets.top} variant={variant} />
      <ScrollView
        style={{ flex: 1 }}
        contentContainerStyle={{ flexGrow: 1, paddingTop: insets.top + space.md }}
        showsVerticalScrollIndicator={false}
        refreshControl={refreshControl}>
        <View style={[styles.top, { minHeight: SHEET_TOP - space.md }]}>{topBar}</View>
        <View
          style={[
            styles.sheet,
            { backgroundColor: theme.surface, shadowColor: theme.shadow, paddingBottom: TAB_BAR_SPACE + insets.bottom },
          ]}>
          <View style={[styles.handle, { backgroundColor: theme.border }]} />
          {children}
        </View>
      </ScrollView>
    </View>
  );
}

const styles = StyleSheet.create({
  top: { paddingHorizontal: space.md },
  sheet: {
    flexGrow: 1,
    borderTopLeftRadius: radius.sheet,
    borderTopRightRadius: radius.sheet,
    paddingHorizontal: space.lg,
    paddingTop: 10,
    gap: space.md,
    shadowOpacity: 0.12,
    shadowRadius: 24,
    shadowOffset: { width: 0, height: -8 },
    elevation: 10,
  },
  handle: { width: 40, height: 5, borderRadius: 5, alignSelf: 'center', marginBottom: space.xs },
});
