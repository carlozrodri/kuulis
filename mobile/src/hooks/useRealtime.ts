import { useQueryClient } from '@tanstack/react-query';
import { useEffect, useRef, useState } from 'react';
import { AppState } from 'react-native';

import { DRIVER_QUERY_KEY, isDriverNotification } from '@/hooks/useDriver';
import { tokens } from '@/lib/api';
import { config } from '@/lib/config';

export type RealtimeStatus = 'connecting' | 'open' | 'closed';

/**
 * WebSocket connection to /api/v1/ws. Authenticates with the first message, reconnects with
 * exponential backoff and pauses while the app is in background.
 */
export function useRealtime(enabled: boolean) {
  const queryClient = useQueryClient();
  const [status, setStatus] = useState<RealtimeStatus>('closed');
  const socketRef = useRef<WebSocket | null>(null);

  useEffect(() => {
    if (!enabled) return;
    let attempts = 0;
    let timer: ReturnType<typeof setTimeout> | undefined;
    let stopped = false;
    let paused = false;
    let pingTimer: ReturnType<typeof setInterval> | undefined;

    const connect = () => {
      if (stopped || !tokens.access) return;
      setStatus('connecting');
      const ws = new WebSocket(config.wsUrl);
      socketRef.current = ws;
      ws.onopen = () => ws.send(JSON.stringify({ type: 'auth', token: tokens.access }));
      ws.onmessage = (event) => {
        const message = JSON.parse(String(event.data)) as { event: string; data: unknown };
        if (message.event === 'ready') {
          attempts = 0;
          setStatus('open');
          pingTimer = setInterval(() => ws.send(JSON.stringify({ type: 'ping' })), 25_000);
        }
        if (message.event === 'notification') {
          void queryClient.invalidateQueries({ queryKey: ['notifications'] });
          if (isDriverNotification(message.data)) void queryClient.invalidateQueries({ queryKey: DRIVER_QUERY_KEY });
        }
      };
      ws.onclose = () => {
        clearInterval(pingTimer);
        setStatus('closed');
        if (stopped || paused) return;
        attempts += 1;
        timer = setTimeout(connect, Math.min(30_000, 1000 * 2 ** attempts));
      };
    };

    const stop = () => {
      clearTimeout(timer);
      clearInterval(pingTimer);
      socketRef.current?.close();
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

  return status;
}
