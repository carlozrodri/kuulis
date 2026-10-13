import * as Notifications from 'expo-notifications';
import { useEffect, useRef } from 'react';
import { Platform } from 'react-native';

import { useOpenNotification } from './useOpenNotification';

/** Taps already handled (the listener and the cold-start response can report the same one). */
const handled = new Set<string>();

const keyOf = (response: Notifications.NotificationResponse) =>
  `${response.notification.request.identifier}|${response.actionIdentifier}`;

/** Plain taps open the app on the right screen; "Necesito ayuda" too. "Estoy bien" answers in the background. */
const opensScreen = (actionIdentifier: string) =>
  actionIdentifier === Notifications.DEFAULT_ACTION_IDENTIFIER || actionIdentifier === 'help';

/**
 * Doc 14: tapping a push opens its screen, also when the tap started the app. Mounted inside the signed-in
 * area, so the navigator and the mode are ready before it navigates (a tap made while signed out opens its
 * screen right after signing in).
 */
export function NotificationOpener() {
  const open = useOpenNotification();
  const openRef = useRef(open);
  useEffect(() => {
    openRef.current = open;
  });

  useEffect(() => {
    if (Platform.OS === 'web') return;
    const handle = (response: Notifications.NotificationResponse | null) => {
      if (!response || !opensScreen(response.actionIdentifier)) return;
      const key = keyOf(response);
      if (handled.has(key)) return;
      handled.add(key);
      void openRef.current(response.notification.request.content.data, 'push').catch(() => undefined);
    };
    const subscription = Notifications.addNotificationResponseReceivedListener(handle);
    // The tap that started the app (or that came before this mounted). Not cleared: the root push hook also
    // reads it for the "¿Todo bien?" buttons; `handled` keeps it from opening twice (e.g. sign out and in).
    try {
      handle(Notifications.getLastNotificationResponse());
    } catch {
      // Native module without the synchronous call.
      void Notifications.getLastNotificationResponseAsync()
        .then(handle)
        .catch(() => undefined);
    }
    return () => subscription.remove();
  }, []);

  return null;
}
