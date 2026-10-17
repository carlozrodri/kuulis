import { Linking, Share } from 'react-native';

import { createShareLink } from '@/hooks/useSafety';
import { whatsappUrl } from '@/lib/profile';
import { liveShareMessage, riderShareMessage } from '@/lib/safety';
import type { Ride } from '@/lib/types';

type Translate = (key: string, options?: Record<string, unknown>) => string;

/** WhatsApp to one number (or WhatsApp's own picker); the share sheet when WhatsApp is not there. */
export async function sendText(message: string, phone?: string | null) {
  try {
    await Linking.openURL(whatsappUrl(message, phone));
  } catch {
    await Share.share({ message }).catch(() => undefined);
  }
}

/**
 * Creates a live link (doc 11) and sends it: to a contact over WhatsApp, or through the share sheet.
 * Throws the API error so the caller can fall back to the text-only share.
 */
export async function shareLive(ride: Ride, t: Translate, target: { phone?: string | null; sheet?: boolean } = {}) {
  const link = await createShareLink(ride.id);
  const message = liveShareMessage(ride, link.url, t);
  if (target.sheet) await Share.share({ message }).catch(() => undefined);
  else await sendText(message, target.phone);
  return link;
}

/** Doc 23: the ride was requested for someone else; WhatsApp to them with the live link (driver, plate, PIN). */
export async function shareWithRider(ride: Ride, t: Translate) {
  const link = await createShareLink(ride.id, true);
  await sendText(riderShareMessage(ride, link.url, t), ride.rider_phone);
  return link;
}
