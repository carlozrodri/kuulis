import Constants from 'expo-constants';
import * as FileSystem from 'expo-file-system/legacy';
import { Platform } from 'react-native';

import { tokens } from '@/lib/api';
import { config } from '@/lib/config';

/**
 * Sends app errors to POST /client-errors, where they land in the API logs (no crash-reporting service).
 * Covers JS errors (global handler and the route error boundary) and, on Android, the native crash that
 * plugins/withCrashLog.js saved before the app last closed. Best-effort: reporting never throws.
 */
export type ClientErrorKind = 'js' | 'js_fatal' | 'render' | 'native';

const NATIVE_CRASH_FILE = 'kuulis-last-crash.txt';
let currentRoute: string | null = null;

/** The screen the user was on, sent with each report. */
export function setCrashRoute(route: string) {
  currentRoute = route;
}

export function reportError(kind: ClientErrorKind, error: unknown, stack?: string | null): Promise<void> {
  const err = error instanceof Error ? error : null;
  const body = {
    kind,
    message: (err ? `${err.name}: ${err.message}` : String(error)).slice(0, 2000),
    stack: (stack ?? err?.stack ?? null)?.slice(0, 20000) ?? null,
    platform: Platform.OS,
    app_version: `${Constants.expoConfig?.version ?? '?'} ${config.appEnv}`.slice(0, 40),
    route: currentRoute?.slice(0, 300) ?? null,
  };
  const headers: Record<string, string> = { 'Content-Type': 'application/json' };
  if (tokens.access) headers.Authorization = `Bearer ${tokens.access}`;
  return fetch(`${config.apiUrl}/client-errors`, { method: 'POST', headers, body: JSON.stringify(body) })
    .then(() => undefined)
    .catch(() => undefined);
}

/** Reports the native crash saved by the previous run (Android), then deletes it. */
export async function reportSavedNativeCrash() {
  if (Platform.OS !== 'android' || !FileSystem.documentDirectory) return;
  const path = `${FileSystem.documentDirectory}${NATIVE_CRASH_FILE}`;
  try {
    const info = await FileSystem.getInfoAsync(path);
    if (!info.exists) return;
    const trace = await FileSystem.readAsStringAsync(path);
    await FileSystem.deleteAsync(path, { idempotent: true });
    const firstLine = trace.split('\n').find((line) => line && !line.startsWith('thread=')) ?? 'native crash';
    await reportError('native', firstLine, trace);
  } catch {
    // nothing to report
  }
}

type ErrorUtilsType = {
  getGlobalHandler: () => (error: unknown, isFatal?: boolean) => void;
  setGlobalHandler: (handler: (error: unknown, isFatal?: boolean) => void) => void;
};

let installed = false;

/** Reports uncaught JS errors before React Native's own handler runs (which closes the app when fatal). */
export function installCrashReporting() {
  if (installed) return;
  installed = true;
  const errorUtils = (globalThis as { ErrorUtils?: ErrorUtilsType }).ErrorUtils;
  if (errorUtils) {
    const previous = errorUtils.getGlobalHandler();
    errorUtils.setGlobalHandler((error, isFatal) => {
      void reportError(isFatal ? 'js_fatal' : 'js', error);
      previous(error, isFatal);
    });
  }
  void reportSavedNativeCrash();
}
