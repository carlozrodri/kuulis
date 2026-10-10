import { type QueryClient, useInfiniteQuery, useMutation, useQuery, useQueryClient } from '@tanstack/react-query';

import { routedRides } from '@/features/ride/store';
import { ApiError, api } from '@/lib/api';
import { isActiveStatus, isTerminalStatus, mergeRide } from '@/lib/ride';
import type {
  DriverState,
  DriverStats,
  GeoResult,
  Offer,
  Page,
  PaymentMethod,
  Place,
  Quote,
  Ride,
  RideMessage,
  VehicleType,
} from '@/lib/types';

export const rideKeys = {
  all: ['rides'] as const,
  active: ['rides', 'active'] as const,
  pendingRating: ['rides', 'pending-rating'] as const,
  detail: (id: string) => ['rides', 'detail', id] as const,
  messages: (id: string) => ['rides', 'messages', id] as const,
  history: (role: 'passenger' | 'driver') => ['rides', 'history', role] as const,
  // Under 'rides' so every ride re-sync also refreshes the driver's earnings.
  driverStats: ['rides', 'driver-stats'] as const,
  driverState: ['drivers', 'me', 'state'] as const,
};

// ── Cache updates (shared by HTTP responses and WS events) ──

/** Writes a ride snapshot everywhere it is cached. */
export function applyRide(queryClient: QueryClient, ride: Ride) {
  queryClient.setQueryData<Ride>(rideKeys.detail(ride.id), (current) => mergeRide(current, ride));
  queryClient.setQueryData<Ride | null>(rideKeys.active, (current) => {
    if (isActiveStatus(ride.status)) return mergeRide(current?.id === ride.id ? current : null, ride);
    return current?.id === ride.id ? null : current;
  });
  if (isTerminalStatus(ride.status)) {
    void queryClient.invalidateQueries({ queryKey: rideKeys.pendingRating });
    void queryClient.invalidateQueries({ queryKey: ['rides', 'history'] });
    void queryClient.invalidateQueries({ queryKey: rideKeys.driverState });
    // A completed ride with a promotion credits the driver's wallet.
    if (ride.status === 'completed') void queryClient.invalidateQueries({ queryKey: ['wallet'] });
  }
}

export function applyDriverLocation(
  queryClient: QueryClient,
  event: { ride_id: string; lat: number; lng: number; heading?: number | null },
) {
  const update = (ride: Ride | null | undefined) =>
    ride && ride.id === event.ride_id
      ? { ...ride, driver_location: { lat: event.lat, lng: event.lng, heading: event.heading ?? null } }
      : ride;
  queryClient.setQueryData<Ride>(rideKeys.detail(event.ride_id), (ride) => update(ride) ?? undefined);
  queryClient.setQueryData<Ride | null>(rideKeys.active, (ride) => update(ride) ?? null);
}

/** Appends a chat message once (WS and POST can both deliver it). Returns true when it was new. */
export function applyMessage(queryClient: QueryClient, message: RideMessage): boolean {
  let added = false;
  queryClient.setQueryData<RideMessage[]>(rideKeys.messages(message.ride_id), (messages) => {
    if (!messages) return messages; // not loaded yet: the screen fetches the full list
    if (messages.some((m) => m.id === message.id)) return messages;
    added = true;
    return [...messages, message];
  });
  return added;
}

export function setDriverOffer(queryClient: QueryClient, offer: Offer | null) {
  queryClient.setQueryData<DriverState>(rideKeys.driverState, (state) => ({
    online: state?.online ?? true,
    active_ride_id: state?.active_ride_id ?? null,
    current_offer: offer,
  }));
}

// ── Queries ──

/** The ride in progress for this user (as passenger or driver), or null. */
export function useActiveRide(enabled = true) {
  return useQuery({
    queryKey: rideKeys.active,
    queryFn: () => api<Ride | null>('/rides/active'),
    enabled,
    staleTime: 15_000,
  });
}

/** A completed ride this user still has to rate (blocks new rides until rated). */
export function usePendingRating(enabled = true) {
  return useQuery({
    queryKey: rideKeys.pendingRating,
    queryFn: () => api<Ride | null>('/rides/pending-rating'),
    enabled,
    staleTime: 60_000,
  });
}

