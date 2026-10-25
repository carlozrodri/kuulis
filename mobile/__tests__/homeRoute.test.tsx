import { describe, expect, it } from '@jest/globals';
import { Stack } from 'expo-router';
import { renderRouter, screen } from 'expo-router/testing-library';
import { Text } from 'react-native';

import { homeRoute } from '@/lib/homeRoute';

/** The root layout's guards (src/app/_layout.tsx), with each closed guard redirecting to homeRoute(). */
function routes(state: { signedIn: boolean; pendingLegal: boolean; hasMode: boolean }) {
  const { signedIn, pendingLegal, hasMode } = state;
  const home = homeRoute(state);
  const Root = () => (
    <Stack screenOptions={{ headerShown: false }}>
      <Stack.Protected guard={!signedIn} redirectTo={home}>
        <Stack.Screen name="(auth)" />
      </Stack.Protected>
      <Stack.Protected guard={signedIn && pendingLegal} redirectTo={home}>
        <Stack.Screen name="accept-terms" />
      </Stack.Protected>
      <Stack.Protected guard={signedIn && !pendingLegal && !hasMode} redirectTo={home}>
        <Stack.Screen name="welcome" />
      </Stack.Protected>
      <Stack.Protected guard={signedIn && !pendingLegal && hasMode} redirectTo={home}>
        <Stack.Screen name="(app)" />
      </Stack.Protected>
    </Stack>
  );
  return {
    _layout: Root,
    '(auth)/_layout': { default: () => <Stack />, unstable_settings: { anchor: 'login' } },
    '(auth)/login': () => <Text>login</Text>,
    '(auth)/register': () => <Text>register</Text>,
    'accept-terms': () => <Text>accept-terms</Text>,
    welcome: () => <Text>welcome</Text>,
    '(app)/_layout': { default: () => <Stack />, unstable_settings: { anchor: '(tabs)' } },
    '(app)/(tabs)/_layout': () => <Stack />,
    '(app)/(tabs)/index': () => <Text>home</Text>,
  };
}

describe('opening the app at kuulis:/// (Expo Router 58)', () => {
  it.each([
    [{ signedIn: false, pendingLegal: false, hasMode: false }, 'login'],
    [{ signedIn: true, pendingLegal: true, hasMode: true }, 'accept-terms'],
    [{ signedIn: true, pendingLegal: false, hasMode: false }, 'welcome'],
    [{ signedIn: true, pendingLegal: false, hasMode: true }, 'home'],
  ])('%o opens %s instead of an unmatched route', async (state, expected) => {
    await renderRouter(routes(state) as never, { initialUrl: '/' });
    expect(screen.getByText(expected)).toBeTruthy();
  });
});
