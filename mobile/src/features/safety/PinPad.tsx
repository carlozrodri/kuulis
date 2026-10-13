import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { ActivityIndicator, Linking, Modal, Pressable, StyleSheet, View } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';

import { Check, Delete, Lock, MessageCircle, X } from '@/components/icons';
import { Button, IconButton, Notice, Txt } from '@/components/ui';
import { Avatar } from '@/features/ride/components';
import { useAppLinks } from '@/hooks/useBootstrap';
import { apiErrorMessage } from '@/i18n';
import { selectionHaptic } from '@/lib/feedback';
import { whatsappUrl } from '@/lib/profile';
import { cleanPin, PIN_LENGTH, pinAttemptsLeft, pinErrorKind } from '@/lib/safety';
import type { Ride } from '@/lib/types';
import { fonts, radius, space, useTheme } from '@/theme';

const KEYS = ['1', '2', '3', '4', '5', '6', '7', '8', '9', 'del', '0', 'ok'] as const;

/**
 * Driver (doc 11): a huge keypad (usable with gloves) for the passenger's 4-digit PIN before "Iniciar viaje".
 * Three wrong tries lock it: then the driver calls support or cancels the ride. Mount it only while open, so
 * each opening starts empty.
 */
export function PinPad({
  visible,
  ride,
  onClose,
  onSubmit,
  onCancelRide,
}: {
  visible: boolean;
  ride: Ride;
  onClose: () => void;
  onSubmit: (pin: string) => Promise<unknown>;
  onCancelRide: () => void;
}) {
  const { t } = useTranslation();
  const theme = useTheme();
  const { support_whatsapp: support } = useAppLinks();
  const [pin, setPin] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [locked, setLocked] = useState(false);
  const [sending, setSending] = useState(false);

  const submit = async (value: string) => {
    if (value.length !== PIN_LENGTH || sending) return;
    setSending(true);
    try {
      await onSubmit(value);
    } catch (e) {
      const kind = pinErrorKind(e);
      setPin('');
      if (kind === 'locked') setLocked(true);
      else if (kind === 'invalid') {
        const left = pinAttemptsLeft(e);
        setError(left != null ? t('safety.pin.wrongLeft', { count: left }) : t('safety.pin.wrong'));
      } else setError(apiErrorMessage(e));
    } finally {
      setSending(false);
    }
  };

  const press = (key: (typeof KEYS)[number]) => {
    selectionHaptic();
    if (key === 'del') return setPin((p) => p.slice(0, -1));
    if (key === 'ok') return void submit(pin);
    const next = cleanPin(pin + key);
    setPin(next);
    setError(null);
    if (next.length === PIN_LENGTH) void submit(next);
  };

  return (
    <Modal visible={visible} animationType="slide" onRequestClose={onClose} statusBarTranslucent>
      <SafeAreaView style={[styles.flex, { backgroundColor: theme.background }]} edges={['top', 'bottom', 'left', 'right']}>
        <View style={styles.header}>
          <IconButton icon={X} label={t('common.close')} onPress={onClose} />
        </View>
        <View style={styles.top}>
          <Avatar name={ride.passenger.first_name} photoUrl={ride.passenger.photo_url} size={56} />
          <Txt variant="heading" align="center" accessibilityRole="header">
            {t('safety.pin.askTitle', { name: ride.passenger.first_name })}
          </Txt>
          <Txt color="muted" align="center">
            {t('safety.pin.askBody')}
          </Txt>
        </View>

        {locked ? (
          <View style={styles.locked}>
            <Notice tone="danger">{t('safety.pin.locked')}</Notice>
            {support ? (
              <Button
                title={t('safety.pin.callSupport')}
                icon={MessageCircle}
                variant="secondary"
                onPress={() => void Linking.openURL(whatsappUrl(t('safety.pin.supportMessage'), support)).catch(() => undefined)}
              />
            ) : null}
            <Button title={t('safety.pin.cancelRide')} variant="danger" onPress={onCancelRide} />
          </View>
        ) : (
          <>
            <View style={styles.dots} accessibilityLabel={t('safety.pin.typed', { count: pin.length })}>
              {Array.from({ length: PIN_LENGTH }, (_, i) => (
                <View
                  key={i}
                  style={[
                    styles.slot,
                    { borderColor: error ? theme.danger : i === pin.length ? theme.primary : theme.border, backgroundColor: theme.surface },
                  ]}>
                  <Txt style={[styles.digit, { color: theme.text }]}>{pin[i] ?? ''}</Txt>
                </View>
              ))}
            </View>
            <View style={styles.message}>
              {sending ? (
                <ActivityIndicator color={theme.primary} />
              ) : error ? (
                <Txt variant="bodyStrong" align="center" style={{ color: theme.danger }}>
                  {error}
                </Txt>
              ) : null}
            </View>
            <View style={styles.pad}>
              {KEYS.map((key) => {
                const Icon = key === 'del' ? Delete : key === 'ok' ? Check : null;
                const isOk = key === 'ok';
                const disabled = sending || (isOk && pin.length < PIN_LENGTH) || (key === 'del' && !pin);
                return (
                  <Pressable
                    key={key}
                    accessibilityRole="button"
                    accessibilityLabel={key === 'del' ? t('safety.pin.delete') : isOk ? t('safety.pin.confirm') : key}
                    disabled={disabled}
                    onPress={() => press(key)}
                    style={({ pressed }) => [
                      styles.key,
                      {
                        backgroundColor: isOk ? theme.primary : pressed ? theme.surfaceAlt : theme.surface,
                        borderColor: theme.border,
                        opacity: disabled ? 0.45 : 1,
                      },
                    ]}>
                    {Icon ? (
                      <Icon size={30} color={isOk ? theme.onPrimary : theme.text} strokeWidth={2.4} />
                    ) : (
                      <Txt style={[styles.keyText, { color: theme.text }]}>{key}</Txt>
                    )}
                  </Pressable>
                );
              })}
            </View>
            <View style={styles.hint}>
              <Lock size={14} color={theme.muted} />
              <Txt variant="caption" color="muted">
                {t('safety.pin.attempts')}
              </Txt>
            </View>
          </>
        )}
      </SafeAreaView>
    </Modal>
  );
}

const styles = StyleSheet.create({
  flex: { flex: 1 },
  header: { flexDirection: 'row', paddingHorizontal: space.md, paddingTop: space.xs },
  top: { alignItems: 'center', gap: space.xs, paddingHorizontal: space.lg },
  dots: { flexDirection: 'row', justifyContent: 'center', gap: space.sm, marginTop: space.lg },
  slot: { width: 64, height: 76, borderRadius: radius.field, borderWidth: 2, alignItems: 'center', justifyContent: 'center' },
  digit: { fontFamily: fonts.extrabold, fontSize: 36 },
  message: { minHeight: 44, alignItems: 'center', justifyContent: 'center', paddingHorizontal: space.lg },
  pad: { flexDirection: 'row', flexWrap: 'wrap', justifyContent: 'center', gap: space.sm, paddingHorizontal: space.lg },
  // Big targets: drivers type with gloves on.
  key: { width: '30%', height: 76, borderRadius: radius.tile, borderWidth: 1.5, alignItems: 'center', justifyContent: 'center' },
  keyText: { fontFamily: fonts.bold, fontSize: 32 },
  hint: { flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: space.xxs, marginTop: space.md },
  locked: { gap: space.sm, padding: space.lg, marginTop: space.lg },
});
