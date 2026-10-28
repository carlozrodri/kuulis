import { type PropsWithChildren, type ReactNode, useEffect, useRef, useState } from 'react';
import { StyleSheet, useWindowDimensions, View, type StyleProp, type ViewStyle } from 'react-native';
import Animated, {
  Easing,
  useAnimatedStyle,
  useReducedMotion,
  useSharedValue,
  withDelay,
  withSequence,
  withSpring,
  withTiming,
} from 'react-native-reanimated';

import { useTheme } from '@/theme';

/**
 * Motion building blocks (docs/product/wow/02-movimiento.md). Everything runs on the UI thread and turns
 * into a plain fade or no animation when the system asks to reduce motion.
 */

/** Spring used for taps: short and without a visible bounce. */
export const PRESS_SPRING = { damping: 18, stiffness: 420, mass: 0.6 } as const;
/** Spring for things that arrive (cards, sheets). */
export const ARRIVE_SPRING = { damping: 16, stiffness: 180, mass: 0.9 } as const;

/** Press feedback: wrap a Pressable's content (or the Pressable) in `Animated.View style={press.style}`. */
export function usePressScale(scaleTo = 0.97) {
  const reduce = useReducedMotion();
  const scale = useSharedValue(1);
  const style = useAnimatedStyle(() => ({ transform: [{ scale: scale.value }] }));
  return {
    style,
    onPressIn: () => {
      if (!reduce) scale.set(withSpring(scaleTo, PRESS_SPRING));
    },
    onPressOut: () => {
      scale.set(withSpring(1, PRESS_SPRING));
    },
  };
}

/** Rises and fades in once when mounted. `delay` staggers lists (30 ms per row). */
export function Rise({
  children,
  delay = 0,
  distance = 16,
  style,
}: PropsWithChildren<{ delay?: number; distance?: number; style?: StyleProp<ViewStyle> }>) {
  const reduce = useReducedMotion();
  const progress = useSharedValue(reduce ? 1 : 0);
  useEffect(() => {
    if (reduce) return;
    progress.set(withDelay(delay, withTiming(1, { duration: 260, easing: Easing.out(Easing.cubic) })));
  }, [delay, progress, reduce]);
  const animated = useAnimatedStyle(() => ({
    opacity: progress.value,
    transform: [{ translateY: (1 - progress.value) * distance }],
  }));
  return <Animated.View style={[animated, style]}>{children}</Animated.View>;
}

/**
 * A celebration entrance: grows from 60 % with a spring and a tiny overshoot. `trigger` replays it when it
 * changes (e.g. the ride status).
 */
export function Pop({
  children,
  trigger,
  delay = 0,
  style,
}: PropsWithChildren<{ trigger?: unknown; delay?: number; style?: StyleProp<ViewStyle> }>) {
  const reduce = useReducedMotion();
  const scale = useSharedValue(reduce ? 1 : 0.6);
  const opacity = useSharedValue(reduce ? 1 : 0);
  useEffect(() => {
    if (reduce) return;
    scale.set(0.6);
    opacity.set(0);
    scale.set(withDelay(delay, withSpring(1, { damping: 11, stiffness: 160, mass: 0.8 })));
    opacity.set(withDelay(delay, withTiming(1, { duration: 180 })));
  }, [trigger, delay, opacity, scale, reduce]);
  const animated = useAnimatedStyle(() => ({ opacity: opacity.value, transform: [{ scale: scale.value }] }));
  return <Animated.View style={[animated, style]}>{children}</Animated.View>;
}

/** One soft "heartbeat" when `trigger` changes: for a status pill or a badge that just updated. */
export function Beat({ children, trigger, style }: PropsWithChildren<{ trigger: unknown; style?: StyleProp<ViewStyle> }>) {
  const reduce = useReducedMotion();
  const scale = useSharedValue(1);
  const first = useRef(true);
  useEffect(() => {
    if (first.current) {
      first.current = false;
      return;
    }
    if (reduce) return;
    scale.set(withSequence(withTiming(1.12, { duration: 140 }), withSpring(1, PRESS_SPRING)));
  }, [trigger, reduce, scale]);
  const animated = useAnimatedStyle(() => ({ transform: [{ scale: scale.value }] }));
  return <Animated.View style={[animated, style]}>{children}</Animated.View>;
}

