import { useQueryClient } from '@tanstack/react-query';
import { createContext, type PropsWithChildren, useCallback, useContext, useEffect, useMemo, useState } from 'react';

import i18n from '@/i18n';
import { api, setSessionExpiredHandler, tokens } from '@/lib/api';
import type { AuthResponse, User } from '@/lib/types';

type AuthContextValue = {
  user: User | null;
  isLoading: boolean;
  signIn: (email: string, password: string) => Promise<void>;
  signUp: (email: string, password: string, fullName: string) => Promise<void>;
  signOut: () => Promise<void>;
  refreshUser: () => Promise<void>;
};

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: PropsWithChildren) {
  const queryClient = useQueryClient();
  const [user, setUser] = useState<User | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  const applySession = useCallback(async (data: AuthResponse) => {
    await tokens.save(data);
    setUser(data.user);
    if (data.user.locale !== i18n.language) await i18n.changeLanguage(data.user.locale);
  }, []);

  const clear = useCallback(async () => {
    await tokens.clear();
    queryClient.clear();
    setUser(null);
  }, [queryClient]);

  // Restore the session on app start.
  useEffect(() => {
    setSessionExpiredHandler(() => void clear());
    (async () => {
      try {
        const { refreshToken } = await tokens.load();
        if (refreshToken) setUser(await api<User>('/users/me'));
      } catch {
        await clear();
      } finally {
        setIsLoading(false);
      }
    })();
  }, [clear]);

  const value = useMemo<AuthContextValue>(
    () => ({
      user,
      isLoading,
      signIn: async (email, password) => {
        await applySession(
          await api<AuthResponse>('/auth/login', { method: 'POST', body: { email, password }, auth: false }),
        );
      },
      signUp: async (email, password, fullName) => {
        await applySession(
          await api<AuthResponse>('/auth/register', {
            method: 'POST',
            body: { email, password, full_name: fullName, locale: i18n.language },
            auth: false,
          }),
        );
      },
      signOut: async () => {
        const refreshToken = await tokens.refreshToken();
        if (refreshToken) {
          await api('/auth/logout', { method: 'POST', body: { refresh_token: refreshToken }, auth: false }).catch(
            () => undefined,
          );
        }
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
