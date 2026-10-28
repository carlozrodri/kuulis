import { type PropsWithChildren, type ReactElement, type ReactNode, useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import {
  KeyboardAvoidingView,
  Platform,
  Pressable,
  type RefreshControlProps,
  ScrollView,
  StyleSheet,
  useWindowDimensions,
  View,
} from 'react-native';
import { GestureDetector, usePanGesture } from 'react-native-gesture-handler';
import Animated, { useAnimatedStyle, useSharedValue, withSpring } from 'react-native-reanimated';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import { scheduleOnRN } from 'react-native-worklets';

import { ARRIVE_SPRING } from '@/components/motion';
import { TAB_BAR_SPACE } from '@/components/ui';
import { selectionHaptic } from '@/lib/feedback';
import { radius, space, useTheme } from '@/theme';

export type MapInsets = { top: number; bottom: number };

/** Part of a collapsed sheet that stays visible above the bottom padding (handle + title) by default. */
const PEEK = 112;

/**
 * "The map is the screen": a full-screen map with floating controls on top and a rounded bottom sheet.
 * `map` receives the space covered by the overlays so the camera centres in the visible part.
 * A collapsible sheet can be dragged down by its handle to show more map (and back up, or tapped).
 */
export function MapSheetLayout({
  map,
  topBar,
  refreshControl,
  tabBar = true,
  footer,
  maxSheetRatio = 0.62,
  collapsible = false,
  expandKey,
  peek = PEEK,
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
  /** The handle drags the sheet down to a peek. Off for sheets whose main action must stay visible. */
  collapsible?: boolean;
  /** When this changes the sheet opens again (e.g. the ride status changed). */
  expandKey?: unknown;
  /** How much of a collapsed sheet stays visible (above the tab bar or the bottom inset). */
  peek?: number;
}>) {
  const { t } = useTranslation();
  const theme = useTheme();
  const insets = useSafeAreaInsets();
  const { height } = useWindowDimensions();
  const [sheetHeight, setSheetHeight] = useState(Math.round(height * 0.4));
  const [topHeight, setTopHeight] = useState(0);
  const bottomPad = tabBar ? TAB_BAR_SPACE + insets.bottom : Math.max(insets.bottom, space.md) + space.xs;
  const [collapsed, setCollapsed] = useState(false);
  const offset = useSharedValue(0);
  const start = useSharedValue(0);
  // How far down the sheet travels when collapsed; nothing to hide on short sheets.
  const travel = collapsible ? Math.max(0, sheetHeight - peek - bottomPad) : 0;


  // A status change opens the sheet again (state adjusted while rendering, not in an effect).
  const [seenKey, setSeenKey] = useState(expandKey);
  if (seenKey !== expandKey) {
    setSeenKey(expandKey);
    setCollapsed(false);
  }

  useEffect(() => {
    // Keeps the sheet where it belongs when it opens, closes or changes height.
    offset.set(withSpring(collapsed ? travel : 0, ARRIVE_SPRING));
  }, [travel, collapsed, offset]);

  const pan = usePanGesture({
    enabled: travel > 0,
    activeOffsetY: [-6, 6],
    onBegin: () => {
      'worklet';
      start.set(offset.value);
    },
    onUpdate: (event) => {
      'worklet';
      const next = start.value + event.translationY;
      // A little resistance past the open position, none past the peek.
      offset.set(next < 0 ? next / 4 : Math.min(next, travel));
    },
    onDeactivate: (event) => {
      'worklet';
      const close = event.velocityY > 600 || (event.velocityY > -600 && offset.value > travel / 2);
      offset.set(withSpring(close ? travel : 0, { ...ARRIVE_SPRING, velocity: event.velocityY }));
      // The effect above then confirms the same target, so the spring keeps its velocity.
      scheduleOnRN(setCollapsed, close);
      scheduleOnRN(selectionHaptic);
    },
  });

  const sheetMotion = useAnimatedStyle(() => ({ transform: [{ translateY: offset.value }] }));
  const visibleSheet = collapsed ? sheetHeight - travel : sheetHeight;

  const handle = <View style={[styles.handle, { backgroundColor: theme.border }]} />;

  return (
    <View style={{ flex: 1, backgroundColor: theme.background }}>
      {map({ top: insets.top + topHeight, bottom: Math.max(0, visibleSheet - radius.sheet) })}
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
        <Animated.View
          onLayout={(e) => setSheetHeight(Math.round(e.nativeEvent.layout.height))}
          style={[
            styles.sheet,
            { backgroundColor: theme.surface, shadowColor: theme.shadow, maxHeight: height * maxSheetRatio + bottomPad },
            sheetMotion,
          ]}>
          {travel > 0 ? (
            <GestureDetector gesture={pan}>
              <Pressable
                accessibilityRole="button"
                accessibilityLabel={collapsed ? t('common.sheetExpand') : t('common.sheetCollapse')}
                onPress={() => {
                  selectionHaptic();
                  setCollapsed(!collapsed);
                }}
                hitSlop={{ top: 8, bottom: 8 }}
                style={styles.handleZone}>
                {handle}
              </Pressable>
            </GestureDetector>
          ) : (
            handle
          )}
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
        </Animated.View>
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
  // Taller than the handle itself so it is easy to grab (48 dp touch target with the hit slop).
  handleZone: { alignSelf: 'stretch', alignItems: 'center', paddingTop: 6, paddingBottom: 4, marginTop: -6, minHeight: 32 },
});
