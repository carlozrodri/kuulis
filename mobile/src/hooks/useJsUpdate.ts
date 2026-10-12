import * as Updates from 'expo-updates';
import { useState } from 'react';

import { useDriverProfile } from '@/hooks/useDriver';
import { useActiveRide, useDriverState } from '@/hooks/useRides';
import { otaEnabled } from '@/lib/appVersion';
import { checkAndFetchUpdate, type JsCheckOutcome, restartBlocker, shortUpdateId } from '@/lib/jsUpdate';
import { isActiveStatus } from '@/lib/ride';
import { createStore, useStore } from '@/lib/store';
import { useAuth } from '@/providers/AuthProvider';

/** Downloaded update whose "Hay una mejora lista" banner was closed (until the app is opened again). */
const dismissedUpdate = createStore<string | null>(null);

/**
 * Whether the user may restart the app now (doc 09 part 2): never during a ride (passenger or driver) nor
 * while a driver is online. Pass `enabled = false` to skip the queries when nothing would be restarted.
 */
export function useCanRestart(enabled = true) {
  const { user } = useAuth();
  const signedIn = enabled && !!user;
  const profile = useDriverProfile(signedIn);
  const approved = signedIn && profile.data?.status === 'approved';
  const state = useDriverState(approved);
  const active = useActiveRide(signedIn);

  const known =
    !signedIn ||
    (active.data !== undefined && profile.data !== undefined && (!approved || state.data !== undefined));
  const blocker = enabled
    ? restartBlocker({
        inRide: !!active.data && isActiveStatus(active.data.status),
        driverOnline: approved && !!state.data?.online,
        known,
      })
    : 'unknown';
  return { allowed: blocker === null, blocker };
}

/** The running JS update, a downloaded one waiting for the next start, and the user's own check / restart. */
export function useJsUpdate() {
  const updates = Updates.useUpdates();
  const dismissed = useStore(dismissedUpdate);
  const [restartFailed, setRestartFailed] = useState(false);

  const pending = otaEnabled && updates.isUpdatePending;
  const pendingId = updates.downloadedUpdate?.updateId ?? 'pending';
  const running = updates.currentlyRunning;
  const embedded = running.isEmbeddedLaunch || !running.updateId;

  return {
    enabled: otaEnabled,
    running: {
      embedded,
      shortId: embedded ? '' : shortUpdateId(running.updateId),
      createdAt: embedded ? null : (running.createdAt ?? null),
      channel: running.channel || null,
    },
    pending,
    dismissed: dismissed === pendingId,
    dismiss: () => dismissedUpdate.set(pendingId),
    /** "Buscar actualizaciones": check, then download if there is something new. Never rejects. */
    check: (): Promise<JsCheckOutcome> =>
      otaEnabled ? checkAndFetchUpdate(Updates) : Promise.resolve('none'),
    restartFailed,
    /** Only ever called from a user's tap, after useCanRestart allowed it. */
    restart() {
      if (!otaEnabled) return;
      setRestartFailed(false);
      Updates.reloadAsync().catch(() => setRestartFailed(true));
    },
  };
}
