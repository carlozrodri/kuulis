import { useEffect, useState } from 'react';
import { Animated, StyleSheet, View } from 'react-native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';

import { CircleCheck, Info, TriangleAlert } from '@/components/icons';
import { Txt } from '@/components/ui';
import { createStore, useStore } from '@/lib/store';
import { elevation, radius, space, useTheme } from '@/theme';

type ToastTone = 'info' | 'success' | 'danger';
type ToastState = { id: number; message: string; tone: ToastTone } | null;

const toastStore = createStore<ToastState>(null);
let nextId = 1;

/** Shows a short message at the top of the screen (used for ride events and action errors). */
export function showToast(message: string, tone: ToastTone = 'info') {
  toastStore.set({ id: nextId++, message, tone });
}

export function ToastHost() {
  const toast = useStore(toastStore);
  const theme = useTheme();
  const insets = useSafeAreaInsets();
  const [opacity] = useState(() => new Animated.Value(0));

  useEffect(() => {
    if (!toast) return;
    opacity.setValue(0);
    Animated.timing(opacity, { toValue: 1, duration: 220, useNativeDriver: true }).start();
    const timer = setTimeout(() => {
      Animated.timing(opacity, { toValue: 0, duration: 220, useNativeDriver: true }).start(() => {
        if (toastStore.get()?.id === toast.id) toastStore.set(null);
      });
    }, 3800);
    return () => clearTimeout(timer);
  }, [toast, opacity]);

  if (!toast) return null;
  const ToastIcon = toast.tone === 'danger' ? TriangleAlert : toast.tone === 'success' ? CircleCheck : Info;
  const fg = toast.tone === 'danger' ? theme.danger : toast.tone === 'success' ? theme.success : theme.primary;
  return (
    <View pointerEvents="none" style={[styles.wrap, { top: insets.top + space.sm }]}>
      <Animated.View
        accessibilityLiveRegion="polite"
        accessibilityRole="alert"
        style={[
          styles.toast,
          { backgroundColor: theme.surface, opacity, transform: [{ translateY: opacity.interpolate({ inputRange: [0, 1], outputRange: [-12, 0] }) }] },
          elevation(theme, 2),
        ]}>
        <ToastIcon size={20} color={fg} strokeWidth={2.2} />
        <Txt variant="bodyStrong" style={{ flex: 1 }}>
          {toast.message}
        </Txt>
      </Animated.View>
    </View>
  );
}

const styles = StyleSheet.create({
  wrap: { position: 'absolute', left: space.md, right: space.md, alignItems: 'center', zIndex: 100 },
  toast: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: space.sm,
    width: '100%',
    maxWidth: 480,
    borderRadius: radius.tile,
    paddingHorizontal: space.md,
    paddingVertical: 14,
  },
});
