import type { ReactNode } from 'react';

import type { Coordinate } from '@/lib/ride';
import type { ActiveTrip, DriverLocation, LatLng } from '@/lib/types';

/** A filled polygon under the markers (doc 21: demand cells). */
export type MapArea = { id: string; coordinates: LatLng[]; fill: string; stroke: string };

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
  /** Polygons drawn under the route and the markers. */
  areas?: MapArea[];
  /** Moves the camera there once each time `key` changes (and stops following the user). */
  focus?: { point: LatLng; key: string | number } | null;
  /** A soft ring grows from the pickup point (the moto is on its way). */
  pulsePickup?: boolean;
  /** "Caracas en movimiento": real trips in progress, approximate (they glide like the ride's moto). */
  activity?: ActiveTrip[];
  onActivityPress?: (trip: ActiveTrip) => void;
  /** Extra overlays rendered on top of the map (pulsing rings, centre pin). */
  children?: ReactNode;
};
