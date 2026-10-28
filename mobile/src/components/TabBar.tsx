import type { BottomTabBarProps } from 'expo-router/tabs';
import { useEffect, useState } from 'react';
import { Pressable, StyleSheet, View } from 'react-native';
import Animated, { useAnimatedStyle, useSharedValue, withSpring } from 'react-native-reanimated';
import { useSafeAreaInsets } from 'react-native-safe-area-context';

import { selectionHaptic } from '@/lib/feedback';

import { Bell, House, type Icon, Route, User, Wallet } from '@/components/icons';
import { TAB_BAR_HEIGHT } from '@/components/ui';
import { radius, space, useTheme } from '@/theme';

const ICONS: Record<string, Icon> = { index: House, rides: Route, wallet: Wallet, notifications: Bell, profile: User };

const BUBBLE_SPRING = { damping: 17, stiffness: 210, mass: 0.8 } as const;

/** Floating dark pill navigation; the active item sits in a `primary` bubble that slides between tabs. */
export function TabBar({ state, descriptors, emitter, navigateToTab, badges = {} }: BottomTabBarProps & { badges?: Record<string, boolean> }) {
  const theme = useTheme();
  const insets = useSafeAreaInsets();
  // x of each tab inside the bar, measured on layout; the bubble springs to the focused one.
  const [positions, setPositions] = useState<Record<string, number>>({});
  const focusedKey = state.routes[state.index]?.key;
  const target = focusedKey !== undefined ? positions[focusedKey] : undefined;
  const bubbleX = useSharedValue(target ?? 0);
  const placed = useSharedValue(0);

  useEffect(() => {
    if (target === undefined) return;
    if (placed.value === 0) {
      // First layout: no slide from the left edge.
      bubbleX.set(target);
      placed.set(1);
    } else {
      bubbleX.set(withSpring(target, BUBBLE_SPRING));
    }
  }, [target, bubbleX, placed]);

  const bubble = useAnimatedStyle(() => ({ opacity: placed.value, transform: [{ translateX: bubbleX.value }] }));

  return (
    <View
      pointerEvents="box-none"
      style={[styles.wrap, { bottom: Math.max(insets.bottom, space.md) }]}>
      <View
        accessibilityRole="tablist"
        style={[styles.bar, { backgroundColor: theme.nav, shadowColor: theme.shadow }]}>
        <Animated.View pointerEvents="none" style={[styles.bubble, { backgroundColor: theme.primary }, bubble]} />
        {state.routes.map((route, index) => {
          const focused = state.index === index;
          const { options } = descriptors[route.key];
          // Tabs hidden with `href: null` (e.g. the wallet outside driver mode).
          if (options.hidden) return null;
          const TabIcon = ICONS[route.name] ?? House;
          const label = options.title ?? route.name;
          const onPress = () => {
            const event = emitter.emit({ type: 'tabPress', target: route.key, canPreventDefault: true });
            if (!focused && !event.defaultPrevented) {
              selectionHaptic();
              navigateToTab(route.key);
            }
          };
          return (
            <Pressable
              key={route.key}
              accessibilityRole="tab"
              accessibilityLabel={badges[route.name] ? `${label} •` : label}
              accessibilityState={{ selected: focused }}
              onPress={onPress}
              onLongPress={() => emitter.emit({ type: 'tabLongPress', target: route.key })}
              hitSlop={6}
              onLayout={(e) => {
                const x = e.nativeEvent.layout.x;
                setPositions((prev) => (prev[route.key] === x ? prev : { ...prev, [route.key]: x }));
              }}
              style={styles.item}>
              <TabIcon size={22} color={focused ? theme.onPrimary : theme.navIcon} strokeWidth={2} />
              {badges[route.name] ? <View style={[styles.badge, { backgroundColor: theme.accent, borderColor: focused ? theme.primary : theme.nav }]} /> : null}
            </Pressable>
          );
        })}
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  wrap: { position: 'absolute', left: space.md, right: space.md, alignItems: 'center' },
  bar: {
    height: TAB_BAR_HEIGHT,
    width: '100%',
    maxWidth: 420,
    borderRadius: radius.pill,
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-around',
    paddingHorizontal: space.xs,
    shadowOpacity: 0.25,
    shadowRadius: 20,
    shadowOffset: { width: 0, height: 10 },
    elevation: 12,
  },
  item: { width: 52, height: 48, borderRadius: radius.pill, alignItems: 'center', justifyContent: 'center' },
  // Same size as an item, positioned from the bar's left edge by translateX.
  bubble: { position: 'absolute', left: 0, top: (TAB_BAR_HEIGHT - 48) / 2, width: 52, height: 48, borderRadius: radius.pill },
  badge: { position: 'absolute', top: 10, right: 13, width: 10, height: 10, borderRadius: 5, borderWidth: 2 },
});
