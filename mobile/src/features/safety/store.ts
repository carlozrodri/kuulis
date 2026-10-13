import { createStore } from '@/lib/store';
import type { Ride } from '@/lib/types';

/** The live link of the open SOS and the ride it is about, so the SOS banner can send it again. */
export const sosShare = createStore<{ ride: Ride; url: string } | null>(null);
/** Whether the "send the link to your contacts" sheet is showing. */
export const sosSheetOpen = createStore(false);
