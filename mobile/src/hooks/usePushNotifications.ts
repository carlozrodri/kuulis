import * as Device from 'expo-device';
import * as Notifications from 'expo-notifications';
import { useQueryClient } from '@tanstack/react-query';
import { useEffect } from 'react';
import { Platform } from 'react-native';

import { DRIVER_QUERY_KEY, isDriverNotification } from '@/hooks/useDriver';
import { api } from '@/lib/api';
import { config } from '@/lib/config';

Notifications.setNotificationHandler({
  handleNotification: async () => ({
    shouldShowBanner: true,
    shouldShowList: true,
    shouldPlaySound: true,
    shouldSetBadge: true,
  }),
});

/**
 * Asks for permission and registers the Expo push token with the API once the user is signed in.
 * Requires a physical device and an EAS projectId (see docs/blockers.md).
 */
export function usePushNotifications(enabled: boolean) {
  const queryClient = useQueryClient();

  // Driver status / document review pushes refresh the onboarding screens and the inbox right away.
  useEffect(() => {
    if (!enabled || Platform.OS === 'web') return;
    const sub = Notifications.addNotificationReceivedListener((notification) => {
      void queryClient.invalidateQueries({ queryKey: ['notifications'] });
      if (isDriverNotification(notification.request.content.data)) {
        void queryClient.invalidateQueries({ queryKey: DRIVER_QUERY_KEY });
      }
    });
    return () => sub.remove();
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
