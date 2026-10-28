import { useQuery } from '@tanstack/react-query';

import { api } from '@/lib/api';
import type { PublicActivity } from '@/lib/types';

/**
 * "Caracas en movimiento" (docs/product/wow/01-mapa-vivo.md, part B): real trips only, anonymous. The API
 * caches it for 30 s, so reading it more often would show nothing new.
 */
export const ACTIVITY_QUERY_KEY = ['public-activity'] as const;
export const ACTIVITY_REFRESH_MS = 30_000;

export function usePublicActivity(enabled = true) {
  return useQuery({
    queryKey: ACTIVITY_QUERY_KEY,
    enabled,
    queryFn: () => api<PublicActivity>('/public/rides/activity', { auth: false }),
    refetchInterval: ACTIVITY_REFRESH_MS,
    staleTime: ACTIVITY_REFRESH_MS,
  });
}
