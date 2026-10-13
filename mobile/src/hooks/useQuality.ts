import { useQuery, useQueryClient } from '@tanstack/react-query';
import { useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';

import { showToast } from '@/components/Toast';
import { useRealtimeEvent } from '@/hooks/useRealtime';
import { rideKeys } from '@/hooks/useRides';
import { api } from '@/lib/api';
import { notificationType } from '@/lib/notificationRoutes';
import { activePause, parseQualityPaused, pauseFromError, pauseFromQuality } from '@/lib/quality';
import { createStore, useStore } from '@/lib/store';
import type { DriverQuality, QualityPause } from '@/lib/types';

export const QUALITY_QUERY_KEY = ['drivers', 'me', 'quality'] as const;

type Side = 'driver' | 'passenger';

/**
 * Doc 15: the temporary pause in force for each side of the account, as last told by the server (a 403
 * temporarily_paused, the `quality.paused` event or the driver's quality panel).
 */
const pauses = createStore<Record<Side, QualityPause | null>>({ driver: null, passenger: null });

export function setQualityPause(side: Side, pause: QualityPause | null) {
  pauses.set((current) => ({ ...current, [side]: pause }));
}

/** Remembers the pause a 403 temporarily_paused describes. Returns true when the error was one. */
export function rememberPauseFromError(side: Side, error: unknown): boolean {
  const pause = pauseFromError(error);
  if (pause) setQualityPause(side, pause);
  return !!pause;
}

/** The pause in force for this side, or null; re-renders by itself when it ends. */
export function useQualityPause(side: Side): QualityPause | null {
  const stored = useStore(pauses)[side];
  const [now, setNow] = useState(() => Date.now());
  const pause = activePause(stored, now);

  useEffect(() => {
    if (!pause) return;
    const ms = Date.parse(pause.until) - Date.now();
    // Timers far in the future are unreliable on Android: re-check every hour until it is close.
    const timer = setTimeout(() => setNow(Date.now()), Math.min(ms + 500, 60 * 60_000));
    return () => clearTimeout(timer);
  }, [pause]);

  return pause;
}

/** GET /drivers/me/quality: the driver's rates, level and the rules behind them ("Mi calidad"). */
export function useDriverQuality(enabled = true) {
  return useQuery({
    queryKey: QUALITY_QUERY_KEY,
    queryFn: async () => {
      const quality = await api<DriverQuality>('/drivers/me/quality');
      setQualityPause('driver', pauseFromQuality(quality));
      return quality;
    },
    enabled,
    staleTime: 60_000,
  });
}

/**
 * Applies `quality.paused` (a pause starts, or the team lifts it) and refreshes "Mi calidad" when a quality
 * notice arrives. Mounted once in the signed-in layout, like the remote control's `driver.paused`.
 */
export function QualitySync() {
  const { t } = useTranslation();
  const queryClient = useQueryClient();

  useRealtimeEvent<unknown>('quality.paused', (data) => {
    const event = parseQualityPaused(data);
    if (!event) return;
    setQualityPause(event.role, event.until ? { until: event.until, reason: event.reason } : null);
    if (event.role !== 'driver') return;
    // The server takes a paused driver offline.
    void queryClient.invalidateQueries({ queryKey: rideKeys.driverState });
    void queryClient.invalidateQueries({ queryKey: QUALITY_QUERY_KEY });
    showToast(event.until ? t('quality.pause.toast') : t('quality.pause.liftedToast'), event.until ? 'danger' : 'success');
  });

  useRealtimeEvent<unknown>('notification', (data) => {
    if (notificationType(data) === 'quality') void queryClient.invalidateQueries({ queryKey: QUALITY_QUERY_KEY });
  });

  return null;
}
