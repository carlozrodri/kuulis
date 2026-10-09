import type { BottomTabBarProps } from 'expo-router/tabs';
import { Pressable, StyleSheet, View } from 'react-native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';

import { Bell, House, type Icon, User } from '@/components/icons';
import { TAB_BAR_HEIGHT } from '@/components/ui';
import { radius, space, useTheme } from '@/theme';

const ICONS: Record<string, Icon> = { index: House, notifications: Bell, profile: User };

/** Floating dark pill navigation; the active item sits in a `primary` circle. */
export function TabBar({ state, descriptors, navigation, badges = {} }: BottomTabBarProps & { badges?: Record<string, boolean> }) {
  const theme = useTheme();
  const insets = useSafeAreaInsets();

  return (
    <View
      pointerEvents="box-none"
      style={[styles.wrap, { bottom: Math.max(insets.bottom, space.md) }]}>
      <View
        accessibilityRole="tablist"
        style={[styles.bar, { backgroundColor: theme.nav, shadowColor: theme.shadow }]}>
        {state.routes.map((route, index) => {
          const focused = state.index === index;
          const { options } = descriptors[route.key];
          const TabIcon = ICONS[route.name] ?? House;
          const label = options.title ?? route.name;
          const onPress = () => {
            const event = navigation.emit({ type: 'tabPress', target: route.key, canPreventDefault: true });
            if (!focused && !event.defaultPrevented) navigation.navigate(route.name, route.params);
          };
          return (
            <Pressable
              key={route.key}
              accessibilityRole="tab"
              accessibilityLabel={badges[route.name] ? `${label} •` : label}
              accessibilityState={{ selected: focused }}
              onPress={onPress}
              onLongPress={() => navigation.emit({ type: 'tabLongPress', target: route.key })}
              hitSlop={6}
              style={[styles.item, focused && { backgroundColor: theme.primary }]}>
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
  badge: { position: 'absolute', top: 10, right: 13, width: 10, height: 10, borderRadius: 5, borderWidth: 2 },
});
