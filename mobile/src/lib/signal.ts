/**
 * Signal and GPS quality for the driver's screen (doc 20), as three levels each, so the driver knows why an
 * action is "Enviando…" or why the passenger sees them jump on the map.
 */
export type Level = 'good' | 'weak' | 'none';

type Net = { isConnected: boolean | null; isInternetReachable: boolean | null; type?: string; details?: unknown };

/** No network → none; network but the live channel down or a 2G link → weak; else good. */
export function signalLevel(net: Net, realtime: 'connecting' | 'open' | 'closed'): Level {
  if (net.isConnected === false || net.isInternetReachable === false) return 'none';
  const generation = (net.details as { cellularGeneration?: string | null } | null | undefined)?.cellularGeneration;
  if (realtime !== 'open' || (net.type === 'cellular' && generation === '2g')) return 'weak';
  return 'good';
}

/** A fix older than this is "no GPS" (the watch asks every 3 s). */
export const GPS_STALE_MS = 30_000;

/** Fresh and within 25 m → good; fresh but rough (up to 100 m) → weak; old, rough or missing → none. */
export function gpsLevel(position: { accuracy: number | null; timestamp: number } | null, now = Date.now()): Level {
  if (!position || now - position.timestamp > GPS_STALE_MS) return 'none';
  const accuracy = position.accuracy ?? Infinity;
  if (accuracy <= 25) return 'good';
  if (accuracy <= 100) return 'weak';
  return 'none';
}
