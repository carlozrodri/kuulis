import { useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Linking, Share } from 'react-native';

import { CircleHelp, CircleX, PhoneCall, Share2 } from '@/components/icons';
import { Sheet } from '@/components/ui';
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

export function shareRide(ride: Ride, t: (key: string, options?: Record<string, unknown>) => string) {
  const vehicle = ride.driver?.vehicle;
  const message = t('ride.shareMessage', {
    driver: ride.driver?.first_name ?? '',
    vehicle: vehicle ? `${vehicle.brand} ${vehicle.model} ${vehicle.color}`.trim() : '',
    plate: formatPlate(vehicle?.plate),
    pickup: shortAddress(ride.pickup.address),
    dropoff: shortAddress(ride.dropoff.address),
    maps: `https://maps.google.com/?q=${ride.dropoff.lat},${ride.dropoff.lng}`,
  });
  return Share.share({ message }).catch(() => undefined);
}

/** Safety tools: call emergencies, share the trip. */
export function SafetySheet({ visible, ride, onClose }: { visible: boolean; ride: Ride; onClose: () => void }) {
  const { t } = useTranslation();
  return (
    <Sheet
      visible={visible}
      title={t('safety.title')}
      subtitle={t('safety.subtitle')}
      onClose={onClose}
      options={[
        {
          label: t('safety.call911'),
          hint: t('safety.call911Hint'),
          icon: PhoneCall,
          destructive: true,
          onPress: () => void Linking.openURL('tel:911').catch(() => undefined),
        },
        {
          label: t('safety.share'),
          hint: t('safety.shareHint'),
          icon: Share2,
          onPress: () => void shareRide(ride, t),
        },
      ]}
    />
  );
}
