import { useQuery } from '@tanstack/react-query';
import { useEffect } from 'react';

import { api, setUpdateRequiredHandler } from '@/lib/api';
import { appVersion, canSelfUpdate, fromPlayStore } from '@/lib/appVersion';
import { secureStorage } from '@/lib/storage';
import { createStore, useStore } from '@/lib/store';
import type { AppVersionCheck } from '@/lib/types';

export const APP_VERSION_KEY = ['app', 'version'] as const;
const SIX_HOURS = 6 * 60 * 60 * 1000;
const DISMISSED_KEY = 'kuulis.update.dismissed_build';

/** Minimum build announced by a 426 app_update_required (0 = none). */
const forcedMinimum = createStore(0);
/** Build whose "update available" banner the user closed (null until read from storage). */
const dismissedBuild = createStore<number | null>(null);
let dismissedLoaded = false;

// A ride action refused for an old build blocks the app right away, without waiting for the next check.
setUpdateRequiredHandler((minimumBuild) => {
  forcedMinimum.set(Math.max(minimumBuild, appVersion.build + 1));
});

function loadDismissed() {
  if (dismissedLoaded) return;
  dismissedLoaded = true;
  void secureStorage
    .get(DISMISSED_KEY)
    .then((value) => dismissedBuild.set(Number(value) || 0))
    .catch(() => dismissedBuild.set(0));
}

/**
 * Newer APK for this channel (doc 09 part 1). Checked at start and every 6 h on installed Android builds;
 * dev clients, Expo Go and web skip it.
 */
export function useAppUpdate() {
  const forced = useStore(forcedMinimum);
  const dismissed = useStore(dismissedBuild);
  const query = useQuery({
    queryKey: APP_VERSION_KEY,
    queryFn: () =>
      api<AppVersionCheck>('/app/version', {
        auth: false,
        query: { platform: 'android', channel: appVersion.channel, build: appVersion.build },
      }),
    enabled: canSelfUpdate,
    staleTime: SIX_HOURS,
    refetchInterval: SIX_HOURS,
  });

  useEffect(loadDismissed, []);

  const { refetch } = query;
  useEffect(() => {
    // The 426 means there is a mandatory release this app has not heard of yet.
    if (forced && canSelfUpdate) void refetch();
  }, [forced, refetch]);

  const data = canSelfUpdate ? query.data : undefined;
  const latest = data?.latest ?? null;
  // A Play build only learns of a mandatory update from a refused ride action (426); it sends people to Play.
  const required =
    (canSelfUpdate && (!!data?.update_required || forced > appVersion.build)) ||
    (fromPlayStore && forced > appVersion.build);
  const available = !!latest && latest.build > appVersion.build && (required || !!data?.update_available);

  return {
    enabled: canSelfUpdate,
    query,
    latest,
    available,
    required,
    /** The banner stays hidden for the build the user dismissed (a newer build shows it again). */
    // Hidden until storage is read, so a dismissed banner does not flash on start.
    dismissed: dismissed === null || (!!latest && dismissed >= latest.build),
    dismiss() {
      if (!latest) return;
      dismissedBuild.set(latest.build);
      void secureStorage.set(DISMISSED_KEY, String(latest.build)).catch(() => undefined);
    },
  };
}
