import { router } from 'expo-router';
import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Platform, Share, StyleSheet, View } from 'react-native';

import { BookmarkPlus, Briefcase, House, Repeat, Share2, Star } from '@/components/icons';
import { showToast } from '@/components/Toast';
import { Button, Sheet } from '@/components/ui';
import { fetchRideReceipt } from '@/hooks/useRides';
import { apiErrorMessage } from '@/i18n';
import { selectionHaptic } from '@/lib/feedback';
import { receiptText } from '@/lib/receipt';
import type { PlaceKind, Ride } from '@/lib/types';
import { space } from '@/theme';

import { repeatRide } from './store';

/** "Repetir viaje" (doc 23): same pickup and destination, a fresh price on the quote screen. */
export function repeat(ride: Ride) {
  selectionHaptic();
  repeatRide(ride);
  router.push('/ride/quote');
}

/** The ride's receipt image (signed link) through the share sheet, with a text summary. */
export async function shareReceipt(ride: Ride, t: (key: string, options?: Record<string, unknown>) => string, language: string) {
  try {
    const receipt = await fetchRideReceipt(ride.id);
    const message = receiptText(receipt, t, language);
    // iOS shares the link as an attachment preview; Android only takes text.
    await Share.share(Platform.OS === 'ios' ? { message, url: receipt.image_url } : { message: `${message}\n${receipt.image_url}` });
  } catch (error) {
    showToast(apiErrorMessage(error), 'danger');
  }
}

const SAVE_ICONS = { home: House, work: Briefcase, other: Star } as const;

/** Doc 23, on a past ride: repeat it, share its receipt and save its destination as Casa, Trabajo or another place. */
export function RideActions({ ride, role }: { ride: Ride; role: 'passenger' | 'driver' }) {
  const { t, i18n } = useTranslation();
  const [sharing, setSharing] = useState(false);
  const [saveOpen, setSaveOpen] = useState(false);
  const passenger = role === 'passenger';
  const completed = ride.status === 'completed';

  const save = (kind: PlaceKind) =>
    router.push({
      pathname: '/profile/place',
      params: { kind, lat: String(ride.dropoff.lat), lng: String(ride.dropoff.lng), address: ride.dropoff.address },
    });

  return (
    <View style={styles.actions}>
      {passenger ? <Button title={t('rideActions.repeat')} icon={Repeat} variant="secondary" size="sm" style={styles.action} onPress={() => repeat(ride)} /> : null}
      {completed ? (
        <Button
          title={t('rideActions.receipt')}
          icon={Share2}
          variant="secondary"
          size="sm"
          style={styles.action}
          loading={sharing}
          onPress={() => {
            setSharing(true);
            void shareReceipt(ride, t, i18n.language).finally(() => setSharing(false));
          }}
        />
      ) : null}
      {passenger && ride.dropoff.address ? (
        <Button title={t('rideActions.save')} icon={BookmarkPlus} variant="secondary" size="sm" style={styles.action} onPress={() => setSaveOpen(true)} />
      ) : null}
      <Sheet
        visible={saveOpen}
        title={t('rideActions.saveTitle')}
        subtitle={ride.dropoff.address}
        onClose={() => setSaveOpen(false)}
        options={(['home', 'work', 'other'] as PlaceKind[]).map((kind) => ({
          label: kind === 'other' ? t('profile.saved.addOther') : t(`profile.saved.set_${kind}`),
          icon: SAVE_ICONS[kind],
          onPress: () => save(kind),
        }))}
      />
    </View>
  );
}

const styles = StyleSheet.create({
  actions: { flexDirection: 'row', flexWrap: 'wrap', gap: space.xs },
  action: { flexGrow: 1, marginTop: 0 },
});
