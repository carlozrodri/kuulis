import { useQueryClient } from "@tanstack/react-query";
import { useCallback, useEffect, useState } from "react";

import { rideKeys } from "@/hooks/useRides";
import {
  activeSuspension,
  isAccountSuspended,
  msUntilLifted,
  suspensionFromError,
} from "@/lib/suspension";
import type { Suspension } from "@/lib/types";
import { useAuth } from "@/providers/AuthProvider";

/**
 * The signed-in user's suspension in force, if any (GET /users/me `suspension`). A 403 account_suspended
 * passed to `handleError` shows the panel right away from the error details and refreshes the user; the
 * screen re-renders by itself when a timed suspension ends.
 */
export function useSuspension() {
  const { user, refreshUser } = useAuth();
  const queryClient = useQueryClient();
  // From a 403 account_suspended, until the refreshed user says otherwise.
  const [fromError, setFromError] = useState<{
    suspension: Suspension;
    user: unknown;
  } | null>(null);
  const [now, setNow] = useState(() => Date.now());

  const fallback =
    fromError && fromError.user === user ? fromError.suspension : null;
  const suspension = activeSuspension(user?.suspension ?? fallback, now);

  useEffect(() => {
    const ms = msUntilLifted(suspension);
    if (ms === null) return;
    const timer = setTimeout(() => setNow(Date.now()), ms + 1000);
    return () => clearTimeout(timer);
  }, [suspension]);

  /** Returns true when the error was account_suspended (the caller then skips its own toast). */
  const handleError = useCallback(
    (error: unknown) => {
      if (!isAccountSuspended(error)) return false;
      const fromDetails = suspensionFromError(error);
      if (fromDetails) setFromError({ suspension: fromDetails, user });
      void refreshUser().catch(() => undefined);
      void queryClient.invalidateQueries({ queryKey: rideKeys.driverState });
      return true;
    },
    [refreshUser, queryClient, user],
  );

  return { suspension, handleError };
}
