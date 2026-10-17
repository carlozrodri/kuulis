import { type QueryClient, useMutation, useQuery, useQueryClient } from '@tanstack/react-query';

import { getFreshPosition } from '@/hooks/useLocation';
import { api } from '@/lib/api';
import type { CheckInAnswer } from '@/lib/safety';
import { createStore } from '@/lib/store';
import type { SafetyAlert, ShareLink, SosResult, TrustedContact } from '@/lib/types';

/** Trip safety (doc 11): trusted contacts, live links, SOS and the "¿Todo bien?" check-ins. */
export const safetyKeys = {
  contacts: ['safety', 'contacts'] as const,
  alerts: ['safety', 'alerts'] as const,
};

export type ContactInput = Omit<TrustedContact, 'id'>;

/** GET /users/me/trusted-contacts (up to five). */
export function useTrustedContacts(enabled = true) {
  return useQuery({
    queryKey: safetyKeys.contacts,
    queryFn: () => api<TrustedContact[]>('/users/me/trusted-contacts'),
    enabled,
    staleTime: 5 * 60_000,
  });
}

/** Adds (no id) or edits a contact. */
export function useSaveContact() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ id, ...body }: ContactInput & { id?: string }) =>
      id
        ? api<TrustedContact>(`/users/me/trusted-contacts/${id}`, { method: 'PUT', body })
        : api<TrustedContact>('/users/me/trusted-contacts', { method: 'POST', body }),
    onSuccess: () => void queryClient.invalidateQueries({ queryKey: safetyKeys.contacts }),
  });
}

export function useDeleteContact() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => api(`/users/me/trusted-contacts/${id}`, { method: 'DELETE' }),
    onSuccess: () => void queryClient.invalidateQueries({ queryKey: safetyKeys.contacts }),
  });
}

/** A fresh live link for the ride (`/v/{token}` on the website); it stops working when the ride ends. */
/** `forRider` (doc 23): the link for the person riding a ride requested for them; it also shows the PIN. */
export const createShareLink = (rideId: string, forRider = false) =>
  api<ShareLink>(`/rides/${rideId}/share`, { method: 'POST', ...(forRider ? { body: { for_rider: true } } : {}) });

/** My open SOS and the check-ins waiting for my answer. Polls while one is open, and while `watch`. */
export function useActiveAlerts(enabled: boolean, watch: boolean) {
  return useQuery({
    queryKey: safetyKeys.alerts,
    queryFn: () => api<SafetyAlert[]>('/safety/alerts/active'),
    enabled,
    staleTime: 10_000,
    refetchInterval: (query) => ((query.state.data?.length ?? 0) > 0 || watch ? 30_000 : false),
  });
}

export const refreshAlerts = (queryClient: QueryClient) =>
  void queryClient.invalidateQueries({ queryKey: safetyKeys.alerts });

/** "Estoy bien" / "Necesito ayuda". */
export const answerCheckIn = (alertId: string, answer: CheckInAnswer) =>
  api<SafetyAlert>(`/safety/alerts/${alertId}/${answer}`, { method: 'POST' });

export function useAnswerCheckIn() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ id, answer }: { id: string; answer: CheckInAnswer }) => answerCheckIn(id, answer),
    onSettled: () => refreshAlerts(queryClient),
  });
}

// ── SOS ──

/** The SOS this device is reporting a position for (survives screen changes; resumed from the API). */
export type SosState = { alertId: string; rideId: string | null; every: number } | null;
export const sosStore = createStore<SosState>(null);

const DEFAULT_SOS_SECONDS = 5;

/** POST /rides/{id}/sos with the current position; returns the live link for the trusted contacts. */
export async function triggerSos(rideId: string): Promise<SosResult> {
  const position = await getFreshPosition();
  const result = await api<SosResult>(`/rides/${rideId}/sos`, {
    method: 'POST',
    body: position ? { lat: position.lat, lng: position.lng } : {},
  });
  sosStore.set({ alertId: result.id, rideId, every: result.location_seconds || DEFAULT_SOS_SECONDS });
  return result;
}

/** The person who pressed SOS closes it (false alarm). */
export async function cancelSos(alertId: string) {
  await api<SafetyAlert>(`/safety/alerts/${alertId}/cancel`, { method: 'POST' });
  if (sosStore.get()?.alertId === alertId) sosStore.set(null);
}

/** After a restart: keep reporting for an SOS that is still open. */
export function resumeSos(alerts: SafetyAlert[] | undefined) {
  const open = alerts?.find((alert) => alert.kind === 'sos');
  const current = sosStore.get();
  if (open && current?.alertId !== open.id) {
    sosStore.set({ alertId: open.id, rideId: open.ride_id, every: current?.every ?? DEFAULT_SOS_SECONDS });
  } else if (!open && current && alerts) {
    sosStore.set(null);
  }
}

/** One position for the open SOS; false when the API says it is over (404 no_active_sos). */
export async function sendSosLocation(): Promise<boolean> {
  const position = await getFreshPosition();
  if (!position) return true;
  try {
    await api('/safety/location', { method: 'POST', body: { lat: position.lat, lng: position.lng } });
    return true;
  } catch (error) {
    const code = (error as { code?: string }).code;
    return code !== 'no_active_sos';
  }
}
