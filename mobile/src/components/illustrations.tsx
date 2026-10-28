import { Image, type ImageStyle, type StyleProp } from 'react-native';

/**
 * The Kuulis 3D illustration set (docs/product/wow/04-identidad-iconos.md). Decorative: hidden from screen
 * readers, the text next to it carries the meaning.
 */
const SOURCES = {
  moto: require('../../assets/illustrations/moto-kuulis.png'),
} as const;

export type IllustrationName = keyof typeof SOURCES;

export function Illustration({ name, size = 96, style }: { name: IllustrationName; size?: number; style?: StyleProp<ImageStyle> }) {
  return (
    <Image
      source={SOURCES[name]}
      style={[{ width: size, height: size }, style]}
      resizeMode="contain"
      accessible={false}
      accessibilityElementsHidden
      importantForAccessibility="no"
      accessibilityIgnoresInvertColors
    />
  );
}
