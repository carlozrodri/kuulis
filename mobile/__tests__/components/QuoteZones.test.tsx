import { afterEach, beforeEach, describe, expect, it, jest } from '@jest/globals';
import type { QueryClient } from '@tanstack/react-query';
import { cleanup, fireEvent, screen, waitFor } from '@testing-library/react-native';

import { QuoteScreen } from '@/features/ride/QuoteScreen';
import { rideDraft } from '@/features/ride/store';
import i18n from '@/i18n';
import type { Quote } from '@/lib/types';
import type { ZoneCheck } from '@/lib/zones';

import { makeUser } from '../../test-utils/fixtures';
import { renderScreen as render } from '../../test-utils/render';

const mockApi = jest.fn<(path: string, options?: { body?: unknown; query?: Record<string, unknown> }) => Promise<unknown>>();

jest.mock('@/lib/api', () => ({ ...jest.requireActual<object>('@/lib/api'), api: (...args: [string]) => mockApi(...args) }));
// The real outbox keeps a retry timer alive (Jest would not exit); rides are never queued anyway (doc 20).
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
jest.mock('expo-router', () => ({ router: { push: jest.fn(), back: jest.fn(), replace: jest.fn(), dismissTo: jest.fn() } }));

const mockUser = makeUser();
const PICKUP = { lat: 10.6012, lng: -66.991, address: 'Aeropuerto, salidas' };
const DROPOFF = { lat: 10.5, lng: -66.85, address: 'Los Dos Caminos' };
const GATE = { name: 'Entrada Norte', lat: 10.6031, lng: -66.989, distance_m: 180, zone: 'Recogida aeropuerto' };

const quote = (fields: Partial<Quote> = {}): Quote => ({
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
  ...fields,
});

// useQuote sets its own gcTime (5 min): its timer would keep Jest alive, so every cache is cleared after a test.
const clients: QueryClient[] = [];
async function renderScreen(ui: Parameters<typeof render>[0]) {
  const result = await render(ui);
  clients.push(result.queryClient);
  return result;
}

const check = (fields: Partial<ZoneCheck> = {}): ZoneCheck => ({ city: 'Caracas', restricted: null, suggestion: null, surge: null, ...fields });

function routes(handlers: { check: (lat: number) => ZoneCheck; quote: (lat: number) => Quote }) {
  mockApi.mockImplementation(async (path, options) => {
    if (path === '/zones/check') return handlers.check(Number(options?.query?.lat));
    if (path === '/rides/quote') return handlers.quote((options?.body as { pickup: { lat: number } }).pickup.lat);
    if (path === '/config/public') return {};
    return null;
  });
}

