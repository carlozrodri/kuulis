import * as Haptics from 'expo-haptics';
import { Platform } from 'react-native';

/**
 * Haptics and sounds for ride events. Every call is best-effort: a missing module or a muted phone must
 * never break the flow (Expo Go, simulators, web).
 */
type Player = { play: () => void; seekTo: (seconds: number) => Promise<void> | void; remove?: () => void };

let offerPlayer: Player | null = null;
let audioReady = false;

async function loadOfferPlayer(): Promise<Player | null> {
  if (offerPlayer) return offerPlayer;
  if (Platform.OS === 'web') return null;
  try {
    // Loaded lazily so a build without expo-audio still runs (sound is optional).
    const audio = await import('expo-audio');
    if (!audioReady) {
      await audio.setAudioModeAsync({ playsInSilentMode: true }).catch(() => undefined);
      audioReady = true;
    }
    offerPlayer = audio.createAudioPlayer(require('../../assets/sounds/ride-offer.wav')) as unknown as Player;
    return offerPlayer;
  } catch (error) {
    console.warn('Offer sound unavailable', error);
    return null;
  }
}

/** Preloads the offer chime so it plays instantly when an offer arrives. */
export function preloadRideSounds() {
  void loadOfferPlayer();
}

export async function playOfferAlert() {
  void Haptics.notificationAsync(Haptics.NotificationFeedbackType.Warning).catch(() => undefined);
  const player = await loadOfferPlayer();
  if (!player) return;
  try {
    await player.seekTo(0);
    player.play();
  } catch {
    // ignore: sound is a nice-to-have
  }
}

export const tick = () => void Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Light).catch(() => undefined);
export const confirmHaptic = () =>
  void Haptics.notificationAsync(Haptics.NotificationFeedbackType.Success).catch(() => undefined);
export const heavyHaptic = () => void Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Heavy).catch(() => undefined);
export const selectionHaptic = () => void Haptics.selectionAsync().catch(() => undefined);
