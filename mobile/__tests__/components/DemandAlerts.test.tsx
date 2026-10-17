import { beforeEach, describe, expect, it, jest } from '@jest/globals';
import { fireEvent, screen, waitFor } from '@testing-library/react-native';

import { NotificationSettingsScreen } from '@/features/notifications/NotificationSettingsScreen';
import i18n from '@/i18n';

import { renderScreen } from '../../test-utils/render';

const mockApi = jest.fn<(path: string, options?: { method?: string; body?: unknown }) => Promise<unknown>>();
let mockMode: 'driver' | 'passenger' = 'driver';

jest.mock('@/lib/api', () => ({ ...jest.requireActual<object>('@/lib/api'), api: (...args: [string]) => mockApi(...args) }));
jest.mock('@/components/Toast', () => ({ showToast: jest.fn() }));
jest.mock('@/providers/ModeProvider', () => ({ useMode: () => ({ mode: mockMode }) }));
jest.mock('expo-router', () => ({ router: { back: jest.fn(), canGoBack: () => true, push: jest.fn() } }));

const PREFS = {
  marketing_push: true,
  marketing_email: false,
  quiet_start: '21:00',
  quiet_end: '08:00',
  default_quiet_start: '21:00',
  default_quiet_end: '08:00',
  demand_alerts: true,
};

describe('notification settings: demand alerts (doc 21)', () => {
  beforeEach(async () => {
    mockApi.mockReset();
    mockApi.mockImplementation(async (path, options) =>
      options?.method === 'PUT' ? { ...PREFS, ...(options.body as object) } : PREFS,
    );
    await i18n.changeLanguage('es');
  });

  it('a driver can turn the demand alerts off (PUT with only that field)', async () => {
    mockMode = 'driver';
    await renderScreen(<NotificationSettingsScreen />);
    const toggle = await screen.findByRole('switch', { name: i18n.t('notifications.settings.demandAlerts') });
    expect(toggle.props.accessibilityState).toMatchObject({ checked: true });
    await fireEvent.press(toggle);
    await waitFor(() =>
      expect(mockApi).toHaveBeenCalledWith('/notifications/preferences', { method: 'PUT', body: { demand_alerts: false } }),
    );
    await waitFor(() =>
      expect(screen.getByRole('switch', { name: i18n.t('notifications.settings.demandAlerts') }).props.accessibilityState).toMatchObject({
        checked: false,
      }),
    );
  });

  it('passengers do not see it', async () => {
    mockMode = 'passenger';
    await renderScreen(<NotificationSettingsScreen />);
    expect(await screen.findByText(i18n.t('notifications.settings.marketingPush'))).toBeTruthy();
    expect(screen.queryByText(i18n.t('notifications.settings.demandAlerts'))).toBeNull();
  });
});
