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
    ['expo-notifications', { color: '#4F46E5' }],
  ],
  experiments: {
    typedRoutes: true,
  },
  extra: {
    appEnv: APP_ENV,
    apiUrl: API_URLS[APP_ENV],
    // EAS project "kuulis" on expo.dev. Needed to sign Expo Go manifests and for push tokens.
    eas: { projectId: process.env.EAS_PROJECT_ID ?? '91bc2a11-022d-4f60-81bf-32eeba5384ba' },
  },
});
