import { beforeEach, describe, expect, it, jest } from '@jest/globals';
import { QueryClient } from '@tanstack/react-query';
import { persistQueryClientRestore, persistQueryClientSave } from '@tanstack/react-query-persist-client';
import { screen } from '@testing-library/react-native';

import { WalletScreen } from '@/features/driver/WalletScreen';
import i18n from '@/i18n';
import { formatAmount } from '@/lib/money';
import { createFilePersister, PERSIST_BUSTER, shouldPersistQuery } from '@/lib/queryPersistence';

import { renderScreen } from '../../test-utils/render';

const mockApi = jest.fn<(path: string) => Promise<unknown>>();

jest.mock('@/lib/api', () => ({ ...jest.requireActual<object>('@/lib/api'), api: (...args: [string]) => mockApi(...args) }));
jest.mock('@/hooks/useBootstrap', () => ({ useFlag: () => true }));
jest.mock('expo-router', () => ({ router: { push: jest.fn(), back: jest.fn() } }));

const page = <T,>(items: T[]) => ({ items, total: items.length, limit: 20, offset: 0 });
const ONLINE: Record<string, unknown> = {
  '/wallet/me': { balance: '12.50', currency: 'USDT' },
  '/wallet/me/entries': page([
    {
      id: 'e1',
      kind: 'top_up',
      amount: '10.00',
      balance_after: '12.50',
      ride_id: null,
      description: null,
      details: { method: 'binance', reference: '123' },
      created_at: '2026-10-15T15:00:00Z',
    },
  ]),
  '/wallet/me/top-ups': page([]),
  '/wallet/me/subscription': null,
};

const client = () => new QueryClient({ defaultOptions: { queries: { retry: false, gcTime: Infinity } } });

describe('wallet without signal (doc 20)', () => {
  beforeEach(async () => {
    mockApi.mockReset();
    await i18n.changeLanguage('es');
  });

  it('shows the last balance and movements saved on the phone', async () => {
    let contents: string | null = null;
    const persister = createFilePersister(
      { read: async () => contents, write: async (_name, next) => void (contents = next) },
      0,
    );

    // Online: the screen loads and the cache is saved.
    mockApi.mockImplementation(async (path) => {
      if (path in ONLINE) return ONLINE[path];
      throw new Error(`unexpected ${path}`);
    });
    const online = await renderScreen(<WalletScreen />, client());
    expect(await screen.findAllByText(new RegExp(formatAmount('12.50').replace('.', '\\.')))).not.toHaveLength(0);
    await persistQueryClientSave({
      queryClient: online.queryClient,
      persister,
      buster: PERSIST_BUSTER,
      dehydrateOptions: { shouldDehydrateQuery: shouldPersistQuery },
    });
    await persister.flush();
    online.unmount();

    // Next start without signal: every request fails, the saved copy is shown.
    mockApi.mockImplementation(async () => Promise.reject(new TypeError('Network request failed')));
    const offline = client();
    await persistQueryClientRestore({ queryClient: offline, persister, buster: PERSIST_BUSTER });
    await renderScreen(<WalletScreen />, offline);
    expect(await screen.findAllByText(new RegExp(formatAmount('12.50').replace('.', '\\.')))).not.toHaveLength(0);
    expect(screen.getAllByText(/10[.,]00/).length).toBeGreaterThan(0);
  });
});
