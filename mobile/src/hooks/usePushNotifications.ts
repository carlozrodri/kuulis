import * as Device from 'expo-device';
import * as Notifications from 'expo-notifications';
import { useQueryClient } from '@tanstack/react-query';
import { router } from 'expo-router';
import { useEffect, useRef } from 'react';
import { Platform } from 'react-native';

import { DRIVER_QUERY_KEY, isDriverNotification } from '@/hooks/useDriver';
import { refreshReports } from '@/hooks/useReports';
import { rideKeys } from '@/hooks/useRides';
import { isSubscriptionNotification, isWalletNotification, refreshSubscription, refreshWallet } from '@/hooks/useWallet';
import { api } from '@/lib/api';
import { config } from '@/lib/config';
import { isAccountNotification, isReportNotification, reportIdOf } from '@/lib/reports';
import { useAuth } from '@/providers/AuthProvider';

Notifications.setNotificationHandler({
  handleNotification: async () => ({
    shouldShowBanner: true,
    shouldShowList: true,
    shouldPlaySound: true,
    shouldSetBadge: true,
  }),
});

/** Ride pushes carry {type: "ride.*" | "ride_*", ride_id, ...} (assumed; anything with a ride_id counts). */
export function isRideNotification(payload: unknown): boolean {
  const record = payload as { type?: unknown; ride_id?: unknown; data?: { type?: unknown; ride_id?: unknown } } | null;
  const typeValue = record?.type ?? record?.data?.type;
  return (typeof typeValue === 'string' && typeValue.startsWith('ride')) || !!(record?.ride_id ?? record?.data?.ride_id);
}

/**
 * Asks for permission and registers the Expo push token with the API once the user is signed in.
 * Requires a physical device and an EAS projectId (see docs/blockers.md).
 */
export function usePushNotifications(enabled: boolean) {
  const queryClient = useQueryClient();
  const { refreshUser } = useAuth();
  const refreshUserRef = useRef(refreshUser);
  useEffect(() => {
    refreshUserRef.current = refreshUser;
  });

  // Driver status / document review pushes refresh the onboarding screens and the inbox right away; ride
  // pushes (offers, status changes) re-sync the ride state, also when the user opens the app from one.
  useEffect(() => {
    if (!enabled || Platform.OS === 'web') return;
    const handle = (data: unknown) => {
      void queryClient.invalidateQueries({ queryKey: ['notifications'] });
      if (isDriverNotification(data)) void queryClient.invalidateQueries({ queryKey: DRIVER_QUERY_KEY });
      if (isRideNotification(data)) {
        void queryClient.invalidateQueries({ queryKey: rideKeys.all });
        void queryClient.invalidateQueries({ queryKey: rideKeys.driverState });
      }
      // Wallet pushes (top-up credited or rejected, transfer received) and subscription pushes (fee charged, due
      // tomorrow, blocked) refresh the balance, the fee card and whether the driver may go online.
      if (isWalletNotification(data)) refreshWallet(queryClient);
      if (isSubscriptionNotification(data)) refreshSubscription(queryClient);
      // Account pushes (suspended, suspension lifted) re-read the user, which shows or hides the suspension
      // panels; a suspended driver is also taken offline. Report pushes (resolved, dismissed) refresh Mis reportes.
      if (isAccountNotification(data)) {
        void refreshUserRef.current().catch(() => undefined);
        void queryClient.invalidateQueries({ queryKey: rideKeys.driverState });
      }
      if (isReportNotification(data)) refreshReports(queryClient);
    };
    const received = Notifications.addNotificationReceivedListener((n) => handle(n.request.content.data));
    const opened = Notifications.addNotificationResponseReceivedListener((r) => {
      const data = r.notification.request.content.data;
      handle(data);
      // Tapping a report push opens that report.
      const reportId = isReportNotification(data) ? reportIdOf(data) : null;
      if (reportId) router.push({ pathname: '/reports/[id]', params: { id: reportId } });
    });
    return () => {
      received.remove();
      opened.remove();
    };
  }, [enabled, queryClient]);

  useEffect(() => {
    if (!enabled || Platform.OS === 'web' || !Device.isDevice || !config.easProjectId) return;

    (async () => {
      if (Platform.OS === 'android') {
        await Notifications.setNotificationChannelAsync('default', {
          name: 'default',
          importance: Notifications.AndroidImportance.DEFAULT,
        });
      }
      let { status } = await Notifications.getPermissionsAsync();
      if (status !== 'granted') status = (await Notifications.requestPermissionsAsync()).status;
      if (status !== 'granted') return;

      const { data: pushToken } = await Notifications.getExpoPushTokenAsync({ projectId: config.easProjectId });
      await api('/notifications/devices', {
        method: 'POST',
        body: { push_token: pushToken, platform: Platform.OS },
      });
    })().catch((error) => console.warn('Push registration failed', error));
  }, [enabled]);
}
