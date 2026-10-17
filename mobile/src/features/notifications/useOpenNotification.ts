import { useQueryClient } from '@tanstack/react-query';
import { router, usePathname, type Href } from 'expo-router';
import { useCallback, useEffect, useRef } from 'react';
import { Linking } from 'react-native';

import { routedRides } from '@/features/ride/store';
import { demandFocusRequest, setDemandLayer } from '@/hooks/useDemand';
import { markNotificationRead } from '@/hooks/useNotifications';
import { rideKeys } from '@/hooks/useRides';
import { api } from '@/lib/api';
import {
  campaignNotificationId,
  demandPushPoint,
  hrefForNotification,
  isInboxTarget,
  needsPendingRating,
  type NotificationTarget,
} from '@/lib/notificationRoutes';
import type { Ride } from '@/lib/types';
import { useMode } from '@/providers/ModeProvider';

/** Gives the read a moment before leaving the app for the browser, without making the tap feel slow. */
const within = <T,>(promise: Promise<T>, ms: number) =>
  Promise.race([promise.then(() => undefined), new Promise<void>((resolve) => setTimeout(resolve, ms))]);

const pathOf = (href: Href) => (typeof href === 'string' ? href.split('?')[0] : href.pathname);
const rideIdOf = (href: Href) =>
  typeof href === 'object' && (href.pathname === '/ride' || href.pathname === '/drive')
    ? (href.params as Record<string, unknown> | undefined)?.id
    : undefined;

/**
 * Opens what a notification is about (doc 14), from a push or from the inbox: the ride, the wallet, a
 * conversation, a campaign's link... `from: "inbox"` means the inbox already marked the item read.
 */
export function useOpenNotification() {
  const queryClient = useQueryClient();
  const { mode, setMode } = useMode();
  const pathname = usePathname();
  const state = useRef({ mode, setMode, pathname });
  useEffect(() => {
    state.current = { mode, setMode, pathname };
  });

  return useCallback(
    async (payload: unknown, from: 'push' | 'inbox') => {
      // A campaign tap counts as opened: mark its inbox copy read (the inbox already did it for its own taps).
      const campaignId = from === 'push' ? campaignNotificationId(payload) : null;
      const read = campaignId ? markNotificationRead(queryClient, campaignId).catch(() => undefined) : null;

      let pendingRatingRideId: string | null = null;
      if (needsPendingRating(payload)) {
        const pending = await queryClient
          .fetchQuery({ queryKey: rideKeys.pendingRating, queryFn: () => api<Ride | null>('/rides/pending-rating'), staleTime: 0 })
          .catch(() => null);
        pendingRatingRideId = pending?.id ?? null;
      }
      const target: NotificationTarget = hrefForNotification(payload, { role: state.current.mode, pendingRatingRideId });

      if (target.kind === 'url') {
        if (read) await within(read, 1500);
        await Linking.openURL(target.url).catch(() => undefined);
        return;
      }
      if (from === 'inbox' && isInboxTarget(target)) return;
      // Doc 21: the driver home turns the demand layer on and shows the hot spot.
      const demandPoint = demandPushPoint(payload);
      if (demandPoint) {
        setDemandLayer(true);
        demandFocusRequest.set({ ...demandPoint, at: Date.now() });
      }
      if (target.mode && state.current.mode && state.current.mode !== target.mode) await state.current.setMode(target.mode);
      // Already there (e.g. the rating opened by itself): don't stack a second copy.
      const path = pathOf(target.href);
      const hasParams = typeof target.href === 'object' && !!target.href.params;
      if (!hasParams && state.current.pathname === path) return;
      // The live ride screen is opened once per ride by the ride navigator: this tap counts as that time.
      const rideId = rideIdOf(target.href);
      if (typeof rideId === 'string') routedRides.add(rideId);
      router.push(target.href);
    },
    [queryClient],
  );
}
