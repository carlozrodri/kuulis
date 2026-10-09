import { StyleSheet, useWindowDimensions, View } from 'react-native';

import { MapBackdrop } from '@/components/MapBackdrop';

import type { RideMapProps } from './RideMap.types';

export type { RideMapProps } from './RideMap.types';

/** react-native-maps has no web implementation: the web build (development only) shows the drawn city. */
export function RideMap({ children, driver }: RideMapProps) {
  const { height } = useWindowDimensions();
  return (
    <View style={StyleSheet.absoluteFill}>
      <MapBackdrop height={height} variant={driver ? 'passenger' : 'driver'} />
      {children}
    </View>
  );
}
