/**
 * JS updates over the air (doc 09 part 2): pure decisions shared by the header, Perfil → Acerca de and the
 * "Hay una mejora lista" banner. Nothing here talks to expo-updates, so it can be tested directly.
 */

/** Value of X-App-Update: the running update id, "embedded" for the code inside the APK, null (no header) when updates are off. */
export function updateHeaderValue(state: {
  isEnabled: boolean;
  isEmbeddedLaunch: boolean;
  updateId: string | null | undefined;
}): string | null {
  if (!state.isEnabled) return null;
  if (state.isEmbeddedLaunch || !state.updateId) return 'embedded';
  return state.updateId.toLowerCase();
}

/** First 8 characters of the update uuid, as shown in Acerca de ("" when there is none). */
export function shortUpdateId(updateId: string | null | undefined): string {
  return updateId ? updateId.slice(0, 8).toLowerCase() : '';
}

/** Why "Reiniciar" is not offered right now: a ride in progress, a driver online, or not known yet. */
export type RestartBlocker = 'ride' | 'online' | 'unknown';

/**
 * The app never restarts by itself; the user may restart only when nothing would be interrupted. While the
 * active ride or the driver state is still unknown (loading or failed), restarting stays unavailable.
 */
export function restartBlocker(state: { inRide: boolean; driverOnline: boolean; known: boolean }): RestartBlocker | null {
  if (state.inRide) return 'ride';
  if (state.driverOnline) return 'online';
  if (!state.known) return 'unknown';
  return null;
}

/** Outcome of "Buscar actualizaciones" for JS updates. */
export type JsCheckOutcome = 'none' | 'ready' | 'error';

type CheckResult = { isAvailable: boolean; isRollBackToEmbedded?: boolean };
type FetchResult = { isNew: boolean; isRollBackToEmbedded?: boolean };

/**
 * Asks the update server for a newer update and downloads it if there is one. A downloaded update (or a
 * rollback to the embedded code) is "ready": it applies the next time the app is opened. Never throws.
 */
export async function checkAndFetchUpdate(updates: {
  checkForUpdateAsync: () => Promise<CheckResult>;
  fetchUpdateAsync: () => Promise<FetchResult>;
}): Promise<JsCheckOutcome> {
  try {
    const check = await updates.checkForUpdateAsync();
    if (!check.isAvailable && !check.isRollBackToEmbedded) return 'none';
    const fetched = await updates.fetchUpdateAsync();
    return fetched.isNew || fetched.isRollBackToEmbedded ? 'ready' : 'none';
  } catch {
    return 'error';
  }
}
