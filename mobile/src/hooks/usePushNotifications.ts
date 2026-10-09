import * as Device from 'expo-device';
import * as Notifications from 'expo-notifications';
import { useEffect } from 'react';
import { Platform } from 'react-native';

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
