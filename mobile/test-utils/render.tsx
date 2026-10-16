import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { render } from '@testing-library/react-native';
import type { ReactElement } from 'react';
import { SafeAreaProvider } from 'react-native-safe-area-context';

/** Renders a screen with a fresh React Query cache (no retries) and safe-area insets, for component tests. */
// gcTime Infinity: no garbage-collection timers left running after a test (Jest would not exit).
const testClient = () =>
  new QueryClient({
    defaultOptions: { queries: { retry: false, gcTime: Infinity }, mutations: { retry: false, gcTime: Infinity } },
  });

export async function renderScreen(ui: ReactElement, queryClient = testClient()) {
  const metrics = { frame: { x: 0, y: 0, width: 390, height: 844 }, insets: { top: 0, left: 0, right: 0, bottom: 0 } };
  return {
    queryClient,
    ...(await render(
      <SafeAreaProvider initialMetrics={metrics}>
        <QueryClientProvider client={queryClient}>{ui}</QueryClientProvider>
      </SafeAreaProvider>,
    )),
  };
}
