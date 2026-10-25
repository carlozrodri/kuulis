/**
 * The screen a signed-out, pending-terms, mode-less or ready user belongs on. The root layout's guards
 * redirect there: Expo Router 58 no longer falls back to a group's first screen, so "/" signed out was an
 * unmatched route.
 */
export function homeRoute(state: { signedIn: boolean; pendingLegal: boolean; hasMode: boolean }) {
  if (!state.signedIn) return '/login' as const;
  if (state.pendingLegal) return '/accept-terms' as const;
  if (!state.hasMode) return '/welcome' as const;
  return '/' as const;
}
