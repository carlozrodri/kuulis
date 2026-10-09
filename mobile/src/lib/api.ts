import { config } from './config';
import { secureStorage } from './storage';
import type { TokenPair } from './types';

const ACCESS_KEY = 'kuulis.access_token';
const REFRESH_KEY = 'kuulis.refresh_token';

export class ApiError extends Error {
  constructor(
    public status: number,
    public code: string,
    message: string,
    public details?: unknown,
  ) {
    super(message);
  }
}

let accessToken: string | null = null;
let refreshPromise: Promise<boolean> | null = null;
let onSessionExpired: (() => void) | null = null;
let currentLocale = 'es';

export const tokens = {
  async load() {
    accessToken = await secureStorage.get(ACCESS_KEY);
    return { accessToken, refreshToken: await secureStorage.get(REFRESH_KEY) };
  },
  async save(pair: TokenPair) {
    accessToken = pair.access_token;
    await Promise.all([
      secureStorage.set(ACCESS_KEY, pair.access_token),
      secureStorage.set(REFRESH_KEY, pair.refresh_token),
    ]);
  },
  async clear() {
    accessToken = null;
    await Promise.all([secureStorage.remove(ACCESS_KEY), secureStorage.remove(REFRESH_KEY)]);
  },
  get access() {
    return accessToken;
  },
  refreshToken: () => secureStorage.get(REFRESH_KEY),
};

export function setSessionExpiredHandler(handler: () => void) {
  onSessionExpired = handler;
}

export function setApiLocale(locale: string) {
  currentLocale = locale;
}

async function refreshTokens(): Promise<boolean> {
  // One refresh at a time; concurrent 401s wait for the same promise.
  refreshPromise ??= (async () => {
    const refreshToken = await tokens.refreshToken();
    if (!refreshToken) return false;
    const response = await fetch(`${config.apiUrl}/auth/refresh`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ refresh_token: refreshToken }),
    });
    if (!response.ok) {
      await tokens.clear();
      return false;
    }
    await tokens.save((await response.json()) as TokenPair);
    return true;
  })().finally(() => {
    refreshPromise = null;
  });
  return refreshPromise;
}

type RequestOptions = Omit<RequestInit, 'body'> & {
  body?: unknown;
  query?: Record<string, string | number | boolean | undefined>;
  auth?: boolean;
};

export async function api<T>(path: string, options: RequestOptions = {}, retried = false): Promise<T> {
  const { body, query, auth = true, headers, ...init } = options;
  const qs = query
    ? '?' +
      Object.entries(query)
        .filter(([, v]) => v !== undefined)
        .map(([k, v]) => `${encodeURIComponent(k)}=${encodeURIComponent(String(v))}`)
        .join('&')
    : '';

  const response = await fetch(`${config.apiUrl}${path}${qs}`, {
    ...init,
    headers: {
      Accept: 'application/json',
      'Accept-Language': currentLocale,
      ...(body !== undefined ? { 'Content-Type': 'application/json' } : {}),
      ...(auth && accessToken ? { Authorization: `Bearer ${accessToken}` } : {}),
      ...(headers as Record<string, string> | undefined),
    },
    body: body !== undefined ? JSON.stringify(body) : undefined,
  });

  if (response.status === 401 && auth && !retried) {
    if (await refreshTokens()) return api<T>(path, options, true);
    onSessionExpired?.();
  }
  if (!response.ok) {
    const payload = await response.json().catch(() => null);
    const error = payload?.error;
    throw new ApiError(
      response.status,
      error?.code ?? `http_${response.status}`,
      error?.message ?? response.statusText,
      error?.details,
    );
  }
  if (response.status === 204) return undefined as T;
  return (await response.json()) as T;
}
