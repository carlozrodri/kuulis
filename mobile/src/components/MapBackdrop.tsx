import { useWindowDimensions } from 'react-native';
import Svg, { Circle, G, Path, Rect } from 'react-native-svg';

import { useTheme } from '@/theme';

/**
 * Stylized city map used as a backdrop until the real map arrives (later phase).
 * Decorative only: hidden from screen readers.
 */
export function MapBackdrop({ height = 380, variant = 'passenger' }: { height?: number; variant?: 'passenger' | 'driver' }) {
  const theme = useTheme();
  const { width } = useWindowDimensions();
  const dark = theme.scheme === 'dark';
  const land = dark ? '#101A15' : '#E4EEE8';
  const park = dark ? '#14241C' : '#CFE3D6';
  const road = dark ? '#1C2A23' : '#FFFFFF';
  const block = dark ? '#16221C' : '#D8E8DD';

  return (
    <Svg
      width={width}
      height={height}
      viewBox="0 0 390 380"
      preserveAspectRatio="xMidYMid slice"
      style={{ position: 'absolute', top: 0, left: 0 }}
      accessibilityElementsHidden
      importantForAccessibility="no-hide-descendants">
      <Rect width={390} height={380} fill={land} />
      <Path d="M0 0 H390 V110 C330 130 280 100 220 118 C160 136 90 108 0 130 Z" fill={park} />
      <Rect x={236} y={250} width={96} height={64} rx={14} fill={block} />
      <Rect x={28} y={300} width={70} height={50} rx={12} fill={block} />
      <Path d="M-10 210 C90 200 160 230 260 216 S 360 200 400 208" fill="none" stroke={road} strokeWidth={14} strokeLinecap="round" />
      <Path d="M-10 340 C100 332 220 360 400 344" fill="none" stroke={road} strokeWidth={10} strokeLinecap="round" />
      <Path d="M120 140 L140 380" stroke={road} strokeWidth={8} />
      <Path d="M300 140 L270 380" stroke={road} strokeWidth={8} />
      <Path d="M30 280 H220" stroke={road} strokeWidth={5} />
      {variant === 'driver' ? (
        <G>
          <Circle cx={250} cy={270} r={60} fill={theme.accent} opacity={0.28} />
          <Circle cx={80} cy={190} r={40} fill={theme.accent} opacity={0.22} />
        </G>
      ) : (
        <G fill={dark ? '#E7EFEB' : '#14201B'}>
          <G transform="translate(76 232)">
            <Rect width={26} height={18} rx={6} />
            <Circle cx={7} cy={18} r={4} />
            <Circle cx={19} cy={18} r={4} />
          </G>
          <G transform="translate(286 168)">
            <Rect width={26} height={18} rx={6} />
            <Circle cx={7} cy={18} r={4} />
            <Circle cx={19} cy={18} r={4} />
          </G>
        </G>
      )}
      <Circle cx={190} cy={262} r={34} fill={theme.primary} opacity={0.16} />
      <Circle cx={190} cy={262} r={10} fill={theme.primary} stroke={road} strokeWidth={4} />
    </Svg>
  );
}
