import { afterEach, beforeEach, describe, expect, it, jest } from '@jest/globals';
import type { QueryClient } from '@tanstack/react-query';
import { cleanup, fireEvent, screen, waitFor } from '@testing-library/react-native';

import { SavedShortcuts } from '@/features/passenger/SavedShortcuts';
import { RideNote } from '@/features/ride/components';
import { QuoteScreen } from '@/features/ride/QuoteScreen';
import { rideDraft } from '@/features/ride/store';
import i18n from '@/i18n';
import type { Quote, SavedPlace } from '@/lib/types';

import { makeRide, makeUser } from '../../test-utils/fixtures';
import { renderScreen as render } from '../../test-utils/render';

const mockApi = jest.fn<(path: string, options?: { body?: unknown; query?: Record<string, unknown> }) => Promise<unknown>>();
const mockPush = jest.fn();

jest.mock('@/lib/api', () => ({
  ...jest.requireActual<object>('@/lib/api'),
  api: (...args: [string]) => mockApi(...args),
  apiOnce: (...args: [string]) => mockApi(...args),
}));
jest.mock('@/lib/actionQueue', () => {
  const { createOutbox } = jest.requireActual<typeof import('@/lib/outbox')>('@/lib/outbox');
  return { outbox: createOutbox({ send: async () => undefined, read: async () => null, write: async () => undefined }) };
});
jest.mock('@/lib/analytics', () => ({ track: jest.fn() }));
jest.mock('@/components/Toast', () => ({ showToast: jest.fn() }));
jest.mock('@/components/map/RideMap', () => ({ RideMap: () => null }));
jest.mock('@/hooks/useRealtime', () => ({ useRealtime: () => 'open', useRealtimeEvent: () => undefined }));
jest.mock('@/hooks/useBootstrap', () => ({ useBootstrap: () => ({ data: undefined }), useFlag: () => true }));
jest.mock('@/providers/AuthProvider', () => ({ useAuth: () => ({ user: mockUser, refreshUser: async () => undefined }) }));
jest.mock('expo-router', () => ({
  router: { push: (...args: unknown[]) => mockPush(...args), back: jest.fn(), replace: jest.fn(), dismissTo: jest.fn() },
}));

const mockUser = makeUser();
const PICKUP = { lat: 10.49, lng: -66.88, address: 'Plaza Altamira' };
const DROPOFF = { lat: 10.5, lng: -66.85, address: 'Los Dos Caminos' };

const QUOTE: Quote = {
  quote_id: 'q-1',
  vehicle_type: 'moto',
  pickup: PICKUP,
  dropoff: DROPOFF,
  distance_m: 3200,
  duration_s: 600,
  fare: '3.00',
  surge_multiplier: '1.00',
  polyline: null,
  expires_at: new Date(Date.now() + 120_000).toISOString(),
  surge_reason: null,
  surge_zone: null,
};

const place = (fields: Partial<SavedPlace>): SavedPlace => ({
  id: 'p-1',
  kind: 'home',
  label: '',
  lat: 10.48,
  lng: -66.86,
  address: 'Residencias El Parque, Chacao',
  updated_at: '2026-10-17T10:00:00Z',
  ...fields,
});

const clients: QueryClient[] = [];
async function renderScreen(ui: Parameters<typeof render>[0]) {
  const result = await render(ui);
  clients.push(result.queryClient);
  return result;
}

describe('doc 23: rider improvements', () => {
  afterEach(async () => {
    await cleanup();
    clients.splice(0).forEach((client) => client.clear());
  });

  beforeEach(async () => {
    mockApi.mockReset();
    mockPush.mockReset();
    rideDraft.set({ pickup: PICKUP, pickupIsCurrent: false, dropoff: DROPOFF, paymentMethod: 'cash_usd', promoCode: null, note: '', rider: null });
    await i18n.changeLanguage('es');
  });

  it('requests for someone else with a note for the driver', async () => {
    mockApi.mockImplementation(async (path) => {
      if (path === '/rides/quote') return QUOTE;
      if (path === '/zones/check') return { city: 'Caracas', restricted: null, suggestion: null, surge: null };
      if (path === '/users/me/trusted-contacts') return [{ id: 'c-1', name: 'Mamá', phone: '+584241234567' }];
      if (path === '/rides') return makeRide({ id: 'r-9', status: 'searching' });
      return {};
    });
    await renderScreen(<QuoteScreen />);
    expect(await screen.findByText('$3.00')).toBeTruthy();

    await fireEvent.press(screen.getByRole('button', { name: /Para mí/ }));
    // A trusted contact fills both fields; a bad phone is refused first.
    await fireEvent.changeText(screen.getByLabelText(i18n.t('quote.rider.name')), 'María José');
    await fireEvent.changeText(screen.getByLabelText(i18n.t('quote.rider.phone')), '123');
    await fireEvent.press(screen.getByRole('button', { name: i18n.t('quote.rider.save') }));
    expect(screen.getByText(i18n.t('quote.rider.phoneInvalid'))).toBeTruthy();
    await fireEvent.press(await screen.findByRole('button', { name: 'Mamá' }));
    await fireEvent.changeText(screen.getByLabelText(i18n.t('quote.rider.name')), 'María José');
    await fireEvent.press(screen.getByRole('button', { name: i18n.t('quote.rider.save') }));
    expect(rideDraft.get().rider).toEqual({ name: 'María José', phone: '+584241234567' });
    expect(screen.getByText('Para María José')).toBeTruthy();

    await fireEvent.press(screen.getByRole('button', { name: /Nota para el motorizado\./ }));
    await fireEvent.changeText(screen.getByLabelText(i18n.t('quote.note.title')), '  Portón azul  ');
    await fireEvent.press(screen.getByRole('button', { name: i18n.t('quote.note.save') }));
    expect(screen.getByText('Portón azul')).toBeTruthy();

    await fireEvent.press(screen.getByRole('button', { name: /Pedir moto/i }));
    await waitFor(() => expect(mockApi).toHaveBeenCalledWith('/rides', expect.anything()));
    const call = mockApi.mock.calls.find(([path]) => path === '/rides');
    expect(call?.[1]?.body).toEqual({
      quote_id: 'q-1',
      payment_method: 'cash_usd',
      note: 'Portón azul',
      rider: { name: 'María José', phone: '+584241234567' },
    });
    // The next request starts clean.
    expect(rideDraft.get().note).toBe('');
    expect(rideDraft.get().rider).toBeNull();
  });

  it('home shortcuts go to the price for Casa and invite to add Trabajo', async () => {
    mockApi.mockImplementation(async (path) => (path === '/users/me/places' ? [place({})] : {}));
    await renderScreen(<SavedShortcuts />);
    await fireEvent.press(await screen.findByRole('button', { name: 'Casa' }));
    expect(rideDraft.get().dropoff).toEqual({ lat: 10.48, lng: -66.86, address: 'Residencias El Parque, Chacao' });
    expect(mockPush).toHaveBeenCalledWith('/ride/quote');

    await fireEvent.press(screen.getByRole('button', { name: i18n.t('profile.saved.add_work') }));
    expect(mockPush).toHaveBeenCalledWith({ pathname: '/profile/place', params: { kind: 'work' } });
  });

  it('shows who rides and the note to the driver', async () => {
    await renderScreen(<RideNote ride={{ rider_name: 'María José', note: 'Portón azul' }} />);
    expect(screen.getByText('Viaja: María José')).toBeTruthy();
    expect(screen.getByText('“Portón azul”')).toBeTruthy();
  });
});
