import NetInfo from '@react-native-community/netinfo';
import { useQueryClient } from '@tanstack/react-query';
import { createContext, type PropsWithChildren, useCallback, useContext, useEffect, useMemo, useState } from 'react';

import i18n from '@/i18n';
import { track } from '@/lib/analytics';
import { outbox } from '@/lib/actionQueue';
import { api, ApiError, setLegalRequiredHandler, setSessionExpiredHandler, tokens } from '@/lib/api';
import { localFile } from '@/lib/localFile';
import { queryPersister } from '@/lib/queryPersistence';
import { googleSignOut } from '@/lib/social';
import type { AuthResponse, User } from '@/lib/types';

type AuthContextValue = {
  user: User | null;
  isLoading: boolean;
  signIn: (email: string, password: string) => Promise<void>;
  signUp: (email: string, password: string, fullName: string, acceptLegal: boolean) => Promise<void>;
  /** Exchanges a Google / Apple id token for a Kuulis session (POST /auth/social/{provider}). */
  signInWithGoogle: (idToken: string) => Promise<void>;
  signInWithApple: (idToken: string, fullName: string | null) => Promise<void>;
  signOut: () => Promise<void>;
  refreshUser: () => Promise<void>;
};

const AuthContext = createContext<AuthContextValue | null>(null);

/** The last profile seen, so the app opens signed in without signal (doc 20). */
const USER_FILE = 'user.json';

export async function readCachedUser(): Promise<User | null> {
  const raw = await localFile.read(USER_FILE);
  if (!raw) return null;
  try {
    return JSON.parse(raw) as User;
  } catch {
    return null;
  }
}

/** A social sign-in that created the account just now counts as a sign-up (doc 19). */
function trackSocialSignup(data: AuthResponse, method: 'google' | 'apple') {
  const created = Date.parse(data.user.created_at);
  if (Number.isFinite(created) && Date.now() - created < 2 * 60_000) track('signup_completed', { method });
}

export function AuthProvider({ children }: PropsWithChildren) {
  const queryClient = useQueryClient();
  const [user, setUser] = useState<User | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  const applySession = useCallback(async (data: AuthResponse) => {
    await tokens.save(data);
    setUser(data.user);
    if (data.user.locale !== i18n.language) await i18n.changeLanguage(data.user.locale);
  }, []);

  // Opened offline with the saved profile: it is read again once the network is back.
  const [stale, setStale] = useState(false);

  const clear = useCallback(async () => {
    await tokens.clear();
    queryClient.clear();
    // Nothing of this account stays on the phone for the next one.
    await Promise.all([queryPersister.removeClient(), localFile.write(USER_FILE, ''), outbox.clear()]);
    setUser(null);
  }, [queryClient]);

  // Restore the session on app start.
  useEffect(() => {
    setSessionExpiredHandler(() => void clear());
    // Shows the acceptance screen: the root navigator follows user.pending_legal.
    setLegalRequiredHandler((kinds) => setUser((current) => (current ? { ...current, pending_legal: kinds } : current)));
    (async () => {
      try {
        const { refreshToken } = await tokens.load();
        if (refreshToken) setUser(await api<User>('/users/me'));
      } catch (error) {
        // No signal (or the server failing) is not a closed session: open with the last profile, keep the tokens.
        const unreachable = !(error instanceof ApiError) || error.status >= 500;
        const cached = unreachable ? await readCachedUser() : null;
        if (cached) {
          setUser(cached);
          setStale(true);
        } else {
          await clear();
        }
      } finally {
        setIsLoading(false);
      }
    })();
  }, [clear]);

  useEffect(() => {
    if (user) void localFile.write(USER_FILE, JSON.stringify(user));
  }, [user]);

  useEffect(() => {
    if (!stale) return;
    return NetInfo.addEventListener((state) => {
      if (!state.isConnected || state.isInternetReachable === false) return;
      setStale(false);
      api<User>('/users/me')
        .then(setUser)
        // A 401 here already closed the session (api() calls the expired handler); anything else keeps the
        // saved profile until the next start.
        .catch(() => undefined);
    });
  }, [stale]);

  const value = useMemo<AuthContextValue>(
    () => ({
      user,
      isLoading,
      signIn: async (email, password) => {
        await applySession(
          await api<AuthResponse>('/auth/login', { method: 'POST', body: { email, password }, auth: false }),
        );
      },
      signUp: async (email, password, fullName, acceptLegal) => {
        await applySession(
          await api<AuthResponse>('/auth/register', {
            method: 'POST',
            body: { email, password, full_name: fullName, locale: i18n.language, accept_legal: acceptLegal },
            auth: false,
          }),
        );
        track('signup_completed', { method: 'email' });
      },
      signInWithGoogle: async (idToken) => {
        const data = await api<AuthResponse>('/auth/social/google', { method: 'POST', body: { id_token: idToken }, auth: false });
        await applySession(data);
        trackSocialSignup(data, 'google');
      },
      signInWithApple: async (idToken, fullName) => {
        const data = await api<AuthResponse>('/auth/social/apple', {
          method: 'POST',
          body: { id_token: idToken, full_name: fullName },
          auth: false,
        });
        await applySession(data);
        trackSocialSignup(data, 'apple');
      },
      signOut: async () => {
        const refreshToken = await tokens.refreshToken();
        if (refreshToken) {
          await api('/auth/logout', { method: 'POST', body: { refresh_token: refreshToken }, auth: false }).catch(
            () => undefined,
          );
        }
        void googleSignOut();
        await clear();
      },
      refreshUser: async () => setUser(await api<User>('/users/me')),
    }),
    [user, isLoading, applySession, clear],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error('useAuth must be used inside <AuthProvider>');
  return ctx;
}
