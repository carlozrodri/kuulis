import { describe, expect, it, jest } from '@jest/globals';

import { checkAndFetchUpdate, restartBlocker, shortUpdateId, updateHeaderValue } from '@/lib/jsUpdate';

const UUID = '0F3A9C21-7B4E-4D2A-9C1B-5E6F7A8B9C0D';

describe('X-App-Update header', () => {
  it('sends the running update id, "embedded" for the APK code, nothing when updates are off', () => {
    expect(updateHeaderValue({ isEnabled: true, isEmbeddedLaunch: false, updateId: UUID })).toBe(UUID.toLowerCase());
    expect(updateHeaderValue({ isEnabled: true, isEmbeddedLaunch: true, updateId: UUID })).toBe('embedded');
    expect(updateHeaderValue({ isEnabled: true, isEmbeddedLaunch: false, updateId: null })).toBe('embedded');
    expect(updateHeaderValue({ isEnabled: false, isEmbeddedLaunch: false, updateId: UUID })).toBeNull();
    expect(updateHeaderValue({ isEnabled: false, isEmbeddedLaunch: true, updateId: null })).toBeNull();
  });

  it('is added to the API headers only when expo-updates is enabled', () => {
    const headersWith = (updates: Record<string, unknown>) => {
      let headers: Record<string, string> = {};
      jest.isolateModules(() => {
        jest.doMock('expo-updates', () => updates);
        // eslint-disable-next-line @typescript-eslint/no-require-imports
        headers = (require('@/lib/appVersion') as typeof import('@/lib/appVersion')).APP_VERSION_HEADERS;
      });
      jest.dontMock('expo-updates');
      return headers;
    };
    expect(headersWith({ isEnabled: true, isEmbeddedLaunch: false, updateId: UUID })['X-App-Update']).toBe(
      UUID.toLowerCase(),
    );
    expect(headersWith({ isEnabled: true, isEmbeddedLaunch: true, updateId: UUID })['X-App-Update']).toBe('embedded');
    expect(headersWith({ isEnabled: false, isEmbeddedLaunch: false, updateId: null })).not.toHaveProperty('X-App-Update');
  });
});

describe('running update', () => {
  it('shows the first 8 characters of the uuid', () => {
    expect(shortUpdateId(UUID)).toBe('0f3a9c21');
    expect(shortUpdateId(null)).toBe('');
    expect(shortUpdateId(undefined)).toBe('');
  });
});

describe('restart', () => {
  it('is allowed only with no ride in progress, the driver offline and both known', () => {
    expect(restartBlocker({ inRide: false, driverOnline: false, known: true })).toBeNull();
    expect(restartBlocker({ inRide: true, driverOnline: false, known: true })).toBe('ride');
    expect(restartBlocker({ inRide: true, driverOnline: true, known: true })).toBe('ride');
    expect(restartBlocker({ inRide: false, driverOnline: true, known: true })).toBe('online');
    expect(restartBlocker({ inRide: false, driverOnline: false, known: false })).toBe('unknown');
  });
});

describe('Buscar actualizaciones', () => {
  const none = { isAvailable: false, isRollBackToEmbedded: false };
  const available = { isAvailable: true, isRollBackToEmbedded: false };

  it('downloads an available update and reports it ready', async () => {
    const fetchUpdateAsync = jest.fn(async () => ({ isNew: true, isRollBackToEmbedded: false }));
    await expect(checkAndFetchUpdate({ checkForUpdateAsync: async () => available, fetchUpdateAsync })).resolves.toBe('ready');
    expect(fetchUpdateAsync).toHaveBeenCalledTimes(1);
  });

  it('does not download when there is nothing new', async () => {
    const fetchUpdateAsync = jest.fn(async () => ({ isNew: true }));
    await expect(checkAndFetchUpdate({ checkForUpdateAsync: async () => none, fetchUpdateAsync })).resolves.toBe('none');
    expect(fetchUpdateAsync).not.toHaveBeenCalled();
  });

  it('treats a rollback to the embedded code as ready', async () => {
    await expect(
      checkAndFetchUpdate({
        checkForUpdateAsync: async () => ({ isAvailable: false, isRollBackToEmbedded: true }),
        fetchUpdateAsync: async () => ({ isNew: false, isRollBackToEmbedded: true }),
      }),
    ).resolves.toBe('ready');
  });

  it('reports nothing new when the download brings nothing', async () => {
    await expect(
      checkAndFetchUpdate({ checkForUpdateAsync: async () => available, fetchUpdateAsync: async () => ({ isNew: false }) }),
    ).resolves.toBe('none');
  });

  it('never throws', async () => {
    const fail = async (): Promise<never> => {
      throw new Error('offline');
    };
    await expect(checkAndFetchUpdate({ checkForUpdateAsync: fail, fetchUpdateAsync: fail })).resolves.toBe('error');
    await expect(checkAndFetchUpdate({ checkForUpdateAsync: async () => available, fetchUpdateAsync: fail })).resolves.toBe(
      'error',
    );
  });
});
