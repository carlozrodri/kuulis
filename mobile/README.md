# Kuulis Mobile

React Native + Expo (SDK 57) + TypeScript + Expo Router, for iOS and Android. i18n in Spanish and English.

```bash
npm install
npm start                 # local API (EXPO_PUBLIC_API_URL, default http://localhost:8000/api/v1)
npm run start:qa          # points to https://kuulis-qa.top8.uk/api/v1
npm run lint && npm run typecheck && npm test
```

Use your machine's LAN IP in `EXPO_PUBLIC_API_URL` when testing against a local API from a phone.

## Google / Apple sign-in

- Google uses native sign-in (`@react-native-google-signin/google-signin`), which is **not in Expo Go**: there the
  button shows "Disponible en la app instalada". Set `EXPO_PUBLIC_GOOGLE_WEB_CLIENT_ID` (required; it is the
  `aud` the API checks) and `EXPO_PUBLIC_GOOGLE_IOS_CLIENT_ID` (iOS; also adds the URL scheme plugin). Without
  them the button is hidden.
- Apple (`expo-apple-authentication`) is shown on iOS only. In Expo Go the token's `aud` is `host.exp.Exponent`.

## Structure

```
src/
├── app/                  # Expo Router routes
│   ├── _layout.tsx       # providers + auth guard (Stack.Protected)
│   ├── (auth)/           # login, register, forgot-password
│   ├── welcome.tsx       # pick Pasajero / Motorizado (stored per user on the device)
│   └── (app)/            # (tabs): home, notifications, profile · driver/: onboarding steps
├── components/           # design-system UI kit (ui.tsx), icons, tab bar, hero header
├── features/             # passenger and driver screens' building blocks
├── hooks/                # usePushNotifications, useRealtime (WebSocket), useDriver (react-query)
├── i18n/                 # i18next + locales/{es,en}.json
├── lib/                  # api client (JWT + refresh), config, secure storage, types
├── providers/            # AuthProvider, ModeProvider
└── theme/                # Verde Ávila tokens (light/dark), spacing, radii, Plus Jakarta Sans type scale
```

## Environments

`APP_ENV` (`local` | `qa` | `production`) picks the API URL and the app identity in `app.config.ts`, so QA and
production builds can be installed side by side (`uk.top8.kuulis.qa` vs `uk.top8.kuulis`). EAS build profiles in
`eas.json` set it for each build.

## Pending before store builds

See `docs/blockers.md`: Apple Developer and Google Play accounts, EAS project (`npx eas-cli init`, then set
`EAS_PROJECT_ID`), push credentials (APNs key / FCM), final bundle identifiers, icons and splash.
