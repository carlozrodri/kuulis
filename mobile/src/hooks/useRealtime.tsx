import { useQueryClient } from '@tanstack/react-query';
import {
  createContext,
  type PropsWithChildren,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
} from 'react';
import { AppState } from 'react-native';

import { DRIVER_QUERY_KEY, isDriverNotification } from '@/hooks/useDriver';
import { refreshReports } from '@/hooks/useReports';
import { rideKeys } from '@/hooks/useRides';
import { isSubscriptionNotification, isWalletNotification, refreshSubscription, refreshWallet } from '@/hooks/useWallet';
import { tokens } from '@/lib/api';
import { config } from '@/lib/config';
import { isAccountNotification, isReportNotification } from '@/lib/reports';
import { useAuth } from '@/providers/AuthProvider';

export type RealtimeStatus = 'connecting' | 'open' | 'closed';
export type RealtimeHandler = (data: unknown) => void;

type RealtimeContextValue = {
  status: RealtimeStatus;
  /** Sends a client message when the socket is authenticated. Returns false when it could not. */
  send: (message: Record<string, unknown>) => boolean;
  /** Subscribes to a server event (`ride.updated`…). Returns the unsubscribe function. */
  subscribe: (event: string, handler: RealtimeHandler) => () => void;
  /** Increments every time the socket becomes ready again after a drop (use it to re-sync state). */
  generation: number;
};

const RealtimeContext = createContext<RealtimeContextValue | null>(null);

/**
 * One WebSocket per signed-in session (/api/v1/ws). Authenticates with the first message, reconnects with
 * exponential backoff and pauses while the app is in background. Screens subscribe to events through
 * `useRealtimeEvent` and re-sync their data when `generation` changes.
 */
export function RealtimeProvider({ enabled, children }: PropsWithChildren<{ enabled: boolean }>) {
  const queryClient = useQueryClient();
  const { refreshUser } = useAuth();
  const refreshUserRef = useRef(refreshUser);
  useEffect(() => {
    refreshUserRef.current = refreshUser;
  });
  const [status, setStatus] = useState<RealtimeStatus>('closed');
  const [generation, setGeneration] = useState(0);
  const socketRef = useRef<WebSocket | null>(null);
  const readyRef = useRef(false);
  const listenersRef = useRef(new Map<string, Set<RealtimeHandler>>());

  useEffect(() => {
    if (!enabled) return;
    let attempts = 0;
    let timer: ReturnType<typeof setTimeout> | undefined;
    let stopped = false;
    let paused = false;
    let pingTimer: ReturnType<typeof setInterval> | undefined;

    const connect = () => {
      if (stopped || paused || !tokens.access) {
        // Tokens may still be loading right after sign-in: try again shortly.
        if (!stopped && !paused) timer = setTimeout(connect, 1000);
        return;
      }
      setStatus('connecting');
      const ws = new WebSocket(config.wsUrl);
      socketRef.current = ws;
      ws.onopen = () => ws.send(JSON.stringify({ type: 'auth', token: tokens.access }));
      ws.onmessage = (event) => {
        let message: { event: string; data: unknown };
        try {
          message = JSON.parse(String(event.data)) as { event: string; data: unknown };
        } catch {
          return;
        }
        if (message.event === 'ready') {
          attempts = 0;
          readyRef.current = true;
          setStatus('open');
          setGeneration((g) => g + 1);
          clearInterval(pingTimer);
          pingTimer = setInterval(() => {
            if (ws.readyState === WebSocket.OPEN) ws.send(JSON.stringify({ type: 'ping' }));
          }, 25_000);
        }
        if (message.event === 'notification') {
          void queryClient.invalidateQueries({ queryKey: ['notifications'] });
          if (isDriverNotification(message.data)) void queryClient.invalidateQueries({ queryKey: DRIVER_QUERY_KEY });
          if (isWalletNotification(message.data)) refreshWallet(queryClient);
          if (isSubscriptionNotification(message.data)) refreshSubscription(queryClient);
          // Suspended / suspension lifted: re-read the user (and the driver's online state).
          if (isAccountNotification(message.data)) {
            void refreshUserRef.current().catch(() => undefined);
            void queryClient.invalidateQueries({ queryKey: rideKeys.driverState });
          }
          if (isReportNotification(message.data)) refreshReports(queryClient);
        }
        listenersRef.current.get(message.event)?.forEach((handler) => {
          try {
            handler(message.data);
          } catch (error) {
            console.warn('Realtime handler failed', message.event, error);
          }
        });
      };
      ws.onclose = () => {
        clearInterval(pingTimer);
        readyRef.current = false;
        if (socketRef.current === ws) socketRef.current = null;
        setStatus('closed');
        if (stopped || paused) return;
        attempts += 1;
        timer = setTimeout(connect, Math.min(30_000, 1000 * 2 ** attempts));
      };
    };

    const stop = () => {
      clearTimeout(timer);
      clearInterval(pingTimer);
      readyRef.current = false;
      socketRef.current?.close();
      socketRef.current = null;
    };

    connect();
    const sub = AppState.addEventListener('change', (state) => {
      if (state === 'active' && paused) {
        paused = false;
        attempts = 0;
        connect();
      } else if (state === 'background') {
        paused = true;
        stop();
      }
    });

    return () => {
      stopped = true;
      sub.remove();
      stop();
    };
  }, [enabled, queryClient]);

  const send = useCallback((message: Record<string, unknown>) => {
    const ws = socketRef.current;
    if (!ws || !readyRef.current || ws.readyState !== WebSocket.OPEN) return false;
    ws.send(JSON.stringify(message));
    return true;
  }, []);

  const subscribe = useCallback((event: string, handler: RealtimeHandler) => {
    const listeners = listenersRef.current;
    if (!listeners.has(event)) listeners.set(event, new Set());
    listeners.get(event)!.add(handler);
    return () => {
      listeners.get(event)?.delete(handler);
    };
  }, []);

  const value = useMemo<RealtimeContextValue>(
    () => ({ status, generation, send, subscribe }),
    [status, generation, send, subscribe],
  );

  return <RealtimeContext.Provider value={value}>{children}</RealtimeContext.Provider>;
}

export function useRealtimeContext() {
  const ctx = useContext(RealtimeContext);
  if (!ctx) throw new Error('useRealtimeContext must be used inside <RealtimeProvider>');
  return ctx;
}

/** Connection status of the realtime socket. */
export function useRealtime() {
  return useRealtimeContext().status;
}

/** Calls `handler` for each server event named `event`. The latest handler is always used. */
export function useRealtimeEvent<T = unknown>(event: string, handler: (data: T) => void) {
  const { subscribe } = useRealtimeContext();
  const ref = useRef(handler);
  useEffect(() => {
    ref.current = handler;
  });
  useEffect(() => subscribe(event, (data) => ref.current(data as T)), [event, subscribe]);
}
