import { router } from 'expo-router';
import { useTranslation } from 'react-i18next';
import { Linking } from 'react-native';

import { Flag, HeartHandshake, Lightbulb, PhoneCall, Share2 } from '@/components/icons';
import { Sheet, type SheetOption } from '@/components/ui';
import { shareRide, shareRideWhatsApp } from '@/features/ride/RideSheets';
import { useAppLinks, useFlag } from '@/hooks/useBootstrap';
import { useTrustedContacts } from '@/hooks/useSafety';
import { firstName } from '@/lib/profile';
import type { Ride } from '@/lib/types';

import { shareLive } from './share';
import { openSafetyTips } from './SafetyTips';

/**
 * Sends the ride: the live link (doc 11), or the text with the moto's details when links are switched off or
 * the link fails. To one phone over WhatsApp, or through the share sheet.
 */
export function useRideShare(ride: Ride) {
  const { t } = useTranslation();
  const live = useFlag('share_live_link');
  return (phone?: string | null, sheet = false) => {
    const fallback = () => (sheet ? shareRide(ride, t) : shareRideWhatsApp(ride, t, phone));
    if (!live) return void fallback();
    void shareLive(ride, t, { phone, sheet }).catch(() => void fallback());
  };
}

/**
 * Safety tools during a ride (passenger and driver, doc 11): call emergencies, share the ride live (a link that
 * follows the moto until it ends), send it to a trusted contact, report a problem and read the tips. The SOS
 * button sits on the map, always in reach.
 */
export function SafetySheet({ visible, ride, role, onClose }: { visible: boolean; ride: Ride; role: 'passenger' | 'driver'; onClose: () => void }) {
  const { t } = useTranslation();
  // Remote emergency number (doc 10), 911 by default.
  const { emergency } = useAppLinks();
  const live = useFlag('share_live_link');
  const contacts = useTrustedContacts(visible).data ?? [];
  const send = useRideShare(ride);

  const options: SheetOption[] = [
    {
      label: t('safety.call911', { number: emergency }),
      hint: t('safety.call911Hint'),
      icon: PhoneCall,
      destructive: true,
      onPress: () => void Linking.openURL(`tel:${emergency}`).catch(() => undefined),
    },
    {
      label: live ? t('safety.shareLive') : t('safety.share'),
      hint: live ? t('safety.shareLiveHint') : t('safety.shareHint'),
      icon: Share2,
      onPress: () => send(null, true),
    },
    ...contacts.map((contact) => ({
      label: t('safety.sendContact', { name: firstName(contact.name) }),
      hint: t('safety.sendContactHint'),
      icon: HeartHandshake,
      onPress: () => send(contact.phone),
    })),
  ];
  if (!contacts.length) {
    options.push({
      label: t('safety.addContact'),
      hint: t('safety.addContactHint'),
      icon: HeartHandshake,
      onPress: () => router.push('/profile/contact'),
    });
  }
  options.push(
    {
      label: t('safety.report'),
      hint: t('safety.reportHint'),
      icon: Flag,
      onPress: () => router.push({ pathname: '/report', params: { ride_id: ride.id } }),
    },
    {
      label: t('safety.tips.open'),
      icon: Lightbulb,
      onPress: () => openSafetyTips(role),
    },
  );

  return <Sheet visible={visible} title={t('safety.title')} subtitle={t('safety.subtitle')} onClose={onClose} options={options} />;
}
