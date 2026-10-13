import { useState } from 'react';
import { useTranslation } from 'react-i18next';

import { HeartHandshake } from '@/components/icons';
import { Sheet } from '@/components/ui';
import { useTrustedContacts } from '@/hooks/useSafety';
import { firstName } from '@/lib/profile';
import { autoShareContacts } from '@/lib/safety';
import type { Ride } from '@/lib/types';

import { useRideShare } from './SafetySheet';
import { useTipsOpen } from './SafetyTips';

/** Rides whose offer was closed, so it shows once per ride (also after leaving the screen and coming back). */
const closed = new Set<string>();

/**
 * Doc 11: when a driver is assigned, offers to send the ride to the contacts with "compartir automáticamente"
 * on (within their hours). WhatsApp needs a tap per contact, so this is a one-tap prompt, never a silent send.
 */
export function AutoShareSheet({ ride }: { ride: Ride }) {
  const { t } = useTranslation();
  const contacts = useTrustedContacts(ride.status === 'driver_assigned').data;
  const send = useRideShare(ride);
  const tipsOpen = useTipsOpen();
  const [, rerender] = useState(0);
  const due = autoShareContacts(contacts, new Date());
  const open = ride.status === 'driver_assigned' && due.length > 0 && !closed.has(ride.id);

  return (
    <Sheet
      visible={open && !tipsOpen}
      title={t('safety.autoShare.title')}
      subtitle={t('safety.autoShare.body')}
      onClose={() => {
        closed.add(ride.id);
        rerender((n) => n + 1);
      }}
      options={due.map((contact) => ({
        label: t('safety.sendContact', { name: firstName(contact.name) }),
        hint: t('safety.sendContactHint'),
        icon: HeartHandshake,
        onPress: () => send(contact.phone),
      }))}
    />
  );
}
