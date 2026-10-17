import { beforeEach, describe, expect, it, jest } from '@jest/globals';
import { act, fireEvent, screen, waitFor } from '@testing-library/react-native';

import { DriverDashboard } from '@/features/driver/DriverDashboard';
import { demandLayer } from '@/hooks/useDemand';
import i18n from '@/i18n';
import type { DemandSnapshot } from '@/lib/zones';

import { DRIVER_ID, makeUser } from '../../test-utils/fixtures';
import { renderScreen } from '../../test-utils/render';

type MapProps = { areas?: { id: string; fill: string }[]; focus?: { point: { lat: number; lng: number }; key: number } | null };

const mockApi = jest.fn<(path: string, options?: { query?: Record<string, unknown> }) => Promise<unknown>>();
const mockMap = jest.fn<(props: MapProps) => null>(() => null);
const mockHandlers: Record<string, (data: unknown) => void> = {};
const mockStorage = new Map<string, string>();

jest.mock('@/lib/api', () => ({ ...jest.requireActual<object>('@/lib/api'), api: (...args: [string]) => mockApi(...args) }));
jest.mock('@/lib/storage', () => ({
  secureStorage: {
    get: async (key: string) => mockStorage.get(key) ?? null,
    set: async (key: string, value: string) => void mockStorage.set(key, value),
    remove: async (key: string) => void mockStorage.delete(key),
  },
}));
jest.mock('@/components/map/RideMap', () => ({ RideMap: (props: MapProps) => mockMap(props) }));
jest.mock('@/components/Toast', () => ({ showToast: jest.fn() }));
jest.mock('@/hooks/useRealtime', () => ({
  useRealtime: () => 'open',
  useRealtimeEvent: (event: string, handler: (data: unknown) => void) => {
    mockHandlers[event] = handler;
  },
}));
jest.mock('@/hooks/useLocation', () => ({
  useUserLocation: () => ({ permission: 'granted', position: { lat: 10.4905, lng: -66.88, accuracy: 8, mocked: false } }),
  getFreshPosition: async () => null,
  requestLocationPermission: async () => true,
}));
jest.mock('@/hooks/useBootstrap', () => ({ useBootstrap: () => ({ data: undefined }), useFlag: () => true }));
jest.mock('@/providers/AuthProvider', () => ({ useAuth: () => ({ user: mockUser, refreshUser: async () => undefined }) }));
jest.mock('@/features/control/AnnouncementBanners', () => ({ AnnouncementBanners: () => null }));
jest.mock('@/features/update/UpdateBanner', () => ({ UpdateBanner: () => null }));
jest.mock('@/features/wallet/SubscriptionCard', () => ({ EarningsCard: () => null, goToTopUp: jest.fn() }));
jest.mock('@/lib/backgroundLocation', () => {
  const { createStore } = jest.requireActual<typeof import('@/lib/store')>('@/lib/store');
  return { backgroundLocationActive: createStore(true) };
});
jest.mock('expo-router', () => ({ router: { push: jest.fn(), back: jest.fn(), dismissTo: jest.fn() } }));

const mockUser = makeUser({ id: DRIVER_ID, consents: ['background_location'] });

const hexagon: [number, number][] = [
  [10.49, -66.85],
  [10.495, -66.845],
  [10.5, -66.85],
  [10.5, -66.855],
  [10.495, -66.86],
  [10.49, -66.855],
];

const SNAPSHOT: DemandSnapshot = {
  enabled: true,
  updated_at: '2026-10-17T12:00:00Z',
  window_minutes: 15,
  cells: [
    { cell: 'hot', boundary: hexagon, center: [10.495, -66.85], level: 3, requests: 6, unmatched: 2, name: 'Chacao' },
    { cell: 'warm', boundary: hexagon, center: [10.495, -66.85], level: 2, requests: 3, unmatched: 0 },
  ],
  hot: { name: 'Chacao', level: 3, distance_m: 1200, center: [10.495, -66.853] },
};

