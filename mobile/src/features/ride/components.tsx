import { type ReactNode, useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Animated, Easing, Image, Pressable, ScrollView, StyleSheet, View } from 'react-native';
import Svg, { Circle } from 'react-native-svg';

import { Banknote, Bike, Bitcoin, Coins, type Icon, Landmark, Smartphone, Star } from '@/components/icons';
import { Chip, Txt } from '@/components/ui';
import { formatPlate, formatRating, shortAddress } from '@/lib/ride';
import type { PaymentMethod, Place } from '@/lib/types';
import { elevation, fonts, radius, space, useTheme } from '@/theme';

export const PAYMENT_ICONS: Record<PaymentMethod, Icon> = {
  cash_usd: Banknote,
  pago_movil: Smartphone,
  binance: Bitcoin,
  zelle: Landmark,
  cash_ves: Coins,
};

/** Expanding rings around a centre badge ("searching for your moto"). */
export function PulsingRings({ size = 220, color, children }: { size?: number; color?: string; children?: ReactNode }) {
  const theme = useTheme();
  const tint = color ?? theme.primary;
  const [rings] = useState(() => [0, 1, 2].map(() => new Animated.Value(0)));

  useEffect(() => {
    const loops = rings.map((value, index) =>
      Animated.loop(
        Animated.sequence([
          Animated.delay(index * 700),
          Animated.timing(value, { toValue: 1, duration: 2100, easing: Easing.out(Easing.quad), useNativeDriver: true }),
        ]),
      ),
    );
    loops.forEach((loop) => loop.start());
    return () => loops.forEach((loop) => loop.stop());
  }, [rings]);

  return (
    <View pointerEvents="none" style={{ width: size, height: size, alignItems: 'center', justifyContent: 'center' }}>
      {rings.map((value, index) => (
        <Animated.View
          key={index}
          style={[
            StyleSheet.absoluteFill,
            {
              borderRadius: size / 2,
              backgroundColor: tint,
              opacity: value.interpolate({ inputRange: [0, 0.15, 1], outputRange: [0, 0.28, 0] }),
              transform: [{ scale: value.interpolate({ inputRange: [0, 1], outputRange: [0.25, 1] }) }],
            },
          ]}
        />
      ))}
      {children ?? (
        <View style={[styles.ringCore, { backgroundColor: tint, borderColor: theme.surface }, elevation(theme, 2)]}>
          <Bike size={30} color={theme.onPrimary} strokeWidth={2.2} />
        </View>
      )}
    </View>
  );
}

/** Pickup → destination with the brand markers (green dot, yellow square) joined by a line. */
export function PlaceRows({
  pickup,
  dropoff,
  pickupLabel,
  dropoffLabel,
  onPressPickup,
  onPressDropoff,
  compact,
}: {
  pickup: Place | null | undefined;
  dropoff: Place | null | undefined;
  pickupLabel?: string;
  dropoffLabel?: string;
  onPressPickup?: () => void;
  onPressDropoff?: () => void;
  compact?: boolean;
}) {
  const theme = useTheme();
  const { t } = useTranslation();
  const row = (kind: 'pickup' | 'dropoff', place: Place | null | undefined, label: string, onPress?: () => void) => {
    const content = (
      <View style={[styles.placeRow, compact && { minHeight: 40 }]}>
        <View style={styles.markerCol}>
          {kind === 'pickup' ? (
            <View style={[styles.dot, { backgroundColor: theme.primary, borderColor: theme.surfaceAlt }]} />
          ) : (
            <View style={[styles.square, { backgroundColor: theme.accent, borderColor: theme.nav }]} />
          )}
        </View>
        <View style={{ flex: 1 }}>
          <Txt variant="micro" color="muted">
            {label}
          </Txt>
          <Txt variant="bodyStrong" numberOfLines={1}>
            {place ? shortAddress(place.address) : '—'}
          </Txt>
          {!compact && place && shortAddress(place.address) !== place.address ? (
            <Txt variant="caption" color="muted" numberOfLines={1}>
              {place.address}
            </Txt>
          ) : null}
        </View>
      </View>
    );
    if (!onPress) return content;
    return (
      <Pressable
        accessibilityRole="button"
        accessibilityLabel={`${label}: ${place?.address ?? ''}`}
        onPress={onPress}
        style={({ pressed }) => ({ opacity: pressed ? 0.6 : 1 })}>
        {content}
      </Pressable>
    );
  };
  return (
    <View>
      {row('pickup', pickup, pickupLabel ?? t('ride.pickup'), onPressPickup)}
      <View style={[styles.connector, { backgroundColor: theme.border }, compact && { height: 8 }]} />
      {row('dropoff', dropoff, dropoffLabel ?? t('ride.dropoff'), onPressDropoff)}
    </View>
  );
}

