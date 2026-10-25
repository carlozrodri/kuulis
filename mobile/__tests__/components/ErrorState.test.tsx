import { beforeEach, describe, expect, it, jest } from '@jest/globals';
import { fireEvent, screen } from '@testing-library/react-native';

import { ErrorState } from '@/components/ErrorState';
import { InboxScreen } from '@/features/notifications/InboxScreen';
import i18n from '@/i18n';
import { ApiError } from '@/lib/api';
import { errorKind, isNotFound } from '@/lib/errorKind';

import { renderScreen } from '../../test-utils/render';

const mockApi = jest.fn<(path: string) => Promise<unknown>>();
let mockOffline = false;

jest.mock('@/lib/api', () => ({ ...jest.requireActual<object>('@/lib/api'), api: (...args: [string]) => mockApi(...args) }));
jest.mock('@/hooks/useOnline', () => ({ useIsOffline: () => mockOffline }));
jest.mock('@/features/notifications/useOpenNotification', () => ({ useOpenNotification: () => jest.fn() }));
jest.mock('expo-router', () => ({ router: { push: jest.fn(), back: jest.fn() } }));

describe('errorKind', () => {
  it('tells the phone connection, the server and missing things apart', () => {
    expect(errorKind(new ApiError(500, 'http_500', 'boom'), true)).toBe('offline');
    expect(errorKind(new TypeError('Network request failed'))).toBe('unreachable');
    expect(errorKind(new ApiError(502, 'http_502', 'Bad Gateway'))).toBe('server');
    // Maintenance has its own text (doc 10), not the stock "server" one.
    expect(errorKind(new ApiError(503, 'service_paused', 'paused'))).toBe('generic');
    expect(errorKind(new ApiError(404, 'ride_not_found', 'nope'))).toBe('notFound');
    expect(errorKind(new ApiError(409, 'ride_not_active', 'nope'))).toBe('generic');
    expect(isNotFound(new ApiError(404, 'http_404', ''))).toBe(true);
    expect(isNotFound(new Error('x'))).toBe(false);
  });
});

describe('ErrorState', () => {
  beforeEach(async () => {
    mockOffline = false;
    mockApi.mockReset();
    await i18n.changeLanguage('es');
  });

  it('explains a server failure and tries again', async () => {
    const onRetry = jest.fn(async () => undefined);
    await renderScreen(<ErrorState error={new ApiError(500, 'http_500', 'Internal')} onRetry={onRetry} />);
    expect(screen.getByText(i18n.t('states.server.title'))).toBeTruthy();
    expect(screen.getByText(i18n.t('states.server.body'))).toBeTruthy();
    fireEvent.press(screen.getByText(i18n.t('common.retry')));
    expect(onRetry).toHaveBeenCalledTimes(1);
  });

  it('says the phone is offline whatever the error was', async () => {
    mockOffline = true;
    await renderScreen(<ErrorState error={new TypeError('Network request failed')} />);
    expect(screen.getByText(i18n.t('states.offline.title'))).toBeTruthy();
    expect(screen.queryByText(i18n.t('common.retry'))).toBeNull();
  });

  it('shows the API text when the error has a known code', async () => {
    await renderScreen(<ErrorState inline error={new ApiError(429, 'rate_limited', 'Too many')} onRetry={() => undefined} />);
    expect(screen.getByText(i18n.t('states.generic.title'))).toBeTruthy();
    expect(screen.getByText(i18n.t('errors.rate_limited'))).toBeTruthy();
  });

  it('reads in English too', async () => {
    await i18n.changeLanguage('en');
    await renderScreen(<ErrorState error={new ApiError(404, 'http_404', 'Not Found')} />);
    expect(screen.getByText('We could not find it')).toBeTruthy();
  });
});

describe('notifications inbox', () => {
  beforeEach(async () => {
    mockOffline = false;
    mockApi.mockReset();
    await i18n.changeLanguage('es');
  });

  it('shows the failure instead of "no notifications" when the list could not load', async () => {
    mockApi.mockRejectedValue(new ApiError(503, 'http_503', 'Unavailable'));
    await renderScreen(<InboxScreen />);
    expect(await screen.findByText(i18n.t('states.server.title'))).toBeTruthy();
    expect(screen.queryByText(i18n.t('notifications.empty'))).toBeNull();
  });
});
