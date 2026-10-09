import type { ConfigContext, ExpoConfig } from 'expo/config';

/**
 * APP_ENV selects the backend and the app identity, so QA and production builds can live side by side
 * on the same phone. Set it per EAS build profile (see eas.json).
 */
const APP_ENV = (process.env.APP_ENV ?? 'local') as 'local' | 'qa' | 'production';

const API_URLS = {
  local: process.env.EXPO_PUBLIC_API_URL ?? 'http://localhost:8000/api/v1',
  qa: 'https://kuulis-qa.top8.uk/api/v1',
  production: 'https://kuulis-prod.top8.uk/api/v1',
} as const;

/**
 * Google Sign-In client ids (Google Cloud console). The web client id is the `aud` of the id token the API
 * verifies; the iOS client id is required for the native iOS flow. Without them the Google button is hidden.
 */
const GOOGLE_WEB_CLIENT_ID = process.env.EXPO_PUBLIC_GOOGLE_WEB_CLIENT_ID || undefined;
const GOOGLE_IOS_CLIENT_ID = process.env.EXPO_PUBLIC_GOOGLE_IOS_CLIENT_ID || undefined;

/** "123-abc.apps.googleusercontent.com" -> "com.googleusercontent.apps.123-abc" (iOS URL scheme). */
function reversedClientId(clientId: string) {
  return clientId.split('.').reverse().join('.');
}

const suffix = APP_ENV === 'production' ? '' : `.${APP_ENV}`;
const nameSuffix = APP_ENV === 'production' ? '' : ` (${APP_ENV.toUpperCase()})`;

export default ({ config }: ConfigContext): ExpoConfig => ({
  ...config,
  name: `Kuulis${nameSuffix}`,
  slug: 'kuulis',
  owner: process.env.EXPO_OWNER,
  scheme: 'kuulis',
  version: '1.0.0',
  orientation: 'portrait',
  icon: './assets/icon.png',
  userInterfaceStyle: 'automatic',
  ios: {
    supportsTablet: true,
    bundleIdentifier: `uk.top8.kuulis${suffix}`,
    usesAppleSignIn: true,
    infoPlist: {
      NSCameraUsageDescription: 'Kuulis usa la cámara para fotografiar tus documentos, tu selfie y tu moto.',
      NSPhotoLibraryUsageDescription: 'Kuulis accede a tus fotos para subir tus documentos y las fotos de tu moto.',
    },
  },
  android: {
    package: `uk.top8.kuulis${suffix}`,
    adaptiveIcon: {
      backgroundColor: '#E6F4FE',
      foregroundImage: './assets/android-icon-foreground.png',
      backgroundImage: './assets/android-icon-background.png',
      monochromeImage: './assets/android-icon-monochrome.png',
    },
    predictiveBackGestureEnabled: false,
  },
  web: {
    bundler: 'metro',
    favicon: './assets/favicon.png',
  },
  plugins: [
    'expo-router',
    'expo-secure-store',
    'expo-localization',
    'expo-font',
    'expo-apple-authentication',
    [
      'expo-splash-screen',
      {
        image: './assets/splash-icon.png',
        imageWidth: 240,
        resizeMode: 'contain',
        backgroundColor: '#0E7C5A',
        dark: { image: './assets/splash-icon.png', backgroundColor: '#0B1310' },
      },
    ],
    [
      'expo-image-picker',
      {
        cameraPermission: 'Kuulis usa la cámara para fotografiar tus documentos, tu selfie y tu moto.',
        photosPermission: 'Kuulis accede a tus fotos para subir tus documentos y las fotos de tu moto.',
        microphonePermission: false,
      },
    ],
    ['expo-notifications', { color: '#0E7C5A' }],
    // Native Google Sign-In needs a development or store build (it is not part of Expo Go). The iOS URL
    // scheme is only added when the iOS client id is configured, so `expo start` works without it.
    ...(GOOGLE_IOS_CLIENT_ID
      ? [['@react-native-google-signin/google-signin', { iosUrlScheme: reversedClientId(GOOGLE_IOS_CLIENT_ID) }] as [string, object]]
      : []),
  ],
  experiments: {
    typedRoutes: true,
  },
  extra: {
    appEnv: APP_ENV,
    apiUrl: API_URLS[APP_ENV],
    googleWebClientId: GOOGLE_WEB_CLIENT_ID,
    googleIosClientId: GOOGLE_IOS_CLIENT_ID,
    // EAS project "kuulis" on expo.dev. Needed to sign Expo Go manifests and for push tokens.
    eas: { projectId: process.env.EAS_PROJECT_ID ?? '91bc2a11-022d-4f60-81bf-32eeba5384ba' },
  },
});
