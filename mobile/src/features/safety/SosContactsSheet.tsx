import { router } from 'expo-router';
import { useTranslation } from 'react-i18next';
import { Share } from 'react-native';

import { HeartHandshake, Share2 } from '@/components/icons';
import { Sheet, type SheetOption } from '@/components/ui';
import { useTrustedContacts } from '@/hooks/useSafety';
import { firstName } from '@/lib/profile';
import { liveShareMessage } from '@/lib/safety';
import { useStore } from '@/lib/store';

import { sendText } from './share';
import { sosSheetOpen, sosShare } from './store';

/**
 * After an SOS: send the live link to each trusted contact (WhatsApp opens with the text ready). The sheet
 * closes on every tap; the SOS banner opens it again for the next contact.
 */
export function SosContactsSheet() {
  const { t } = useTranslation();
  const open = useStore(sosSheetOpen);
  const share = useStore(sosShare);
  const contacts = useTrustedContacts(!!share).data ?? [];
  if (!share) return null;
  const message = liveShareMessage(share.ride, share.url, t, true);

  const options: SheetOption[] = contacts.map((contact) => ({
    label: t('safety.sos.sendTo', { name: firstName(contact.name) }),
    hint: t('safety.sos.sendToHint'),
    icon: HeartHandshake,
    destructive: true,
    onPress: () => void sendText(message, contact.phone),
  }));
  options.push({
    label: t('safety.sos.shareOther'),
    icon: Share2,
    onPress: () => void Share.share({ message }).catch(() => undefined),
  });
  if (!contacts.length) {
    options.push({
      label: t('safety.addContact'),
      hint: t('safety.addContactHint'),
      icon: HeartHandshake,
      onPress: () => router.push('/profile/contact'),
    });
  }

  return (
    <Sheet
      visible={open}
      title={t('safety.sos.sheetTitle')}
      subtitle={t('safety.sos.sheetBody')}
      onClose={() => sosSheetOpen.set(false)}
      options={options}
    />
  );
}
