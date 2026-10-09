import { type PropsWithChildren, type ReactElement, type ReactNode, useState } from 'react';
import {
  KeyboardAvoidingView,
  Platform,
  type RefreshControlProps,
  ScrollView,
  StyleSheet,
  useWindowDimensions,
  View,
} from 'react-native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';

import { TAB_BAR_SPACE } from '@/components/ui';
import { radius, space, useTheme } from '@/theme';

export type MapInsets = { top: number; bottom: number };

/**
 * "The map is the screen": a full-screen map with floating controls on top and a rounded bottom sheet.
 * `map` receives the space covered by the overlays so the camera centres in the visible part.
 */
export function MapSheetLayout({
  map,
  topBar,
  refreshControl,
  tabBar = true,
  footer,
  maxSheetRatio = 0.62,
  children,
}: PropsWithChildren<{
  map: (insets: MapInsets) => ReactNode;
  topBar?: ReactNode;
  refreshControl?: ReactElement<RefreshControlProps>;
  /** Leaves room for the floating tab bar (home screens). */
  tabBar?: boolean;
  /** Sticky content under the scrollable sheet body (main call to action). */
  footer?: ReactNode;
  /** Maximum sheet height as a share of the screen. */
  maxSheetRatio?: number;
}>) {
  const theme = useTheme();
  const insets = useSafeAreaInsets();
  const { height } = useWindowDimensions();
  const [sheetHeight, setSheetHeight] = useState(Math.round(height * 0.4));
  const [topHeight, setTopHeight] = useState(0);
  const bottomPad = tabBar ? TAB_BAR_SPACE + insets.bottom : Math.max(insets.bottom, space.md) + space.xs;

  return (
    <View style={{ flex: 1, backgroundColor: theme.background }}>
      {map({ top: insets.top + topHeight, bottom: Math.max(0, sheetHeight - radius.sheet) })}
      {topBar ? (
        <View
          pointerEvents="box-none"
          style={[styles.top, { top: insets.top + space.sm }]}
          onLayout={(e) => setTopHeight(e.nativeEvent.layout.height + space.sm)}>
          {topBar}
        </View>
      ) : null}
      <KeyboardAvoidingView
        behavior={Platform.OS === 'ios' ? 'position' : undefined}
        pointerEvents="box-none"
        style={styles.sheetWrap}>
        <View
          onLayout={(e) => setSheetHeight(Math.round(e.nativeEvent.layout.height))}
          style={[
            styles.sheet,
            { backgroundColor: theme.surface, shadowColor: theme.shadow, maxHeight: height * maxSheetRatio + bottomPad },
          ]}>
          <View style={[styles.handle, { backgroundColor: theme.border }]} />
          <ScrollView
            style={{ flexGrow: 0 }}
            contentContainerStyle={[styles.content, { paddingBottom: footer ? space.sm : bottomPad }]}
            showsVerticalScrollIndicator={false}
            keyboardShouldPersistTaps="handled"
            bounces={!!refreshControl}
            refreshControl={refreshControl}>
            {children}
          </ScrollView>
          {footer ? <View style={[styles.footer, { paddingBottom: bottomPad }]}>{footer}</View> : null}
        </View>
      </KeyboardAvoidingView>
    </View>
  );
}

const styles = StyleSheet.create({
  top: { position: 'absolute', left: space.md, right: space.md },
  sheetWrap: { position: 'absolute', left: 0, right: 0, bottom: 0 },
  sheet: {
    borderTopLeftRadius: radius.sheet,
    borderTopRightRadius: radius.sheet,
    paddingTop: 10,
    shadowOpacity: 0.14,
    shadowRadius: 24,
    shadowOffset: { width: 0, height: -8 },
    elevation: 16,
  },
  content: { paddingHorizontal: space.lg, gap: space.md },
  footer: { paddingHorizontal: space.lg, paddingTop: space.xs, gap: space.xs },
  handle: { width: 40, height: 5, borderRadius: 5, alignSelf: 'center', marginBottom: space.sm },
});
