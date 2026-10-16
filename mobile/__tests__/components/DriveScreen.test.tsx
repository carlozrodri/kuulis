import { beforeEach, describe, expect, it, jest } from '@jest/globals';
import { act, fireEvent, screen, waitFor } from '@testing-library/react-native';
import { Alert } from 'react-native';

import { DriveScreen } from '@/features/driver/DriveScreen';
import { rideKeys } from '@/hooks/useRides';
import i18n from '@/i18n';
import { outbox } from '@/lib/actionQueue';
import type { Ride } from '@/lib/types';

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
jest.mock('@/components/map/RideMap', () => ({ RideMap: () => null }));
jest.mock('@/features/safety/SosButton', () => ({ SosButton: () => null }));
jest.mock('@/features/safety/SafetySheet', () => ({ SafetySheet: () => null }));
jest.mock('@/features/safety/SafetyTips', () => ({ useFirstRideTips: () => undefined }));
jest.mock('@/hooks/useBootstrap', () => ({ useFlag: () => true }));
jest.mock('@/hooks/useRealtime', () => ({ useRealtime: () => 'open' }));
jest.mock('@/hooks/useLocation', () => ({
  useUserLocation: () => ({ position: { lat: 10.4905, lng: -66.88, accuracy: 8, timestamp: Date.now(), heading: null, speed: null, mocked: false } }),
}));
jest.mock('@/providers/AuthProvider', () => ({ useAuth: () => ({ user: mockUser }) }));
jest.mock('@/providers/ModeProvider', () => ({ useMode: () => ({ mode: 'driver' }) }));
jest.mock('expo-router', () => ({
  router: { dismissTo: jest.fn(), push: jest.fn(), back: jest.fn(), canGoBack: () => true, replace: jest.fn() },
  useLocalSearchParams: () => ({ id: 'r-1' }),
}));

const mockUser = makeUser({ id: DRIVER_ID });
const network = () => new TypeError('Network request failed');

async function renderRide(ride: Ride) {
  const result = await renderScreen(<DriveScreen />);
  result.queryClient.setQueryData(rideKeys.detail(ride.id), ride);
  result.queryClient.setQueryData(rideKeys.active, ride);
  return result;
}

describe('DriveScreen (ride flow, doc 20)', () => {
  beforeEach(async () => {
    await outbox.clear();
    mockApi.mockReset();
    mockToast.mockReset();
    await i18n.changeLanguage('es');
  });

  it('marks "Llegué" and moves to the waiting step', async () => {
    const ride = makeRide();
    mockApi.mockImplementation(async (path) => {
      if (path === '/rides/r-1/arrive') return { ...ride, status: 'driver_arrived', arrived_at: new Date().toISOString() };
      if (path === '/rides/r-1') return ride;
      if (path === '/rides/active') return ride;
      throw new Error(`unexpected ${path}`);
    });
    await renderRide(ride);
    await fireEvent.press(await screen.findByLabelText(i18n.t('drive.action.arrive')));
    await waitFor(() => expect(screen.getByText(i18n.t('drive.stage.waiting', { name: 'Ana' }))).toBeTruthy());
    const call = mockApi.mock.calls.find(([path]) => path === '/rides/r-1/arrive');
    expect(call?.[1]?.headers?.['Idempotency-Key']).toBeTruthy();
  });

  it('without signal at the drop-off it shows "Enviando…" and finishes once when the signal is back', async () => {
    const ride = makeRide({ status: 'in_progress', started_at: new Date().toISOString() });
    let online = false;
    const keys: string[] = [];
    mockApi.mockImplementation(async (path, options) => {
      if (path === '/rides/r-1/complete') {
        keys.push(options?.headers?.['Idempotency-Key'] ?? '');
        if (!online) throw network();
        return { ...ride, status: 'completed', completed_at: new Date().toISOString() };
      }
      if (path === '/rides/r-1' || path === '/rides/active') return ride;
      throw new Error(`unexpected ${path}`);
    });
    jest.spyOn(Alert, 'alert').mockImplementation((_title, _body, buttons) => buttons?.[1]?.onPress?.());

    await renderRide(ride);
    await fireEvent.press(await screen.findByLabelText(i18n.t('drive.action.complete')));
    expect(await screen.findByText(i18n.t('drive.retrying'))).toBeTruthy();
    expect(screen.getByText(i18n.t('signal.gps.good'))).toBeTruthy();

    online = true;
    await act(async () => {
      await outbox.flush(true);
    });
    await waitFor(() => expect(screen.queryByText(i18n.t('drive.retrying'))).toBeNull());
    expect(new Set(keys).size).toBe(1);
    expect(keys.length).toBe(2);
    expect(mockToast).not.toHaveBeenCalledWith(expect.anything(), 'danger');
  });

  it('shows why the API refused a step', async () => {
    const ride = makeRide();
    const { ApiError } = jest.requireActual<typeof import('@/lib/api')>('@/lib/api');
    mockApi.mockImplementation(async (path) => {
      if (path === '/rides/r-1/arrive') throw new ApiError(409, 'ride_invalid_transition', 'x');
      return ride;
    });
    await renderRide(ride);
    await fireEvent.press(await screen.findByLabelText(i18n.t('drive.action.arrive')));
    await waitFor(() => expect(mockToast).toHaveBeenCalledWith(i18n.t('errors.ride_invalid_transition'), 'danger'));
  });
});
