import { type PropsWithChildren, type ReactNode, useState } from 'react';
import { ActivityIndicator, Image, Pressable, StyleSheet, View } from 'react-native';

import { Camera, type Icon } from '@/components/icons';
import { Skeleton, Txt } from '@/components/ui';
import { initials } from '@/lib/profile';
import { elevation, fonts, radius, space, useTheme } from '@/theme';

/** Section title + its card; sections are spaced evenly down the screen. */
export function Section({ title, action, children }: PropsWithChildren<{ title: string; action?: ReactNode }>) {
  return (
    <View style={styles.section}>
      <View style={styles.sectionHead}>
        <Txt variant="overline" color="muted" accessibilityRole="header" style={{ flex: 1 }}>
          {title}
        </Txt>
        {action}
      </View>
      {children}
    </View>
  );
}

/** Profile photo with a white ring; with `onEdit` a yellow camera badge opens the photo options. */
export function ProfileAvatar({
  name,
  email,
  photoUrl,
  size = 104,
  busy,
  onEdit,
  editLabel,
}: {
  name: string | null | undefined;
  email?: string | null;
  photoUrl?: string | null;
  size?: number;
  busy?: boolean;
  onEdit?: () => void;
  editLabel?: string;
}) {
  const theme = useTheme();
  const [failedUrl, setFailedUrl] = useState<string | null>(null);
  const showPhoto = !!photoUrl && failedUrl !== photoUrl;
  const ring = 4;

  const avatar = (
    <View
      style={[
        styles.avatarRing,
        { width: size + ring * 2, height: size + ring * 2, borderRadius: (size + ring * 2) / 2, borderColor: 'rgba(255,255,255,0.92)' },
      ]}>
      {showPhoto ? (
        <Image
          source={{ uri: photoUrl }}
          onError={() => setFailedUrl(photoUrl)}
          accessibilityIgnoresInvertColors
          style={{ width: size, height: size, borderRadius: size / 2, backgroundColor: theme.heroShade }}
        />
      ) : (
        <View style={[styles.center, { width: size, height: size, borderRadius: size / 2, backgroundColor: theme.accent }]}>
          <Txt style={{ fontFamily: fonts.extrabold, fontSize: size * 0.36, color: theme.onAccent }}>
            {initials(name, email)}
          </Txt>
        </View>
      )}
      {busy ? (
        <View
          style={[styles.center, { position: 'absolute', width: size, height: size, borderRadius: size / 2, backgroundColor: 'rgba(0,0,0,0.45)' }]}>
          <ActivityIndicator color="#FFFFFF" />
        </View>
      ) : null}
    </View>
  );

  if (!onEdit) return avatar;
  return (
    <Pressable
      accessibilityRole="button"
      accessibilityLabel={editLabel}
      accessibilityState={{ busy: !!busy }}
      onPress={onEdit}
      disabled={busy}
      style={({ pressed }) => ({ transform: [{ scale: pressed ? 0.97 : 1 }] })}>
      {avatar}
      <View style={[styles.cameraBadge, { backgroundColor: theme.accent, borderColor: theme.hero }]}>
        <Camera size={18} color={theme.onAccent} strokeWidth={2.4} />
      </View>
    </Pressable>
  );
}

/** Translucent pill for the green header ("Pasajero", "Correo verificado", "★ 4.9"). */
export function HeroPill({ icon: PillIcon, label, accent }: { icon?: Icon; label: string; accent?: boolean }) {
  const theme = useTheme();
  const fg = accent ? theme.onAccent : theme.onHero;
  return (
    <View style={[styles.heroPill, { backgroundColor: accent ? theme.accent : 'rgba(255,255,255,0.16)' }]}>
      {PillIcon ? <PillIcon size={14} color={fg} fill={accent ? fg : 'transparent'} strokeWidth={2.4} /> : null}
      <Txt variant="micro" style={{ color: fg }} numberOfLines={1}>
        {label}
      </Txt>
    </View>
  );
}

export type Stat = { label: string; value: string; icon?: Icon; accessibilityLabel?: string };