function routes(demand: () => DemandSnapshot) {
  mockApi.mockImplementation(async (path) => {
    if (path === '/drivers/me/demand') return demand();
    if (path === '/drivers/me/state') return { online: false };
    if (path === '/rides/active') return null;
    if (path === '/drivers/me') return { status: 'approved', verification: null };
    if (path === '/drivers/me/quality') return { pause: null };
    if (path === '/config/public') return {};
    return null;
  });
}

const demandCalls = () => mockApi.mock.calls.filter(([path]) => path === '/drivers/me/demand');
const lastMap = () => mockMap.mock.calls[mockMap.mock.calls.length - 1]?.[0] ?? {};
const layerSwitch = () => screen.findByRole('switch', { name: i18n.t('demand.layer') });

describe('driver home: demand layer (doc 21)', () => {
  beforeEach(async () => {
    mockApi.mockReset();
    mockMap.mockClear();
    mockStorage.clear();
    demandLayer.set(false);
    await i18n.changeLanguage('es');
  });

  it('draws the cells, the legend and the hot spot banner once the layer is on, and remembers it', async () => {
    routes(() => SNAPSHOT);
    await renderScreen(<DriverDashboard />);
    // Off: the switch shows, nothing is drawn.
    await fireEvent.press(await layerSwitch());
    await waitFor(() => expect(lastMap().areas).toHaveLength(2));
    expect(demandCalls()[0][1]?.query).toEqual({ lat: 10.4905, lng: -66.88 });
    expect(lastMap().areas?.map((area) => area.id)).toEqual(['hot', 'warm']);
    expect(screen.getByText(i18n.t('demand.level.3'))).toBeTruthy();
    expect(mockStorage.get('kuulis.demand_layer')).toBe('1');

    const banner = screen.getByRole('button', { name: `${i18n.t('demand.hot', { name: 'Chacao' })}, ${i18n.t('demand.away', { distance: '1,2 km' })}` });
    await fireEvent.press(banner);
    expect(lastMap().focus?.point).toEqual({ lat: 10.495, lng: -66.853 });

    // Off again: the map is clean.
    await fireEvent.press(await layerSwitch());
    await waitFor(() => expect(lastMap().areas).toEqual([]));
    expect(screen.queryByText(i18n.t('demand.hot', { name: 'Chacao' }))).toBeNull();
    expect(mockStorage.get('kuulis.demand_layer')).toBe('0');
  });

  it('reads the map again right away on demand.updated while the layer is on', async () => {
    demandLayer.set(true);
    let snapshot: DemandSnapshot = { ...SNAPSHOT, cells: [], hot: null };
    routes(() => snapshot);
    await renderScreen(<DriverDashboard />);
    await waitFor(() => expect(demandCalls().length).toBeGreaterThan(0));
    await waitFor(() => expect(lastMap().areas).toEqual([]));
    snapshot = SNAPSHOT;
    const before = demandCalls().length;
    await act(async () => mockHandlers['demand.updated']?.({ updated_at: '2026-10-17T12:01:00Z' }));
    await waitFor(() => expect(demandCalls().length).toBe(before + 1));
    await waitFor(() => expect(lastMap().areas).toHaveLength(2));
    expect(await screen.findByText(i18n.t('demand.hot', { name: 'Chacao' }))).toBeTruthy();
  });

  it('hides the switch when demand is switched off', async () => {
    routes(() => ({ enabled: false, cells: [] }));
    await renderScreen(<DriverDashboard />);
    await waitFor(() => expect(demandCalls().length).toBe(1));
    expect(screen.queryByRole('switch', { name: i18n.t('demand.layer') })).toBeNull();
    expect(lastMap().areas).toEqual([]);
  });

  it('a driver who left the layer on sees the switch disabled when demand is switched off', async () => {
    demandLayer.set(true);
    routes(() => ({ enabled: false, cells: [] }));
    await renderScreen(<DriverDashboard />);
    await waitFor(() => expect(demandCalls().length).toBeGreaterThan(0));
    await waitFor(async () => expect((await layerSwitch()).props.accessibilityState).toMatchObject({ disabled: true, checked: false }));
    expect(screen.queryByText(i18n.t('demand.level.3'))).toBeNull();
  });
});
