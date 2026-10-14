/**
 * Driver positions sent to the API (doc 16): every one says whether it came from a mock location app.
 * Pure helpers shared by the socket message, the background POST and going online.
 */

/** expo-location's `LocationObject.mocked` (Android only): anything but `true` counts as a real fix. */
export function isMockedLocation(location: { mocked?: boolean | null } | null | undefined): boolean {
  return location?.mocked === true;
}

export interface PositionInput {
  lat: number;
  lng: number;
  heading?: number | null;
  speed?: number | null;
  mocked?: boolean | null;
}

export interface PositionBody {
  lat: number;
  lng: number;
  heading?: number;
  speed?: number;
  mocked: boolean;
}

/**
 * Body of a driver position: heading in whole degrees and speed (m/s) with one decimal, each left out when
 * unknown or negative (iOS reports -1), and `mocked` always present.
 */
export function positionBody(position: PositionInput): PositionBody {
  const { lat, lng, heading, speed } = position;
  return {
    lat,
    lng,
    ...(heading != null && heading >= 0 ? { heading: Math.round(heading) } : {}),
    ...(speed != null && speed >= 0 ? { speed: Math.round(speed * 10) / 10 } : {}),
    mocked: position.mocked === true,
  };
}

/** WS `driver.mock_location`: true when the server took the driver offline (`online: false`). */
export function mockLocationTookOffline(data: unknown): boolean {
  return !!data && typeof data === 'object' && (data as { online?: unknown }).online === false;
}

/** Going online answered 409 mock_location: the position came from a mock location app. */
export function isMockLocationError(error: unknown): boolean {
  return !!error && typeof error === 'object' && (error as { code?: unknown }).code === 'mock_location';
}
