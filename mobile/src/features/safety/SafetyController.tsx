import { useQueryClient } from '@tanstack/react-query';
import { useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Alert, Linking, Modal, Pressable, StyleSheet, View } from 'react-native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';

import { CircleCheck, ShieldAlert, Siren } from '@/components/icons';
import { showToast } from '@/components/Toast';
import { Button, IconTile, Txt } from '@/components/ui';
import { useNow } from '@/features/ride/RideSheets';
import { useAppLinks } from '@/hooks/useBootstrap';
import { useRealtimeEvent } from '@/hooks/useRealtime';
import { useActiveRide } from '@/hooks/useRides';
import {
  cancelSos,
  refreshAlerts,
  resumeSos,
  sendSosLocation,
  sosStore,
  useActiveAlerts,
  useAnswerCheckIn,
} from '@/hooks/useSafety';
import { apiErrorMessage } from '@/i18n';
import { heavyHaptic } from '@/lib/feedback';
import { secondsToAnswer } from '@/lib/safety';
import { useStore } from '@/lib/store';
import type { SafetyAlert } from '@/lib/types';
import { useAuth } from '@/providers/AuthProvider';
import { radius, space, useTheme } from '@/theme';

import { SafetyTips } from './SafetyTips';
import { SosContactsSheet } from './SosContactsSheet';
import { sosSheetOpen, sosShare } from './store';

/**
 * Trip safety that lives above every screen (doc 11): the "¿Todo bien?" question, the banner of an open SOS
 * (with its position sent every few seconds, even after the ride ends) and the sheet to warn the contacts.
 */
export function SafetyController() {
  const { user } = useAuth();
  const queryClient = useQueryClient();
  const ride = useActiveRide(!!user).data;
  const alerts = useActiveAlerts(!!user, !!ride);
  const sos = useStore(sosStore);

  useEffect(() => {
    if (alerts.data) resumeSos(alerts.data);
  }, [alerts.data]);

  useRealtimeEvent('safety.check_in', () => refreshAlerts(queryClient));

  // While the SOS is open: the position every `every` seconds, until the API says it is closed.
  useEffect(() => {
    if (!sos) return;
    let stopped = false;
    const send = async () => {
      const open = await sendSosLocation();
      if (!open && !stopped) {
        sosStore.set(null);
        refreshAlerts(queryClient);
      }
    };
    void send();
    const timer = setInterval(() => void send(), sos.every * 1000);
    return () => {
      stopped = true;
      clearInterval(timer);
    };
  }, [sos, queryClient]);

  const checkIn = alerts.data?.find((alert) => alert.kind !== 'sos' && alert.status === 'checking');

  return (
    <>
      {sos ? <SosBanner alertId={sos.alertId} /> : null}
      {checkIn ? <CheckInModal key={checkIn.id} alert={checkIn} /> : null}
      <SosContactsSheet />
      <SafetyTips />
    </>
  );
}

function SosBanner({ alertId }: { alertId: string }) {
  const { t } = useTranslation();
  const theme = useTheme();
  const insets = useSafeAreaInsets();
  const queryClient = useQueryClient();
  const share = useStore(sosShare);

  const cancel = () =>
    Alert.alert(t('safety.sos.cancelTitle'), t('safety.sos.cancelBody'), [
      { text: t('common.back'), style: 'cancel' },
      {
        text: t('safety.sos.cancelConfirm'),
        style: 'destructive',
        onPress: () =>
          void cancelSos(alertId)
            .then(() => {
              sosShare.set(null);
              refreshAlerts(queryClient);
              showToast(t('safety.sos.cancelled'));
            })
            .catch((error) => showToast(apiErrorMessage(error), 'danger')),
      },
    ]);

  return (
    <View style={[styles.bannerWrap, { top: insets.top + 4 }]} pointerEvents="box-none">
      <View accessibilityRole="alert" style={[styles.banner, { backgroundColor: theme.danger }]}>
        <Siren size={18} color="#FFFFFF" strokeWidth={2.4} />
        <Txt variant="label" style={styles.bannerText} numberOfLines={2}>
          {t('safety.sos.active')}
        </Txt>
        {share ? (
          <Pressable accessibilityRole="button" hitSlop={8} onPress={() => sosSheetOpen.set(true)} style={styles.bannerAction}>
            <Txt variant="micro" style={styles.bannerText}>
              {t('safety.sos.notify')}
            </Txt>
          </Pressable>
        ) : null}
        <Pressable accessibilityRole="button" hitSlop={8} onPress={cancel} style={styles.bannerAction}>
          <Txt variant="micro" style={styles.bannerText}>
            {t('safety.sos.cancel')}
          </Txt>
        </Pressable>
      </View>
    </View>
  );
}

