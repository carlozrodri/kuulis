import { createStore } from '@/lib/store';

/**
 * "Conectarme ahora" after a live selfie (doc 12): the selfie screen sets it and goes back; the dashboard
 * goes online right away and clears it.
 */
export const connectRequest = createStore(0);