const initialsOf = (name: string | null | undefined) =>
  (name ?? '?')
    .trim()
    .split(/\s+/)
    .slice(0, 2)
    .map((part) => part[0] ?? '')
    .join('')
    .toUpperCase() || '?';

export function Avatar({ name, photoUrl, size = 56 }: { name: string | null | undefined; photoUrl?: string | null; size?: number }) {
  const theme = useTheme();
  const [failed, setFailed] = useState(false);
  if (photoUrl && !failed) {
    return (
      <Image
        source={{ uri: photoUrl }}
        onError={() => setFailed(true)}
        accessibilityIgnoresInvertColors
        style={{ width: size, height: size, borderRadius: size / 2, backgroundColor: theme.surfaceAlt }}
      />
    );
  }
  return (
    <View style={[styles.avatar, { width: size, height: size, borderRadius: size / 2, backgroundColor: theme.primary }]}>
      <Txt style={{ fontFamily: fonts.extrabold, fontSize: size * 0.38, color: theme.onPrimary }}>{initialsOf(name)}</Txt>
    </View>
  );
}

export function RatingBadge({ rating }: { rating: number | string | null | undefined }) {
  const theme = useTheme();
  const { t } = useTranslation();
  const value = formatRating(rating);
  return (
    <View style={[styles.rating, { backgroundColor: theme.accentSoft }]} accessibilityLabel={value ? t('ride.ratingA11y', { value }) : t('ride.newUser')}>
      <Star size={13} color={theme.onAccentSoft} fill={theme.accent} strokeWidth={2} />
      <Txt variant="micro" style={{ color: theme.onAccentSoft }}>
        {value ?? t('ride.new')}
      </Txt>
    </View>
  );
}

/** License plate, large and tabular so it can be read from a distance. */
export function PlateBadge({ plate }: { plate: string | null | undefined }) {
  const theme = useTheme();
  const { t } = useTranslation();
  if (!plate) return null;
  return (
    <View
      accessible
      accessibilityLabel={t('ride.plateA11y', { plate: plate.split('').join(' ') })}
      style={[styles.plate, { borderColor: theme.text, backgroundColor: theme.surface }]}>
      <Txt style={{ fontFamily: fonts.extrabold, fontSize: 18, letterSpacing: 2, color: theme.text }} tabular>
        {formatPlate(plate)}
      </Txt>
    </View>
  );
}

/** Round action with a label underneath (chat, share, safety). */
export function RoundAction({
  icon: ActionIcon,
  label,
  onPress,
  badge,
  tone = 'default',
}: {
  icon: Icon;
  label: string;
  onPress: () => void;
  badge?: number;
  tone?: 'default' | 'danger';
}) {
  const theme = useTheme();
  const fg = tone === 'danger' ? theme.danger : theme.scheme === 'dark' ? theme.primary : theme.primaryPressed;
  const bg = tone === 'danger' ? theme.dangerSoft : theme.surfaceAlt;
  return (
    <Pressable
      accessibilityRole="button"
      accessibilityLabel={badge ? `${label}, ${badge}` : label}
      onPress={onPress}
      hitSlop={6}
      style={({ pressed }) => [styles.action, { opacity: pressed ? 0.7 : 1 }]}>
      <View style={[styles.actionCircle, { backgroundColor: bg }]}>
        <ActionIcon size={24} color={fg} strokeWidth={2.2} />
        {badge ? (
          <View style={[styles.badge, { backgroundColor: theme.danger, borderColor: theme.surface }]}>
            <Txt variant="micro" style={{ color: '#FFFFFF', fontSize: 11 }}>
              {badge > 9 ? '9+' : badge}
            </Txt>
          </View>
        ) : null}
      </View>
      <Txt variant="label" color="muted" numberOfLines={1}>
        {label}
      </Txt>
    </Pressable>
  );
}