/** Three numbers side by side in a floating card (overlaps the header). */
export function StatStrip({ stats, loading }: { stats: Stat[]; loading?: boolean }) {
  const theme = useTheme();
  return (
    <View style={[styles.strip, { backgroundColor: theme.surface }, elevation(theme, 2)]}>
      {stats.map((stat, index) => (
        <View
          key={stat.label}
          accessible
          accessibilityLabel={stat.accessibilityLabel ?? `${stat.label}: ${stat.value}`}
          style={[styles.stat, index > 0 && { borderLeftWidth: 1, borderLeftColor: theme.divider }]}>
          {loading ? (
            <Skeleton height={26} width={48} />
          ) : (
            <View style={styles.statValue}>
              {stat.icon ? <stat.icon size={18} color={theme.accent} fill={theme.accent} strokeWidth={2} /> : null}
              <Txt variant="heading" tabular numberOfLines={1}>
                {stat.value}
              </Txt>
            </View>
          )}
          <Txt variant="caption" color="muted" numberOfLines={1} align="center">
            {stat.label}
          </Txt>
        </View>
      ))}
    </View>
  );
}

/** Pill-shaped segmented control (mode, language, appearance). */
export function Segmented<T extends string>({
  options,
  value,
  onChange,
  label,
}: {
  options: { value: T; label: string; icon?: Icon }[];
  value: T;
  onChange: (value: T) => void;
  label: string;
}) {
  const theme = useTheme();
  return (
    <View accessibilityRole="radiogroup" accessibilityLabel={label} style={[styles.segmented, { backgroundColor: theme.surfaceAlt }]}>
      {options.map((option) => {
        const selected = option.value === value;
        const fg = selected ? theme.onPrimary : theme.text;
        return (
          <Pressable
            key={option.value}
            accessibilityRole="radio"
            accessibilityState={{ selected, checked: selected }}
            accessibilityLabel={option.label}
            onPress={() => onChange(option.value)}
            style={({ pressed }) => [
              styles.segment,
              selected && [{ backgroundColor: theme.primary }, elevation(theme)],
              { opacity: pressed && !selected ? 0.7 : 1 },
            ]}>
            {option.icon ? <option.icon size={18} color={fg} strokeWidth={2.2} /> : null}
            <Txt variant="label" style={{ color: fg, fontFamily: selected ? fonts.bold : fonts.semibold }} numberOfLines={1}>
              {option.label}
            </Txt>
          </Pressable>
        );
      })}
    </View>
  );
}

/** Horizontal progress bar with a label on the right ("5 de 7"). */
export function Meter({ value, total, tone = 'primary' }: { value: number; total: number; tone?: 'primary' | 'warning' | 'danger' }) {
  const theme = useTheme();
  const color = tone === 'warning' ? theme.warning : tone === 'danger' ? theme.danger : theme.primary;
  const ratio = total > 0 ? Math.min(1, value / total) : 0;
  return (
    <View
      accessible
      accessibilityRole="progressbar"
      accessibilityValue={{ min: 0, max: total, now: value }}
      style={[styles.meter, { backgroundColor: theme.divider }]}>
      <View style={{ width: `${ratio * 100}%`, height: '100%', borderRadius: radius.pill, backgroundColor: color }} />
    </View>
  );
}

const styles = StyleSheet.create({
  center: { alignItems: 'center', justifyContent: 'center' },
  section: { marginTop: space.xl, gap: space.xs },
  sectionHead: { flexDirection: 'row', alignItems: 'center', minHeight: 24 },
  avatarRing: { borderWidth: 4, alignItems: 'center', justifyContent: 'center' },
  cameraBadge: {
    position: 'absolute',
    right: 2,
    bottom: 2,
    width: 36,
    height: 36,
    borderRadius: 18,
    borderWidth: 3,
    alignItems: 'center',
    justifyContent: 'center',
  },
  heroPill: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 5,
    borderRadius: radius.pill,
    paddingHorizontal: 10,
    paddingVertical: 5,
  },
  strip: { flexDirection: 'row', borderRadius: radius.card, paddingVertical: space.md },
  stat: { flex: 1, alignItems: 'center', gap: 2, paddingHorizontal: space.xs },
  statValue: { flexDirection: 'row', alignItems: 'center', gap: 4, minHeight: 28 },
  segmented: { flexDirection: 'row', borderRadius: radius.pill, padding: 4, gap: 4 },
  segment: {
    flex: 1,
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: 6,
    minHeight: 44,
    borderRadius: radius.pill,
    paddingHorizontal: space.sm,
  },
  meter: { height: 8, borderRadius: radius.pill, overflow: 'hidden' },
});
