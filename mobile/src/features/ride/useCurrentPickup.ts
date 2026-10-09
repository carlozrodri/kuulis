import { useEffect, useRef } from 'react';
import { useTranslation } from 'react-i18next';

import { useUserLocation } from '@/hooks/useLocation';
import { reverseGeocode } from '@/hooks/useRides';
import { useStore } from '@/lib/store';
import { haversineMeters } from '@/lib/ride';

import { rideDraft, setDraftPlace } from './store';

/**
 * Keeps the draft pickup on the user's current location (reverse-geocoded by GET /geo/reverse) until they
 * pick another pickup. Re-geocodes only after moving ~60 m.
 */
export function useCurrentPickup() {
  const { t } = useTranslation();
  const { position } = useUserLocation();
  const draft = useStore(rideDraft);
  const last = useRef<{ lat: number; lng: number } | null>(null);

  useEffect(() => {
    if (!position || !draft.pickupIsCurrent) return;
    const here = { lat: position.lat, lng: position.lng };
    const current = rideDraft.get().pickup;
    if (last.current && current && haversineMeters(last.current, here) < 60) return;
    last.current = here;
    // Show the coordinates right away; the street name follows.
    if (!current) setDraftPlace('pickup', { ...here, address: t('ride.currentLocation') }, true);
    reverseGeocode(here.lat, here.lng)
      .then((result) => {
        if (rideDraft.get().pickupIsCurrent && last.current === here) {
          setDraftPlace('pickup', { ...here, address: result.address || result.name || t('ride.currentLocation') }, true);
        }
      })
      .catch(() => undefined);
  }, [position, draft.pickupIsCurrent, t]);

  return draft.pickup;
}