export function useRide(id: string | undefined) {
  const queryClient = useQueryClient();
  return useQuery({
    queryKey: rideKeys.detail(id ?? ''),
    queryFn: async () => {
      const ride = await api<Ride>(`/rides/${id}`);
      return mergeRide(queryClient.getQueryData<Ride>(rideKeys.detail(ride.id)), ride);
    },
    enabled: !!id,
    initialData: () => {
      const active = queryClient.getQueryData<Ride | null>(rideKeys.active);
      return active && active.id === id ? active : undefined;
    },
    initialDataUpdatedAt: () => queryClient.getQueryState(rideKeys.active)?.dataUpdatedAt,
    staleTime: 10_000,
  });
}

export function useRideMessages(id: string | undefined) {
  return useQuery({
    queryKey: rideKeys.messages(id ?? ''),
    queryFn: () => api<RideMessage[]>(`/rides/${id}/messages`),
    enabled: !!id,
    staleTime: 30_000,
  });
}

export function useDriverStats(enabled = true) {
  return useQuery({
    queryKey: rideKeys.driverStats,
    queryFn: () => api<DriverStats>('/drivers/me/stats'),
    enabled,
  });
}

export function useRideHistory(role: 'passenger' | 'driver') {
  return useInfiniteQuery({
    queryKey: rideKeys.history(role),
    initialPageParam: 0,
    queryFn: ({ pageParam }) => api<Page<Ride>>('/rides', { query: { role, limit: 20, offset: pageParam } }),
    getNextPageParam: (last) => (last.offset + last.items.length < last.total ? last.offset + last.items.length : undefined),
  });
}

export function useDriverState(enabled: boolean) {
  return useQuery({
    queryKey: rideKeys.driverState,
    queryFn: () => api<DriverState>('/drivers/me/state'),
    enabled,
    staleTime: 15_000,
  });
}

export function useGeoSearch(q: string, near: { lat: number; lng: number } | null) {
  const query = q.trim();
  return useQuery({
    queryKey: ['geo', 'search', query, near ? Math.round(near.lat * 100) : null, near ? Math.round(near.lng * 100) : null],
    queryFn: ({ signal }) =>
      api<GeoResult[]>('/geo/search', { query: { q: query, lat: near?.lat, lng: near?.lng }, signal }),
    enabled: query.length >= 3,
    staleTime: 5 * 60_000,
    placeholderData: (previous) => previous,
  });
}

export const reverseGeocode = (lat: number, lng: number) => api<GeoResult>('/geo/reverse', { query: { lat, lng } });

export const quoteKey = (
  pickup: Place | null,
  dropoff: Place | null,
  vehicleType: VehicleType = 'moto',
  promoCode: string | null = null,
) => ['quote', vehicleType, pickup?.lat, pickup?.lng, dropoff?.lat, dropoff?.lng, promoCode ?? ''] as const;

/** POST /rides/quote. With `promo_code` the API answers 400 promotion_invalid when the code does not apply. */
export const fetchQuote = (
  pickup: Place,
  dropoff: Place,
  vehicleType: VehicleType = 'moto',
  promoCode: string | null = null,
  signal?: AbortSignal,
) =>
  api<Quote>('/rides/quote', {
    method: 'POST',
    body: { pickup, dropoff, vehicle_type: vehicleType, ...(promoCode ? { promo_code: promoCode } : {}) },
    signal,
  });

export function useQuote(
  pickup: Place | null,
  dropoff: Place | null,
  vehicleType: VehicleType = 'moto',
  promoCode: string | null = null,
) {
  return useQuery({
    queryKey: quoteKey(pickup, dropoff, vehicleType, promoCode),
    queryFn: ({ signal }) => fetchQuote(pickup!, dropoff!, vehicleType, promoCode, signal),
    enabled: !!pickup && !!dropoff,
    staleTime: Infinity,
    gcTime: 5 * 60_000,
    retry: (count, error) => count < 2 && !(error as { status?: number }).status,
  });
}

// ── Mutations ──