export function PaymentChips({
  methods,
  value,
  onChange,
}: {
  methods: PaymentMethod[];
  value: PaymentMethod | null;
  onChange: (method: PaymentMethod) => void;
}) {
  const { t } = useTranslation();
  return (
    <ScrollView
      horizontal
      showsHorizontalScrollIndicator={false}
      contentContainerStyle={{ gap: space.xs, paddingRight: space.lg }}
      accessibilityRole="radiogroup"
      accessibilityLabel={t('ride.paymentMethod')}>
      {methods.map((method) => (
        <Chip
          key={method}
          label={t(`payment.${method}`)}
          icon={PAYMENT_ICONS[method] ?? Banknote}
          selected={value === method}
          onPress={() => onChange(method)}
        />
      ))}
    </ScrollView>
  );
}

/** Circular countdown (SVG) with free content in the middle. */
export function CountdownRing({
  progress,
  size = 168,
  stroke = 10,
  color,
  track,
  children,
}: {
  progress: number;
  size?: number;
  stroke?: number;
  color: string;
  track: string;
  children?: ReactNode;
}) {
  const r = (size - stroke) / 2;
  const circumference = 2 * Math.PI * r;
  return (
    <View style={{ width: size, height: size, alignItems: 'center', justifyContent: 'center' }}>
      <Svg width={size} height={size} style={StyleSheet.absoluteFill}>
        <Circle cx={size / 2} cy={size / 2} r={r} stroke={track} strokeWidth={stroke} fill="none" />
        <Circle
          cx={size / 2}
          cy={size / 2}
          r={r}
          stroke={color}
          strokeWidth={stroke}
          fill="none"
          strokeLinecap="round"
          strokeDasharray={`${circumference} ${circumference}`}
          strokeDashoffset={circumference * (1 - Math.min(1, Math.max(0, progress)))}
          transform={`rotate(-90 ${size / 2} ${size / 2})`}
        />
      </Svg>
      {children}
    </View>
  );
}

/** Five large tappable stars. */
export function StarInput({ value, onChange }: { value: number; onChange: (stars: number) => void }) {
  const theme = useTheme();
  const { t } = useTranslation();
  return (
    <View style={styles.stars} accessibilityRole="adjustable" accessibilityLabel={t('rating.starsA11y', { count: value })}>
      {[1, 2, 3, 4, 5].map((n) => (
        <Pressable
          key={n}
          accessibilityRole="button"
          accessibilityLabel={t('rating.starN', { count: n })}
          accessibilityState={{ selected: n <= value }}
          hitSlop={4}
          onPress={() => onChange(n)}
          style={({ pressed }) => ({ transform: [{ scale: pressed ? 0.9 : 1 }] })}>
          <Star
            size={46}
            color={n <= value ? theme.accent : theme.border}
            fill={n <= value ? theme.accent : 'transparent'}
            strokeWidth={1.8}
          />
        </Pressable>
      ))}
    </View>
  );
}

const styles = StyleSheet.create({
  ringCore: { width: 72, height: 72, borderRadius: 36, borderWidth: 5, alignItems: 'center', justifyContent: 'center' },
  placeRow: { flexDirection: 'row', alignItems: 'center', gap: space.sm, minHeight: 52 },
  markerCol: { width: 22, alignItems: 'center' },
  dot: { width: 16, height: 16, borderRadius: 8, borderWidth: 4 },
  square: { width: 15, height: 15, borderRadius: 4, borderWidth: 3 },
  connector: { width: 2, height: 14, marginLeft: 10, borderRadius: 1 },
  avatar: { alignItems: 'center', justifyContent: 'center' },
  rating: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 4,
    alignSelf: 'flex-start',
    borderRadius: radius.pill,
    paddingHorizontal: 8,
    paddingVertical: 3,
  },
  plate: { borderWidth: 2, borderRadius: 8, paddingHorizontal: 10, paddingVertical: 4, alignSelf: 'flex-start' },
  action: { alignItems: 'center', gap: 6, flex: 1, minWidth: 64 },
  actionCircle: { width: 56, height: 56, borderRadius: 28, alignItems: 'center', justifyContent: 'center' },
  badge: {
    position: 'absolute',
    top: -2,
    right: -2,
    minWidth: 20,
    height: 20,
    borderRadius: 10,
    borderWidth: 2,
    alignItems: 'center',
    justifyContent: 'center',
    paddingHorizontal: 3,
  },
  stars: { flexDirection: 'row', justifyContent: 'center', gap: space.xs },
});
