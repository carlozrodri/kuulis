import { secureStorage } from '@/lib/storage';
import { createStore } from '@/lib/store';
import type { PaymentMethod, Place } from '@/lib/types';

export type DraftField = 'pickup' | 'dropoff';

export type RideDraft = {
  pickup: Place | null;
  /** True while the pickup is the user's current location (it follows the GPS until edited). */
  pickupIsCurrent: boolean;
  dropoff: Place | null;
  paymentMethod: PaymentMethod | null;
};

/** The ride being put together across search → pin → quote. */
export const rideDraft = createStore<RideDraft>({
  pickup: null,
  pickupIsCurrent: true,
  dropoff: null,
  paymentMethod: null,
});

export function setDraftPlace(field: DraftField, place: Place, fromCurrentLocation = false) {
  rideDraft.set((draft) =>
    field === 'pickup'
      ? { ...draft, pickup: place, pickupIsCurrent: fromCurrentLocation }
      : { ...draft, dropoff: place },
  );
}

export function resetDraftDestination() {
  rideDraft.set((draft) => ({ ...draft, dropoff: null }));
}

const PAYMENT_KEY = 'kuulis.payment_method';

/** Remembers the last payment method on the device. */
export function setDraftPayment(method: PaymentMethod) {
  rideDraft.set((draft) => ({ ...draft, paymentMethod: method }));
  void secureStorage.set(PAYMENT_KEY, method).catch(() => undefined);
}

export async function loadSavedPayment() {
  if (rideDraft.get().paymentMethod) return;
  const saved = await secureStorage.get(PAYMENT_KEY).catch(() => null);
  if (saved && !rideDraft.get().paymentMethod) {
    rideDraft.set((draft) => ({ ...draft, paymentMethod: saved as PaymentMethod }));
  }
}

/** Unread chat messages per ride (reset when the chat screen is open). */
export const chatUnread = createStore<Record<string, number>>({});
/** Ride whose chat is on screen right now. */
export const chatOpen = createStore<string | null>(null);

export function bumpUnread(rideId: string) {
  if (chatOpen.get() === rideId) return;
  chatUnread.set((counts) => ({ ...counts, [rideId]: (counts[rideId] ?? 0) + 1 }));
}

export function clearUnread(rideId: string) {
  chatUnread.set((counts) => (counts[rideId] ? { ...counts, [rideId]: 0 } : counts));
}

/** Rides whose screen was already opened (so the ride navigator does not open it a second time). */
export const routedRides = new Set<string>();
