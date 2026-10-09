/**
 * Social sign-in (Google everywhere, Apple on iOS). Both return an id token that the API verifies
 * (POST /auth/social/google | /auth/social/apple).
 *
 * Native Google Sign-In is not bundled in Expo Go, so the module is only required when its native side is
 * present; otherwise the button explains it is available in the installed app instead of crashing.
 */
import * as AppleAuthentication from 'expo-apple-authentication';
import { Platform, TurboModuleRegistry } from 'react-native';

import { config } from './config';

type GoogleModule = typeof import('@react-native-google-signin/google-signin');

export class SocialCancelled extends Error {
  constructor() {
    super('cancelled');
  }
}

/**
 * - `hidden`: not configured for this build/platform (no client ids) → do not show the button.
 * - `unavailable`: configured, but the native module is missing (Expo Go) → show a friendly notice.
 * - `ready`: native sign-in works.
 */
export type GoogleAvailability = 'hidden' | 'unavailable' | 'ready';

let googleModule: GoogleModule | null | undefined;
let googleConfigured = false;

function loadGoogle(): GoogleModule | null {
  if (googleModule !== undefined) return googleModule;
  googleModule = null;
  if (Platform.OS === 'web') return null;
  try {
    // TurboModuleRegistry.get returns null instead of throwing when the native module is not linked.
    if (TurboModuleRegistry.get('RNGoogleSignin')) {
      // eslint-disable-next-line @typescript-eslint/no-require-imports
      googleModule = require('@react-native-google-signin/google-signin') as GoogleModule;
    }
  } catch {
    googleModule = null;
  }
  return googleModule;
}

export function googleAvailability(): GoogleAvailability {
  if (Platform.OS === 'web' || !config.googleWebClientId) return 'hidden';
  if (Platform.OS === 'ios' && !config.googleIosClientId) return 'hidden';
  return loadGoogle() ? 'ready' : 'unavailable';
}

/** Opens the native Google account picker and returns the id token. Throws SocialCancelled on cancel. */
export async function googleIdToken(): Promise<string> {
  const google = loadGoogle();
  if (!google) throw new Error('google_unavailable');
  const { GoogleSignin, isErrorWithCode, statusCodes } = google;
  if (!googleConfigured) {
    GoogleSignin.configure({ webClientId: config.googleWebClientId, iosClientId: config.googleIosClientId });
    googleConfigured = true;
  }
  try {
    if (Platform.OS === 'android') await GoogleSignin.hasPlayServices({ showPlayServicesUpdateDialog: true });
    const response = await GoogleSignin.signIn();
    if (response.type !== 'success') throw new SocialCancelled();
    const idToken = response.data.idToken;
    if (!idToken) throw new Error('google_no_id_token');
    return idToken;
  } catch (error) {
    if (
      error instanceof SocialCancelled ||
      (isErrorWithCode(error) && (error.code === statusCodes.SIGN_IN_CANCELLED || error.code === statusCodes.IN_PROGRESS))
    ) {
      throw new SocialCancelled();
    }
    throw error;
  }
}

/** Forget the Google account on this device so the next sign-in shows the picker again. */
export async function googleSignOut() {
  try {
    await loadGoogle()?.GoogleSignin.signOut();
  } catch {
    // Not signed in with Google; nothing to do.
  }
}

/** Sign in with Apple is iOS only (App Store guideline 4.8). */
export async function appleAvailable(): Promise<boolean> {
  if (Platform.OS !== 'ios') return false;
  try {
    return await AppleAuthentication.isAvailableAsync();
  } catch {
    return false;
  }
}

/** Apple sends the name only on the first sign-in, so we forward it to the API. */
export async function appleCredential(): Promise<{ idToken: string; fullName: string | null }> {
  try {
    const credential = await AppleAuthentication.signInAsync({
      requestedScopes: [
        AppleAuthentication.AppleAuthenticationScope.FULL_NAME,
        AppleAuthentication.AppleAuthenticationScope.EMAIL,
      ],
    });
    if (!credential.identityToken) throw new Error('apple_no_id_token');
    const name = [credential.fullName?.givenName, credential.fullName?.familyName].filter(Boolean).join(' ').trim();
    return { idToken: credential.identityToken, fullName: name || null };
  } catch (error) {
    if ((error as { code?: string })?.code === 'ERR_REQUEST_CANCELED') throw new SocialCancelled();
    throw error;
  }
}
