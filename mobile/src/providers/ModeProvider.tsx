import { createContext, type PropsWithChildren, useCallback, useContext, useEffect, useMemo, useState } from 'react';

import { secureStorage } from '@/lib/storage';
import { useAuth } from '@/providers/AuthProvider';

export type AppMode = 'passenger' | 'driver';

type ModeContextValue = {
  /** null until the user picks one on the welcome screen. */
  mode: AppMode | null;
  isLoading: boolean;
  setMode: (mode: AppMode) => Promise<void>;
};

const ModeContext = createContext<ModeContextValue | null>(null);

const keyFor = (userId: string) => `kuulis.mode.${userId}`;
const isMode = (value: string | null): value is AppMode => value === 'passenger' || value === 'driver';

/** One account, two modes. The choice is stored on the device, per user. */
export function ModeProvider({ children }: PropsWithChildren) {
  const { user } = useAuth();
  const userId = user?.id;
  const [state, setState] = useState<{ userId?: string; mode: AppMode | null }>({ mode: null });

  useEffect(() => {
    if (!userId) return;
    let active = true;
    secureStorage
      .get(keyFor(userId))
      .catch(() => null)
      .then((stored) => {
        if (active) setState({ userId, mode: isMode(stored) ? stored : null });
      });
    return () => {
      active = false;
    };
  }, [userId]);

  const setMode = useCallback(
    async (mode: AppMode) => {
      if (!userId) return;
      setState({ userId, mode });
      await secureStorage.set(keyFor(userId), mode).catch(() => undefined);
    },
    [userId],
  );

  const value = useMemo<ModeContextValue>(
    () => ({
      mode: userId && state.userId === userId ? state.mode : null,
      isLoading: !!userId && state.userId !== userId,
      setMode,
    }),
    [userId, state, setMode],
  );

  return <ModeContext.Provider value={value}>{children}</ModeContext.Provider>;
}

export function useMode() {
  const ctx = useContext(ModeContext);
  if (!ctx) throw new Error('useMode must be used inside <ModeProvider>');
  return ctx;
}
