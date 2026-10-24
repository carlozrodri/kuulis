import * as Device from 'expo-device';
import * as Notifications from 'expo-notifications';
import { AndroidImportance, AndroidNotificationVisibility } from 'expo-notifications';
import { useQueryClient } from '@tanstack/react-query';
import { useEffect, useRef } from 'react';
import { Platform } from 'react-native';

import { DRIVER_QUERY_KEY, isDriverNotification } from '@/hooks/useDriver';
import { refreshReports } from '@/hooks/useReports';
import { rideKeys } from '@/hooks/useRides';
import { answerCheckIn, refreshAlerts } from '@/hooks/useSafety';
import { isSubscriptionNotification, isWalletNotification, refreshSubscription, refreshWallet } from '@/hooks/useWallet';
import { api } from '@/lib/api';
import { appVersion } from '@/lib/appVersion';
import { config } from '@/lib/config';
import i18n from '@/i18n';
import { type ChannelId, type ChannelImportance, NOTIFICATION_CHANNELS, reportedChannels } from '@/lib/notificationChannels';
import { isAccountNotification, isReportNotification } from '@/lib/reports';
import { alertIdOf, checkInAnswerOf, isSafetyNotification, SAFETY_CATEGORY } from '@/lib/safety';
import { useAuth } from '@/providers/AuthProvider';

Notifications.setNotificationHandler({
  handleNotification: async () => ({
    shouldShowBanner: true,
    shouldShowList: true,
    shouldPlaySound: true,
    shouldSetBadge: true,
  }),
});

const IMPORTANCE: Record<ChannelImportance, AndroidImportance> = {
  max: AndroidImportance.MAX,
  high: AndroidImportance.HIGH,
  default: AndroidImportance.DEFAULT,
  low: AndroidImportance.LOW,
};

/**
 * Creates (or renames, after a language change) the Android channels of doc 14 and returns the ids that exist.
 * Android keeps a channel's importance and vibration as first created; only name and description update.
 */
async function createNotificationChannels(): Promise<string[]> {
  const created = await Promise.all(
    NOTIFICATION_CHANNELS.map((channel) =>
      Notifications.setNotificationChannelAsync(channel.id, {
        name: i18n.t(channel.nameKey),
        description: i18n.t(channel.descriptionKey),
        importance: IMPORTANCE[channel.importance],
        ...(channel.vibrationPattern ? { vibrationPattern: channel.vibrationPattern, enableVibrate: true } : {}),
        ...(channel.publicOnLockScreen ? { lockscreenVisibility: AndroidNotificationVisibility.PUBLIC } : {}),
      })
        .then((result) => (result ? channel.id : null))
        .catch(() => null),
    ),
  );
  return created.filter((id): id is ChannelId => id !== null);
}

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
      // "¿Todo bien?" (doc 11): the app shows the question too.
      if (isSafetyNotification(data)) refreshAlerts(queryClient);
    };
    // The "Estoy bien" / "Necesito ayuda" buttons of a check-in push answer without going through the modal.
    const answerFrom = (r: Notifications.NotificationResponse) => {
      const answer = checkInAnswerOf(r.actionIdentifier);
      const alertId = alertIdOf(r.notification.request.content.data);
      if (!answer || !alertId) return;
      void answerCheckIn(alertId, answer)
        .catch(() => undefined)
        .finally(() => refreshAlerts(queryClient));
    };
    const received = Notifications.addNotificationReceivedListener((n) => handle(n.request.content.data));
    const opened = Notifications.addNotificationResponseReceivedListener((r) => {
      const data = r.notification.request.content.data;
      handle(data);
      answerFrom(r);
      // Opening the right screen (doc 14) is NotificationOpener's job, inside the signed-in navigator.
    });
    // A button pressed while the app was closed: the response is waiting here.
    void Notifications.getLastNotificationResponseAsync()
      .then((r) => {
        if (r) answerFrom(r);
      })
      .catch(() => undefined);
    return () => {
      received.remove();
      opened.remove();
    };
  }, [enabled, queryClient]);

  useEffect(() => {
    if (!enabled || Platform.OS === 'web' || !Device.isDevice || !config.easProjectId) return;

    (async () => {
      const channels = Platform.OS === 'android' ? await createNotificationChannels() : [];
      // Doc 11: action buttons of the "¿Todo bien?" push. "Estoy bien" answers in the background; asking for
      // help opens the app so the person can also call the emergency number.
      await Notifications.setNotificationCategoryAsync(SAFETY_CATEGORY, [
        { identifier: 'ok', buttonTitle: i18n.t('safety.checkIn.ok'), options: { opensAppToForeground: false } },
        { identifier: 'help', buttonTitle: i18n.t('safety.checkIn.help'), options: { opensAppToForeground: true } },
      ]).catch(() => undefined);
      let { status } = await Notifications.getPermissionsAsync();
      if (status !== 'granted') status = (await Notifications.requestPermissionsAsync()).status;
      if (status !== 'granted') return;

      const { data: pushToken } = await Notifications.getExpoPushTokenAsync({ projectId: config.easProjectId });
      await api('/notifications/devices', {
        method: 'POST',
        // Every start: the server refreshes last_seen_at, and only uses the channels this phone has (doc 14).
        body: {
          push_token: pushToken,
          platform: Platform.OS,
          channels: reportedChannels(Platform.OS, channels),
          ...(appVersion.version ? { app_version: appVersion.version } : {}),
        },
      });
    })().catch((error) => console.warn('Push registration failed', error));
  }, [enabled]);
}
