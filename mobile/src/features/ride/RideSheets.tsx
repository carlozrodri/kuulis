import { router } from 'expo-router';
import { useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Linking, Share } from 'react-native';

import { CircleHelp, CircleX, Flag, HeartHandshake, MessageCircle, PhoneCall, Share2 } from '@/components/icons';
import { Sheet } from '@/components/ui';
import { useAppLinks } from '@/hooks/useBootstrap';
import { whatsappUrl } from '@/lib/profile';
import { CANCEL_REASONS, formatPlate, shortAddress } from '@/lib/ride';
import type { Ride } from '@/lib/types';
import { useAuth } from '@/providers/AuthProvider';

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

/** Safety tools: call emergencies, report a problem, share the trip. */
export function SafetySheet({ visible, ride, onClose }: { visible: boolean; ride: Ride; onClose: () => void }) {
  const { t } = useTranslation();
  // Remote emergency number (doc 10), 911 by default.
  const { emergency } = useAppLinks();
  const { user } = useAuth();
  const contact = user?.trusted_contact_phone ? { name: user.trusted_contact_name ?? '', phone: user.trusted_contact_phone } : null;
  return (
    <Sheet
      visible={visible}
      title={t('safety.title')}
      subtitle={t('safety.subtitle')}
      onClose={onClose}
      options={[
        {
          label: t('safety.call911', { number: emergency }),
          hint: t('safety.call911Hint'),
          icon: PhoneCall,
          destructive: true,
          onPress: () => void Linking.openURL(`tel:${emergency}`).catch(() => undefined),
        },
        {
          label: t('safety.report'),
          hint: t('safety.reportHint'),
          icon: Flag,
          onPress: () => router.push({ pathname: '/report', params: { ride_id: ride.id } }),
        },
        contact
          ? {
              label: t('safety.sendContact', { name: contact.name }),
              hint: t('safety.sendContactHint'),
              icon: HeartHandshake,
              onPress: () => void shareRideWhatsApp(ride, t, contact.phone),
            }
          : {
              label: t('safety.addContact'),
              hint: t('safety.addContactHint'),
              icon: HeartHandshake,
              onPress: () => router.push('/profile/contact'),
            },
        {
          label: t('safety.whatsapp'),
          hint: t('safety.whatsappHint'),
          icon: MessageCircle,
          onPress: () => void shareRideWhatsApp(ride, t),
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
