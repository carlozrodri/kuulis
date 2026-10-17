import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';

import { ApiError, api } from '@/lib/api';
import type { PlaceIcon, PlaceKind, ReferralSummary, SavedPlace } from '@/lib/types';

export const accountKeys = {
  places: ['users', 'me', 'places'] as const,
  referrals: ['referrals', 'me'] as const,
};

/** 404 from an older server reads as "nothing yet" so screens still render. */
async function orEmpty<T>(request: Promise<T>, empty: T): Promise<T> {
  try {
    return await request;
  } catch (error) {
    if (error instanceof ApiError && error.status === 404) return empty;
    throw error;
  }
}

export function useSavedPlaces(enabled = true) {
  return useQuery({
    queryKey: accountKeys.places,
    queryFn: () => orEmpty(api<SavedPlace[]>('/users/me/places'), []),
    enabled,
    staleTime: 5 * 60_000,
  });
}

export type PlaceInput = { kind: PlaceKind; label?: string; address: string; lat: number; lng: number; icon?: PlaceIcon | null };

/** Saves a new place, or updates one when `id` is given. Home and work replace the previous one. */
export function useSavePlace() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ id, ...input }: PlaceInput & { id?: string }) =>
      id
        ? api<SavedPlace>(`/users/me/places/${id}`, {
            method: 'PATCH',
            body: { label: input.label, address: input.address, lat: input.lat, lng: input.lng, ...(input.icon ? { icon: input.icon } : {}) },
          })
        : api<SavedPlace>('/users/me/places', { method: 'POST', body: input }),
    onSettled: () => void queryClient.invalidateQueries({ queryKey: accountKeys.places }),
  });
}

export function useDeletePlace() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => api(`/users/me/places/${id}`, { method: 'DELETE' }),
    onMutate: (id) => {
      queryClient.setQueryData<SavedPlace[]>(accountKeys.places, (places) => places?.filter((p) => p.id !== id));
    },
    onSettled: () => void queryClient.invalidateQueries({ queryKey: accountKeys.places }),
  });
}

export function useReferrals(enabled = true) {
  return useQuery({
    queryKey: accountKeys.referrals,
    queryFn: () => orEmpty<ReferralSummary | null>(api<ReferralSummary>('/referrals/me'), null),
    enabled,
    staleTime: 60_000,
  });
}

export function useRedeemCode() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (code: string) => api<ReferralSummary>('/referrals/redeem', { method: 'POST', body: { code } }),
    onSuccess: (summary) => queryClient.setQueryData(accountKeys.referrals, summary),
  });
}
