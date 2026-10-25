import { ApiError } from './api';

/**
 * What kind of failure a screen hit, so error screens can say something useful instead of "algo salió mal":
 * - `offline`: the phone has no network.
 * - `unreachable`: the phone is online but the request never got an answer (bad signal, server down, DNS).
 * - `server`: the API answered 5xx without a code the app knows.
 * - `notFound`: 404 (a ride, receipt or article that no longer exists).
 * - `generic`: any other API error; its own message is the useful part.
 */
export type ErrorKind = 'offline' | 'unreachable' | 'server' | 'notFound' | 'generic';

/** Codes the API sends with a 5xx that already have their own text (doc 10: maintenance and paused cities). */
const SPECIFIC_5XX = new Set(['service_paused']);

export function errorKind(error: unknown, offline = false): ErrorKind {
  if (offline) return 'offline';
  if (!(error instanceof ApiError)) return 'unreachable';
  if (error.status >= 500 && !SPECIFIC_5XX.has(error.code)) return 'server';
  if (error.status === 404) return 'notFound';
  return 'generic';
}

/** True when the API sent a code of its own (not just the HTTP status), so its text beats a stock one. */
export function hasSpecificCode(error: unknown): boolean {
  return error instanceof ApiError && !error.code.startsWith('http_');
}

export const isNotFound = (error: unknown) => error instanceof ApiError && error.status === 404;
