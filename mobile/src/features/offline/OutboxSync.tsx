import NetInfo from '@react-native-community/netinfo';
import { useQueryClient } from '@tanstack/react-query';
import { useEffect } from 'react';
import { useTranslation } from 'react-i18next';
import { AppState } from 'react-native';

import { showToast } from '@/components/Toast';
import { applyMessage, applyRide, rideKeys } from '@/hooks/useRides';
import { apiErrorMessage } from '@/i18n';
import { outbox } from '@/lib/actionQueue';
import { useStore } from '@/lib/store';
import type { Ride, RideMessage } from '@/lib/types';

/**
 * Sends the queued ride actions, messages and ratings (doc 20) when the network comes back, when the app
 * returns to the foreground and on a backoff timer; applies answers that arrive after the screen that asked
 * was closed (or the app restarted), and says so when the API refused one of them.
 */
export function OutboxSync() {
  const { t } = useTranslation();
  const queryClient = useQueryClient();
  const items = useStore(outbox.store);

  useEffect(() => {
    void outbox.flush(true);
    const net = NetInfo.addEventListener((state) => {
      if (state.isConnected && state.isInternetReachable !== false) void outbox.flush(true);
    });
    const app = AppState.addEventListener('change', (state) => {
      if (state === 'active') void outbox.flush(true);
    });
    return () => {
      net();
      app.remove();
    };
  }, []);

  // Next try after the backoff of the first queued action.
  useEffect(() => {
    const delay = outbox.nextDelay();
    if (delay == null) return;
    const timer = setTimeout(() => void outbox.flush(), delay + 50);
    return () => clearTimeout(timer);
  }, [items]);

  useEffect(
    () =>
      outbox.onFinish((item, { data, error, waited }) => {
        if (error === undefined) {
          if (item.kind === 'ride_step' && data && typeof data === 'object') applyRide(queryClient, data as Ride);
          if (item.kind === 'message' && data && typeof data === 'object') applyMessage(queryClient, data as RideMessage);
          if (item.kind === 'rating') void queryClient.invalidateQueries({ queryKey: rideKeys.pendingRating });
          return;
        }
        void queryClient.invalidateQueries({ queryKey: rideKeys.all });
        if (!waited) {
          const what = t(`offline.failed.${item.kind}`);
          showToast(`${what} ${apiErrorMessage(error)}`, 'danger');
        }
      }),
    [queryClient, t],
  );

  return null;
}