/**
 * Counts from the previous value (or `from`) to `value` and renders it with `children`. Runs on the JS
 * thread with requestAnimationFrame: it only re-renders a short text for under a second.
 */
export function CountUp({
  value,
  from,
  duration = 700,
  children,
}: {
  value: number;
  from?: number;
  duration?: number;
  children: (current: number) => ReactNode;
}) {
  const reduce = useReducedMotion();
  const [current, setCurrent] = useState(reduce ? value : (from ?? 0));
  const shown = useRef(current);
  useEffect(() => {
    if (reduce) return;
    const start = shown.current;
    const began = Date.now();
    let frame = 0;
    const step = () => {
      const t = Math.min(1, (Date.now() - began) / duration);
      // easeOutCubic: fast at first, settles gently on the final value.
      const eased = 1 - (1 - t) ** 3;
      const next = start + (value - start) * eased;
      shown.current = next;
      setCurrent(next);
      if (t < 1) frame = requestAnimationFrame(step);
    };
    frame = requestAnimationFrame(step);
    return () => cancelAnimationFrame(frame);
  }, [value, duration, reduce]);
  return <>{children(reduce ? value : current)}</>;
}

const PIECES = 34;

function ConfettiPiece({ index, width, height, colors }: { index: number; width: number; height: number; colors: string[] }) {
  // Deterministic pseudo-random spread so every celebration looks the same (and tests are stable).
  const seed = (n: number) => {
    const x = Math.sin(index * 9301 + n * 49297) * 233280;
    return x - Math.floor(x);
  };
  const startX = seed(1) * width;
  const drift = (seed(2) - 0.5) * 160;
  const size = 7 + seed(3) * 7;
  const delay = seed(4) * 260;
  const duration = 1100 + seed(5) * 700;
  const spin = (seed(6) > 0.5 ? 1 : -1) * (360 + seed(7) * 540);
  const color = colors[index % colors.length];
  const round = index % 3 === 0;

  const progress = useSharedValue(0);
  useEffect(() => {
    progress.set(withDelay(delay, withTiming(1, { duration, easing: Easing.out(Easing.quad) })));
  }, [delay, duration, progress]);
  const animated = useAnimatedStyle(() => ({
    opacity: progress.value < 0.85 ? 1 : (1 - progress.value) / 0.15,
    transform: [
      { translateX: startX + drift * progress.value },
      { translateY: -40 + (height * 0.75 + 40) * progress.value },
      { rotate: `${spin * progress.value}deg` },
    ],
  }));
  return (
    <Animated.View
      style={[
        styles.piece,
        { width: size, height: round ? size : size * 0.45, borderRadius: round ? size / 2 : 2, backgroundColor: color },
        animated,
      ]}
    />
  );
}

/**
 * Green and yellow confetti that falls once over the screen (about 1.5 s). Purely decorative: hidden from
 * screen readers and skipped when the system asks to reduce motion.
 */
export function Confetti({ play = true }: { play?: boolean }) {
  const theme = useTheme();
  const reduce = useReducedMotion();
  const { width, height } = useWindowDimensions();
  const [done, setDone] = useState(false);
  useEffect(() => {
    const timer = setTimeout(() => setDone(true), 2400);
    return () => clearTimeout(timer);
  }, []);
  if (!play || reduce || done) return null;
  const colors = [theme.primary, theme.accent, '#7FE0B5', theme.accent, theme.primaryPressed];
  return (
    <View pointerEvents="none" accessibilityElementsHidden importantForAccessibility="no-hide-descendants" style={StyleSheet.absoluteFill}>
      {Array.from({ length: PIECES }, (_, index) => (
        <ConfettiPiece key={index} index={index} width={width} height={height} colors={colors} />
      ))}
    </View>
  );
}

const styles = StyleSheet.create({
  piece: { position: 'absolute', top: 0, left: 0 },
});
