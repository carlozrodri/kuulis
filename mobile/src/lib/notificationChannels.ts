/**
 * Doc 14: Android notification channels. The server picks one per push and only uses those this phone reported
 * when registering (POST /notifications/devices `channels`); older apps only have "default".
 *
 * Not created here: "ride_offer_sound" (the offer with Kuulis' own sound). It needs the sound file bundled in the
 * APK, so it comes with a future native build; until then the server falls back to "ride_offer".
 */
import { notificationEvent, notificationType } from './notificationRoutes';

export type ChannelId = 'ride_offer' | 'ride_updates' | 'safety' | 'account' | 'marketing' | 'default';
export type ChannelImportance = 'max' | 'high' | 'default' | 'low';

export interface ChannelSpec {
  id: ChannelId;
  /** i18n keys for the name and description shown in the phone's notification settings. */
  nameKey: string;
  descriptionKey: string;
  importance: ChannelImportance;
  vibrationPattern?: number[];
  /** Shown in full on the lock screen. */
  publicOnLockScreen?: boolean;
}

/** Long, insistent buzz for a new offer (the driver may have the phone in a pocket on the moto). */
export const OFFER_VIBRATION = [0, 600, 250, 600, 250, 600, 250, 900];
const SAFETY_VIBRATION = [0, 400, 200, 400, 200, 400];

export const NOTIFICATION_CHANNELS: readonly ChannelSpec[] = [
  {
    id: 'ride_offer',
    nameKey: 'notifications.channels.rideOffer',
    descriptionKey: 'notifications.channels.rideOfferHint',
    importance: 'max',
    vibrationPattern: OFFER_VIBRATION,
    publicOnLockScreen: true,
  },
  {
    id: 'ride_updates',
    nameKey: 'notifications.channels.rideUpdates',
    descriptionKey: 'notifications.channels.rideUpdatesHint',
    importance: 'high',
    publicOnLockScreen: true,
  },
  {
    id: 'safety',
    nameKey: 'notifications.channels.safety',
    descriptionKey: 'notifications.channels.safetyHint',
    importance: 'max',
    vibrationPattern: SAFETY_VIBRATION,
    publicOnLockScreen: true,
  },
  {
    id: 'account',
    nameKey: 'notifications.channels.account',
    descriptionKey: 'notifications.channels.accountHint',
    importance: 'default',
  },
  {
    id: 'marketing',
    nameKey: 'notifications.channels.marketing',
    descriptionKey: 'notifications.channels.marketingHint',
    importance: 'low',
  },
  {
    id: 'default',
    nameKey: 'notifications.channels.default',
    descriptionKey: 'notifications.channels.defaultHint',
    importance: 'default',
  },
];

/** The channel the server uses for a push (same rules as the API), limited to the channels this phone has. */
export function channelForNotification(payload: unknown, available: readonly string[] = NOTIFICATION_CHANNELS.map((c) => c.id)): string {
  const type = notificationType(payload);
  const wanted: string[] =
    type === 'ride'
      ? notificationEvent(payload) === 'offer'
        ? ['ride_offer_sound', 'ride_offer']
        : ['ride_updates']
      : type === 'safety'
        ? ['safety']
        : type === 'campaign'
          ? ['marketing']
          : ['account'];
  return wanted.find((id) => available.includes(id)) ?? 'default';
}

/** What the device registration reports: the channels created (Android only; iOS has none). */
export function reportedChannels(platform: string, created: readonly string[]): string[] {
  return platform === 'android' ? [...new Set(created)] : [];
}