describe('quote: zones (doc 21)', () => {
  afterEach(async () => {
    // Unmount first: removing the last observer schedules the garbage-collection timer that clear() cancels.
    await cleanup();
    clients.splice(0).forEach((client) => client.clear());
  });

  beforeEach(async () => {
    mockApi.mockReset();
    rideDraft.set({ pickup: PICKUP, pickupIsCurrent: false, dropoff: DROPOFF, paymentMethod: 'cash_usd', promoCode: null, note: '', rider: null });
    await i18n.changeLanguage('es');
  });

  it('warns about a restricted pickup and moves it to the suggested point with "Usar"', async () => {
    const { ApiError } = jest.requireActual<typeof import('@/lib/api')>('@/lib/api');
    routes({
      check: (lat) =>
        lat === PICKUP.lat
          ? check({ restricted: { zone: 'Aeropuerto', message: { es: 'Las motos esperan en la Entrada Norte.', en: '' } }, suggestion: GATE })
          : check(),
      quote: (lat) => {
        if (lat === PICKUP.lat) throw new ApiError(422, 'pickup_restricted', 'x', { zone: 'Aeropuerto', suggestion: GATE });
        return quote({ pickup: { ...GATE, address: GATE.name } });
      },
    });
    await renderScreen(<QuoteScreen />);

    expect(await screen.findByText(i18n.t('zones.restrictedTitle'))).toBeTruthy();
    expect(await screen.findByText('Las motos esperan en la Entrada Norte.')).toBeTruthy();
    await fireEvent.press(screen.getByRole('button', { name: i18n.t('zones.use', { name: 'Entrada Norte' }) }));

    expect(rideDraft.get().pickup).toEqual({ lat: GATE.lat, lng: GATE.lng, address: 'Entrada Norte' });
    await waitFor(() => expect(screen.queryByText(i18n.t('zones.restrictedTitle'))).toBeNull());
    expect(await screen.findByText('$3.00')).toBeTruthy();
  });

  it('falls back to the Spanish zone message in English, and to the generic text without one', async () => {
    await i18n.changeLanguage('en');
    const { ApiError } = jest.requireActual<typeof import('@/lib/api')>('@/lib/api');
    routes({
      check: () => {
        throw new TypeError('Network request failed');
      },
      quote: () => {
        throw new ApiError(422, 'pickup_restricted', 'x', { zone: 'Aeropuerto', message: { es: 'Solo en la entrada', en: '' }, suggestion: null });
      },
    });
    await renderScreen(<QuoteScreen />);
    expect(await screen.findByText(i18n.t('zones.restrictedTitle'))).toBeTruthy();
    expect(screen.getByText('Solo en la entrada')).toBeTruthy();
    expect(screen.queryByRole('button', { name: /^Use / })).toBeNull();
    expect(screen.getByRole('button', { name: i18n.t('quote.changePickup') })).toBeTruthy();
  });

  it('suggests a nearby pickup point without blocking the quote', async () => {
    routes({ check: () => check({ suggestion: { ...GATE, distance_m: 120 } }), quote: () => quote() });
    await renderScreen(<QuoteScreen />);
    expect(await screen.findByText(i18n.t('zones.suggested', { name: 'Entrada Norte', distance: '120 m' }))).toBeTruthy();
    expect(screen.getByText('Punto de recogida sugerido: Entrada Norte (a 120 m)')).toBeTruthy();
    expect(screen.getByRole('button', { name: 'Usar Entrada Norte' })).toBeTruthy();
    expect(screen.queryByText(i18n.t('zones.restrictedTitle'))).toBeNull();
  });

  it('says why the price is higher in a surge zone, and keeps the badge for other surcharges', async () => {
    routes({ check: () => check(), quote: () => quote({ surge_multiplier: '1.20', surge_reason: 'zone', surge_zone: 'Las Mercedes' }) });
    const first = await renderScreen(<QuoteScreen />);
    expect(await screen.findByText('Alta demanda en esta zona: +20 %')).toBeTruthy();
    expect(screen.queryByText(i18n.t('quote.surge', { value: '×1.2' }))).toBeNull();
    await first.unmount();

    routes({ check: () => check(), quote: () => quote({ quote_id: 'q-2', surge_multiplier: '1.30', surge_reason: 'time' }) });
    rideDraft.set((draft) => ({ ...draft, dropoff: { ...DROPOFF, lat: 10.51 } }));
    await renderScreen(<QuoteScreen />);
    expect(await screen.findByText(i18n.t('quote.surge', { value: '×1.3' }))).toBeTruthy();
    expect(screen.queryByText(/Alta demanda en esta zona/)).toBeNull();
  });

  it('says a restricted drop-off with the zone message', async () => {
    const { ApiError } = jest.requireActual<typeof import('@/lib/api')>('@/lib/api');
    routes({
      check: () => check(),
      quote: () => {
        throw new ApiError(422, 'dropoff_restricted', 'x', { zone: 'Fuerte Tiuna', message: { es: 'Zona militar: no se deja a nadie aquí.', en: '' } });
      },
    });
    await renderScreen(<QuoteScreen />);
    expect(await screen.findByText(i18n.t('zones.dropoffTitle'))).toBeTruthy();
    expect(screen.getByText('Zona militar: no se deja a nadie aquí.')).toBeTruthy();
  });
});
