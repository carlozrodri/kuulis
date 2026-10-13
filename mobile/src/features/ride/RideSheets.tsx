import { useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Linking, Share } from 'react-native';

import { CircleHelp, CircleX } from '@/components/icons';
import { Sheet } from '@/components/ui';
import { whatsappUrl } from '@/lib/profile';
import { CANCEL_REASONS, formatPlate, shortAddress } from '@/lib/ride';
import type { Ride } from '@/lib/types';

/** Re-renders every `interval` ms (clocks, ETAs). */
export function useNow(interval = 1000) {
  const [now, setNow] = useState(() => Date.now());
  useEffect(() => {
    const timer = setInterval(() => setNow(Date.now()), interval);
    return () => clearInterval(timer);
  }, [interval]);
  return now;
}

/** Choose why you cancel (sent as a stable code in `reason`). */
export function CancelSheet({
  visible,
  role,
  onClose,
  onCancel,
}: {
  visible: boolean;
  role: 'passenger' | 'driver';
  onClose: () => void;
  onCancel: (reason: string) => void;
}) {
  const { t } = useTranslation();
  return (
    <Sheet
      visible={visible}
      title={t('cancel.title')}
      subtitle={role === 'passenger' ? t('cancel.subtitlePassenger') : t('cancel.subtitleDriver')}
      onClose={onClose}
      options={CANCEL_REASONS[role].map((reason) => ({
        label: t(`cancel.reason.${reason}`),
        icon: reason === 'other' ? CircleHelp : CircleX,
        destructive: true,
        onPress: () => onCancel(reason),
      }))}
    />
  );
}

type Translate = (key: string, options?: Record<string, unknown>) => string;

function shareMessage(ride: Ride, t: Translate) {
  const vehicle = ride.driver?.vehicle;
  return t('ride.shareMessage', {
    driver: ride.driver?.first_name ?? '',
    vehicle: vehicle ? `${vehicle.brand} ${vehicle.model} ${vehicle.color}`.trim() : '',
    plate: formatPlate(vehicle?.plate),
    pickup: shortAddress(ride.pickup.address),
    dropoff: shortAddress(ride.dropoff.address),
    maps: `https://maps.google.com/?q=${ride.dropoff.lat},${ride.dropoff.lng}`,
  });
}

/** Any app (system share sheet). */
export function shareRide(ride: Ride, t: Translate) {
  return Share.share({ message: shareMessage(ride, t) }).catch(() => undefined);
}

/**
 * WhatsApp: straight to the trusted contact's chat, or WhatsApp's own chat picker without one.
 * wa.me opens the app when installed (no native query scheme needed); otherwise the share sheet.
 */
export async function shareRideWhatsApp(ride: Ride, t: Translate, phone?: string | null) {
  try {
    await Linking.openURL(whatsappUrl(shareMessage(ride, t), phone));
  } catch {
    await shareRide(ride, t);
  }
}
