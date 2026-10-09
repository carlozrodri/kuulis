import { type PropsWithChildren, type ReactNode } from 'react';
import { StyleSheet, useWindowDimensions, View } from 'react-native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import Svg, { Circle, Path } from 'react-native-svg';

import { Txt, Wordmark } from '@/components/ui';
import { radius, space, useTheme } from '@/theme';

/**
 * Brand header: Verde Ávila block with the Ávila mountain silhouette, the wordmark and a title.
 * The content below should overlap it with `marginTop: -SHEET_OVERLAP` and rounded top corners.
 */
export const SHEET_OVERLAP = 28;

export function HeroHeader({
  title,
  subtitle,
  leading,
  children,
}: PropsWithChildren<{ title?: string; subtitle?: string; leading?: ReactNode }>) {
  const theme = useTheme();
  const insets = useSafeAreaInsets();
  const { width } = useWindowDimensions();

  return (
    <View
      style={[styles.hero, { backgroundColor: theme.hero, paddingTop: insets.top + space.lg }]}
      accessibilityRole="header">
      <Svg width={width} height={130} viewBox="0 0 390 130" preserveAspectRatio="none" style={styles.mountains}>
        <Path
          d="M0 130 L0 78 C40 58 70 34 110 50 C150 66 170 22 215 24 C260 26 280 64 320 56 C350 50 370 40 390 44 L390 130 Z"
          fill={theme.heroShade}
        />
        <Path
          d="M0 130 L0 104 C60 88 110 96 160 84 C210 72 250 92 300 86 C340 82 365 90 390 84 L390 130 Z"
          fill={theme.heroShade}
          opacity={0.6}
        />
      </Svg>
      <Svg width={120} height={120} style={styles.sun} pointerEvents="none">
        <Circle cx={60} cy={60} r={44} fill={theme.accent} opacity={0.14} />
        <Circle cx={60} cy={60} r={22} fill={theme.accent} opacity={0.22} />
      </Svg>
      <View style={styles.top}>
        {leading}
        <Wordmark size={30} color={theme.onHero} />
      </View>
      {title ? (
        <Txt variant="display" style={{ color: theme.onHero, marginTop: space.lg }}>
          {title}
        </Txt>
      ) : null}
      {subtitle ? (
        <Txt style={{ color: theme.onHero, opacity: 0.9, marginTop: space.xs }}>{subtitle}</Txt>
      ) : null}
      {children}
    </View>
  );
}

/** Rounded panel that overlaps the hero header. */
export function HeroSheet({ children }: PropsWithChildren) {
  const theme = useTheme();
  return <View style={[styles.sheet, { backgroundColor: theme.background }]}>{children}</View>;
}

const styles = StyleSheet.create({
  hero: { paddingHorizontal: space.xl, paddingBottom: space.xxl + SHEET_OVERLAP, overflow: 'hidden' },
  mountains: { position: 'absolute', left: 0, bottom: 0 },
  sun: { position: 'absolute', right: -24, top: 24 },
  top: { flexDirection: 'row', alignItems: 'center', gap: space.sm },
  sheet: {
    marginTop: -SHEET_OVERLAP,
    borderTopLeftRadius: radius.sheet,
    borderTopRightRadius: radius.sheet,
    paddingHorizontal: space.lg,
    paddingTop: space.xl,
    flexGrow: 1,
  },
});
