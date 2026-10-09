import type { ReactNode } from 'react';

import type { Coordinate } from '@/lib/ride';
import type { DriverLocation, LatLng } from '@/lib/types';

export type RideMapProps = {
  pickup?: LatLng | null;
  dropoff?: LatLng | null;
  /** Live moto position (passenger side) or the driver's own position. */
  driver?: DriverLocation | null;
  /** Decoded route to draw. */
  route?: Coordinate[];
  /** Shows the blue "you are here" dot (needs location permission). */
  showUser?: boolean;
  /** Space covered by overlays (top bar, bottom sheet) so the camera centres in the visible area. */
  insets?: { top: number; bottom: number };
  /** Change it to re-frame the camera on the current points. */
  fitKey?: string;
  /** Follow the user's position until they pan the map. */
  followUser?: boolean;
  /** Where the camera starts when there is nothing else to show. */
  initialCenter?: LatLng | null;
  /** Called with the centre of the visible area when the camera stops (pin-on-map). */
  onCenterChange?: (center: LatLng) => void;
  /** Called when the user starts dragging the map. */
  onDragStart?: () => void;
  /** Shows the round "recentre" button above the sheet. */
  recenterButton?: boolean;
  /** Distance of the recentre button from the bottom (defaults to just above `insets.bottom`). */
  recenterBottom?: number;
  /** Extra overlays rendered on top of the map (pulsing rings, centre pin). */
  children?: ReactNode;
};