/** "¿Todo bien?": the ride stopped, left the route or is taking too long. No answer → the team is told. */
function CheckInModal({ alert }: { alert: SafetyAlert }) {
  const { t } = useTranslation();
  const theme = useTheme();
  const insets = useSafeAreaInsets();
  const { emergency } = useAppLinks();
  const answer = useAnswerCheckIn();
  const [hidden, setHidden] = useState(false);
  const now = useNow(1000);
  const left = secondsToAnswer(alert.check_in_deadline, now);

  useEffect(() => heavyHaptic(), []);

  const reply = (value: 'ok' | 'help') =>
    answer.mutate(
      { id: alert.id, answer: value },
      {
        onSuccess: () => {
          setHidden(true);
          showToast(value === 'ok' ? t('safety.checkIn.thanks') : t('safety.checkIn.helpSent'), value === 'ok' ? 'success' : 'danger');
          if (value === 'help') void Linking.openURL(`tel:${emergency}`).catch(() => undefined);
        },
        onError: (error) => showToast(apiErrorMessage(error), 'danger'),
      },
    );

  return (
    <Modal visible={!hidden} transparent animationType="fade" statusBarTranslucent onRequestClose={() => undefined}>
      <View style={[styles.backdrop, { backgroundColor: theme.backdrop }]}>
        <View style={[styles.card, { backgroundColor: theme.surface, marginBottom: Math.max(insets.bottom, space.md) }]}>
          <IconTile icon={ShieldAlert} tone="warning" size={56} />
          <Txt variant="heading" accessibilityRole="header">
            {t('safety.checkIn.title')}
          </Txt>
          <Txt color="muted">{t(`safety.checkIn.${alert.kind}`)}</Txt>
          {left != null ? (
            <Txt variant="caption" color="muted">
              {t('safety.checkIn.deadline', { count: left })}
            </Txt>
          ) : null}
          <Button title={t('safety.checkIn.ok')} icon={CircleCheck} loading={answer.isPending && answer.variables?.answer === 'ok'} onPress={() => reply('ok')} />
          <Button
            title={t('safety.checkIn.help')}
            icon={Siren}
            variant="danger"
            loading={answer.isPending && answer.variables?.answer === 'help'}
            onPress={() => reply('help')}
          />
        </View>
      </View>
    </Modal>
  );
}

const styles = StyleSheet.create({
  bannerWrap: { position: 'absolute', left: space.md, right: space.md, alignItems: 'center', zIndex: 95 },
  banner: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: space.xs,
    borderRadius: radius.pill,
    paddingLeft: 14,
    paddingRight: 6,
    paddingVertical: 6,
    maxWidth: 520,
  },
  bannerText: { color: '#FFFFFF', flexShrink: 1 },
  bannerAction: { backgroundColor: 'rgba(255, 255, 255, 0.22)', borderRadius: radius.pill, paddingHorizontal: 12, paddingVertical: 8 },
  backdrop: { flex: 1, justifyContent: 'flex-end', padding: space.md },
  card: { borderRadius: radius.card, padding: space.lg, gap: space.sm },
});
