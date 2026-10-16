import { beforeEach, describe, expect, it, jest } from '@jest/globals';
import { fireEvent, screen, waitFor } from '@testing-library/react-native';

import PersonalStep from '@/app/(app)/driver/personal';
import i18n from '@/i18n';

import { renderScreen } from '../../test-utils/render';

const mockApi = jest.fn<(path: string, options?: { method?: string; body?: unknown }) => Promise<unknown>>();
const mockPush = jest.fn();

jest.mock('@/lib/api', () => ({ ...jest.requireActual<object>('@/lib/api'), api: (...args: [string]) => mockApi(...args) }));
jest.mock('@/lib/analytics', () => ({ track: jest.fn() }));
jest.mock('expo-router', () => ({
  router: { push: (...args: unknown[]) => mockPush(...args), back: jest.fn(), canGoBack: () => true, replace: jest.fn() },
  useLocalSearchParams: () => ({}),
}));

function routes(save: (body: unknown) => Promise<unknown>) {
  const { ApiError } = jest.requireActual<typeof import('@/lib/api')>('@/lib/api');
  mockApi.mockImplementation(async (path, options) => {
    if (path === '/drivers/me' && options?.method === 'PUT') return save(options.body);
    if (path === '/drivers/me') throw new ApiError(404, 'driver_not_found', 'x');
    if (path === '/config/public') return { driver_min_age: 18 };
    throw new Error(`unexpected ${path}`);
  });
}

async function fill(values: { birth: string; id: string; rif: string; phone: string }) {
  await fireEvent.changeText(await screen.findByLabelText(i18n.t('driver.personal.birthDate')), values.birth);
  await fireEvent.changeText(screen.getByLabelText(i18n.t('driver.personal.nationalId')), values.id);
  await fireEvent.changeText(screen.getByLabelText(i18n.t('driver.personal.rif')), values.rif);
  await fireEvent.changeText(screen.getByLabelText(i18n.t('driver.personal.phone')), values.phone);
  await fireEvent.press(screen.getByLabelText(i18n.t('common.continue')));
}

describe('driver onboarding: personal data', () => {
  beforeEach(async () => {
    mockApi.mockReset();
    mockPush.mockReset();
    await i18n.changeLanguage('es');
  });

  it('checks the fields before sending anything', async () => {
    routes(async () => ({}));
    await renderScreen(<PersonalStep />);
    await fill({ birth: '01/01/2015', id: 'X1', rif: '1', phone: '12' });
    expect(await screen.findByText(i18n.t('driver.personal.tooYoung', { age: 18 }))).toBeTruthy();
    expect(screen.getByText(i18n.t('driver.personal.nationalIdInvalid'))).toBeTruthy();
    expect(screen.getByText(i18n.t('driver.personal.phoneInvalid'))).toBeTruthy();
    expect(mockApi.mock.calls.some(([, options]) => options?.method === 'PUT')).toBe(false);
  });

  it('saves normalized data and goes to the vehicle step', async () => {
    let saved: unknown = null;
    routes(async (body) => {
      saved = body;
      return { status: 'draft' };
    });
    await renderScreen(<PersonalStep />);
    await fill({ birth: '15/03/1990', id: 'v 12.345.678', rif: 'v123456789', phone: '0412 123 4567' });
    await waitFor(() => expect(mockPush).toHaveBeenCalledWith('/driver/vehicle'));
    expect(saved).toEqual({ birth_date: '1990-03-15', national_id: 'V12345678', rif: 'V123456789', phone: '+584121234567' });
  });

  it('marks the field the API refused', async () => {
    const { ApiError } = jest.requireActual<typeof import('@/lib/api')>('@/lib/api');
    routes(async () => Promise.reject(new ApiError(409, 'national_id_taken', 'x')));
    await renderScreen(<PersonalStep />);
    await fill({ birth: '15/03/1990', id: 'V12345678', rif: 'V123456789', phone: '04121234567' });
    expect(await screen.findByText(i18n.t('errors.national_id_taken'))).toBeTruthy();
  });
});
