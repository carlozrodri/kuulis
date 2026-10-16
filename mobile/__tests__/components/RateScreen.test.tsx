import { beforeEach, describe, expect, it, jest } from '@jest/globals';
import { fireEvent, screen, waitFor } from '@testing-library/react-native';

import { RateScreen } from '@/features/ride/RateScreen';
import i18n from '@/i18n';
import { outbox } from '@/lib/actionQueue';

import { DRIVER_ID, makeRide, makeUser } from '../../test-utils/fixtures';
import { renderScreen } from '../../test-utils/render';

const mockApi = jest.fn<(path: string, options?: { body?: unknown; headers?: Record<string, string> }) => Promise<unknown>>();
const mockToast = jest.fn();

jest.mock('@/lib/api', () => ({ ...jest.requireActual<object>('@/lib/api'), api: (...args: [string]) => mockApi(...args) }));
jest.mock('@/lib/actionQueue', () => {
  const { createOutbox } = jest.requireActual<typeof import('@/lib/outbox')>('@/lib/outbox');
  return {
    outbox: createOutbox({
      send: (item) => mockApi(item.path, { body: item.body, headers: { 'Idempotency-Key': item.id } }),
      read: async () => null,
      write: async () => undefined,
    }),
  };
});
jest.mock('@/components/Toast', () => ({ showToast: (...args: unknown[]) => mockToast(...args) }));
jest.mock('@/providers/AuthProvider', () => ({ useAuth: () => ({ user: mockUser }) }));
jest.mock('@/providers/ModeProvider', () => ({ useMode: () => ({ mode: 'passenger' }) }));
jest.mock('expo-router', () => ({
  router: { dismissTo: jest.fn(), push: jest.fn(), back: jest.fn() },
  useFocusEffect: () => undefined,
}));

const mockUser = makeUser();
const completed = makeRide({ status: 'completed', completed_at: '2026-10-16T12:20:00Z' });

function routes(rating: () => Promise<unknown>) {
  mockApi.mockImplementation(async (path) => {
    if (path === '/rides/pending-rating') return completed;
    if (path === `/rides/${completed.id}/rating`) return rating();
    throw new Error(`unexpected ${path}`);
  });
}

describe('RateScreen', () => {
  beforeEach(async () => {
    await outbox.clear();
    mockApi.mockReset();
    mockToast.mockReset();
    void i18n.changeLanguage('es');
  });

  it('sends the rating once with an Idempotency-Key', async () => {
    routes(async () => ({ ...completed, my_rating: { stars: 5, tags: [] } }));
    await renderScreen(<RateScreen />);
    expect(await screen.findByText(/Luis/)).toBeTruthy();
    expect(completed.driver?.id).toBe(DRIVER_ID);

    await fireEvent.press(screen.getByLabelText(i18n.t('rating.starN', { count: 5 })));
    await fireEvent.press(screen.getByLabelText(i18n.t('rating.submit')));

    await waitFor(() => expect(mockToast).toHaveBeenCalledWith(i18n.t('rating.thanks'), 'success'));
    const call = mockApi.mock.calls.find(([path]) => path.endsWith('/rating'));
    expect(call?.[1]?.body).toEqual({ stars: 5, tags: [] });
    expect(call?.[1]?.headers?.['Idempotency-Key']).toMatch(/^[0-9a-f-]{36}$/);
  });

  it('without signal it says the rating will be sent later', async () => {
    routes(async () => Promise.reject(new TypeError('Network request failed')));
    await renderScreen(<RateScreen />);
    await fireEvent.press(await screen.findByLabelText(i18n.t('rating.starN', { count: 4 })));
    await fireEvent.press(screen.getByLabelText(i18n.t('rating.submit')));
    await waitFor(() => expect(mockToast).toHaveBeenCalledWith(i18n.t('offline.ratingQueued'), 'success'), { timeout: 8000 });
  }, 10_000);

  it('shows the API refusal', async () => {
    const { ApiError } = jest.requireActual<typeof import('@/lib/api')>('@/lib/api');
    routes(async () => Promise.reject(new ApiError(409, 'ride_not_completed', 'x')));
    await renderScreen(<RateScreen />);
    await fireEvent.press(await screen.findByLabelText(i18n.t('rating.starN', { count: 3 })));
    await fireEvent.press(screen.getByLabelText(i18n.t('rating.submit')));
    await waitFor(() => expect(mockToast).toHaveBeenCalledWith(i18n.t('errors.ride_not_completed'), 'danger'));
  });
});