export function useRequestRide() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (input: { quote_id: string; payment_method: PaymentMethod }) =>
      api<Ride>('/rides', { method: 'POST', body: input }),
    onSuccess: (ride) => {
      // The requesting screen opens the ride itself.
      routedRides.add(ride.id);
      applyRide(queryClient, ride);
    },
  });
}

/**
 * Quotes the same trip again and requests it (no_drivers retry, driver cancelled). Automatic promotions apply
 * again; if one runs out between the quote and the request (409 promotion_unavailable) it quotes once more.
 */
export async function requestAgain(ride: Ride, attempt = 0): Promise<Ride> {
  const quote = await fetchQuote(ride.pickup, ride.dropoff, ride.vehicle_type);
  try {
    return await api<Ride>('/rides', {
      method: 'POST',
      body: { quote_id: quote.quote_id, payment_method: ride.payment_method },
    });
  } catch (error) {
    if (attempt === 0 && error instanceof ApiError && error.code === 'promotion_unavailable') return requestAgain(ride, 1);
    throw error;
  }
}

export function useCancelRide() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ id, reason }: { id: string; reason?: string }) =>
      api<Ride>(`/rides/${id}/cancel`, { method: 'POST', body: reason ? { reason } : {} }),
    onSuccess: (ride) => applyRide(queryClient, ride),
    onError: () => void queryClient.invalidateQueries({ queryKey: rideKeys.all }),
  });
}

export function useDriverRideAction() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ id, action }: { id: string; action: 'arrive' | 'start' | 'complete' }) =>
      api<Ride>(`/rides/${id}/${action}`, { method: 'POST' }),
    onSuccess: (ride) => applyRide(queryClient, ride),
    onError: () => void queryClient.invalidateQueries({ queryKey: rideKeys.all }),
  });
}

export function useSendMessage(rideId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (text: string) => api<RideMessage>(`/rides/${rideId}/messages`, { method: 'POST', body: { text } }),
    onSuccess: (message) => applyMessage(queryClient, message),
  });
}

export function useRateRide() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ id, ...body }: { id: string; stars: number; tags: string[]; comment?: string }) =>
      api(`/rides/${id}/rating`, { method: 'POST', body }),
    onSuccess: () => {
      queryClient.setQueryData(rideKeys.pendingRating, null);
      void queryClient.invalidateQueries({ queryKey: rideKeys.pendingRating });
      void queryClient.invalidateQueries({ queryKey: ['rides', 'history'] });
      void queryClient.invalidateQueries({ queryKey: rideKeys.driverState });
    },
  });
}

// ── Driver availability and offers ──

export function useGoOnline() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (position: { lat: number; lng: number }) =>
      api<DriverState | undefined>('/drivers/me/online', { method: 'POST', body: position }),
    onSuccess: (state) => {
      queryClient.setQueryData<DriverState>(rideKeys.driverState, (current) =>
        state && typeof state === 'object' && 'online' in state
          ? state
          : { online: true, active_ride_id: current?.active_ride_id ?? null, current_offer: current?.current_offer ?? null },
      );
      void queryClient.invalidateQueries({ queryKey: rideKeys.driverState });
    },
  });
}

export function useGoOffline() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: () => api('/drivers/me/offline', { method: 'POST' }),
    onSuccess: () => {
      queryClient.setQueryData<DriverState>(rideKeys.driverState, (current) => ({
        online: false,
        active_ride_id: current?.active_ride_id ?? null,
        current_offer: null,
      }));
      void queryClient.invalidateQueries({ queryKey: rideKeys.driverState });
    },
  });
}

export function useOfferResponse() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ rideId, accept }: { rideId: string; accept: boolean }) =>
      api<Ride | undefined>(`/rides/${rideId}/${accept ? 'accept' : 'decline'}`, { method: 'POST' }),
    onSuccess: (ride, { accept }) => {
      setDriverOffer(queryClient, null);
      if (accept && ride && typeof ride === 'object' && 'id' in ride) routedRides.add(ride.id);
      if (accept && ride && typeof ride === 'object' && 'status' in ride) applyRide(queryClient, ride);
      if (accept) void queryClient.invalidateQueries({ queryKey: rideKeys.active });
    },
    onError: () => {
      setDriverOffer(queryClient, null);
      void queryClient.invalidateQueries({ queryKey: rideKeys.driverState });
    },
  });
}
