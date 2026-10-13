import { useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import {
  KeyboardAvoidingView,
  Linking,
  Modal,
  Platform,
  Pressable,
  ScrollView,
  Share,
  StyleSheet,
  useWindowDimensions,
  View,
} from 'react-native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';

import {
  Bike,
  Check,
  CircleEllipsis,
  Clock,
  HardHat,
  type Icon,
  MapPin,
  MapPinned,
  MessageCircle,
  RotateCcw,
  ShieldAlert,
  UserX,
  Wrench,
  X,
} from '@/components/icons';
import { Button, Field, IconButton, Notice, Row, Txt } from '@/components/ui';
import { selectionHaptic } from '@/lib/feedback';
import { whatsappUrl } from '@/lib/profile';
import {
  CANCEL_REASONS,
  type CancelSheetKind,
  cancelSheetKind,
  formatClock,
  formatPlate,
  passengerCancelCounts,
  secondsUntil,
  shortAddress,
} from '@/lib/ride';
import type { CancelReasonCode, CancelRideInput, Ride } from '@/lib/types';
import { radius, space, useTheme } from '@/theme';

/** Re-renders every `interval` ms (clocks, ETAs). */
export function useNow(interval = 1000) {
  const [now, setNow] = useState(() => Date.now());
  useEffect(() => {
    const timer = setInterval(() => setNow(Date.now()), interval);
    return () => clearInterval(timer);
  }, [interval]);
  return now;
}

const REASON_ICONS: Record<CancelReasonCode, Icon> = {
  driver_late: Clock,
  changed_plans: RotateCcw,
  driver_asked: MessageCircle,
  vehicle_mismatch: Bike,
  wrong_pickup: MapPin,
  wrong_address: MapPinned,
  no_helmet: HardHat,
  vehicle_problem: Wrench,
  safety_concern: ShieldAlert,
  no_show: UserX,
  other: CircleEllipsis,
};

/** Reasons with a consequence worth saying next to them. */
const REASON_HINTS: Partial<Record<CancelReasonCode, string>> = {
  vehicle_mismatch: 'cancel.hint.vehicle_mismatch',
  safety_concern: 'cancel.hint.safety_concern',
};

/**
 * Doc 15: why you cancel, as a `reason_code` plus optional free text. The passenger is told when cancelling now
 * counts (the free minutes after a driver accepts are over); the driver, that it counts toward their rate and
 * that the passenger gets another driver. While still searching the reason is optional.
 */
export function CancelSheet({
  visible,
  ride,
  role,
  loading,
  onClose,
  onConfirm,
}: {
  visible: boolean;
  ride: Ride;
  role: 'passenger' | 'driver';
  loading?: boolean;
  onClose: () => void;
  onConfirm: (input: CancelRideInput) => void;
}) {
  const theme = useTheme();
  const insets = useSafeAreaInsets();
  const { t } = useTranslation();
  const kind = cancelSheetKind(ride, role);
  const close = loading ? undefined : onClose;
  return (
    <Modal visible={visible} transparent animationType="slide" onRequestClose={close} statusBarTranslucent>
      <Pressable
        accessibilityRole="button"
        accessibilityLabel={t('common.close')}
        style={[StyleSheet.absoluteFill, { backgroundColor: theme.backdrop }]}
        onPress={close}
      />
      <KeyboardAvoidingView behavior={Platform.OS === 'ios' ? 'padding' : undefined} style={styles.anchor} pointerEvents="box-none">
        <View style={[styles.sheet, { backgroundColor: theme.surface, paddingBottom: Math.max(insets.bottom, space.md) + space.xs }]}>
          <View style={[styles.handle, { backgroundColor: theme.border }]} />
          <Row style={{ alignItems: 'flex-start' }}>
            <View style={{ flex: 1, gap: 4 }}>
              <Txt variant="heading" accessibilityRole="header">
                {kind === 'searching' ? t('cancel.searchingTitle') : t('cancel.title')}
              </Txt>
              <Txt color="muted">{t(`cancel.subtitle.${kind}`)}</Txt>
            </View>
            <IconButton icon={X} label={t('common.close')} onPress={close} tone="plain" size={40} />
          </Row>
          {/* Mounted only while visible, so each opening starts with nothing picked. */}
          {visible ? <CancelForm ride={ride} kind={kind} loading={loading} onClose={onClose} onConfirm={onConfirm} /> : null}
        </View>
      </KeyboardAvoidingView>
    </Modal>
  );
}

function CancelForm({
  ride,
  kind,
  loading,
  onClose,
  onConfirm,
}: {
  ride: Ride;
  kind: CancelSheetKind;
  loading?: boolean;
  onClose: () => void;
  onConfirm: (input: CancelRideInput) => void;
}) {
  const { t } = useTranslation();
  const theme = useTheme();
  const { height } = useWindowDimensions();
  const now = useNow(1000);
  const [code, setCode] = useState<CancelReasonCode | null>(null);
  const [text, setText] = useState('');
  const optional = kind === 'searching';
  const counts = kind === 'passenger' && passengerCancelCounts(ride, now);
  const freeLeft = kind === 'passenger' && !counts ? secondsUntil(ride.cancel_free_until, now) : 0;

  return (
    <>
      <ScrollView
        style={{ maxHeight: height * 0.5, marginTop: space.sm }}
        keyboardShouldPersistTaps="handled"
        showsVerticalScrollIndicator={false}>
        <View accessibilityRole="radiogroup" accessibilityLabel={t('cancel.title')}>
          {CANCEL_REASONS[kind].map((reason, index, all) => (
            <ReasonRow
              key={reason}
              icon={REASON_ICONS[reason]}
              label={t(`cancel.reason.${reason}`)}
              hint={REASON_HINTS[reason] ? t(REASON_HINTS[reason]) : undefined}
              selected={code === reason}
              divider={index < all.length - 1}
              onPress={() => {
                selectionHaptic();
                setCode(reason);
              }}
            />
          ))}
        </View>
        <View style={{ marginTop: space.sm }}>
          <Field
            label={code === 'other' ? t('cancel.detailsOther') : t('cancel.details')}
            value={text}
            onChangeText={setText}
            placeholder={t('cancel.detailsPlaceholder')}
            multiline
            maxLength={500}
            style={styles.details}
          />
        </View>
      </ScrollView>

      {counts ? (
        <Notice tone="warning" style={{ marginBottom: space.xs }}>
          {t('cancel.countsWarning')}
        </Notice>
      ) : freeLeft > 0 ? (
        <View style={[styles.free, { backgroundColor: theme.surfaceAlt }]}>
          <Clock size={16} color={theme.scheme === 'dark' ? theme.primary : theme.primaryPressed} strokeWidth={2.4} />
          <Txt variant="label" style={{ flex: 1 }}>
            {t('cancel.freeFor', { time: formatClock(freeLeft) })}
          </Txt>
        </View>
      ) : kind === 'driver' ? (
        <Notice tone="info" style={{ marginBottom: space.xs }}>
          {t('cancel.driverNote')}
        </Notice>
      ) : null}

      <Button
        title={t('ride.cancel')}
        variant="danger"
        loading={loading}
        disabled={!optional && !code}
        accessibilityHint={!optional && !code ? t('cancel.pickReason') : undefined}
        onPress={() => onConfirm({ ...(code ? { reason_code: code } : {}), ...(text.trim() ? { reason: text.trim() } : {}) })}
      />
      <Button
        title={kind === 'searching' ? t('cancel.keepSearching') : kind === 'driver' ? t('cancel.keepDriving') : t('cancel.keepRide')}
        variant="ghost"
        disabled={loading}
        onPress={onClose}
      />
    </>
  );
}

/** One reason, picked like a radio button. */
function ReasonRow({
  icon: ReasonIcon,
  label,
  hint,
  selected,
  divider,
  onPress,
}: {
  icon: Icon;
  label: string;
  hint?: string;
  selected: boolean;
  divider: boolean;
  onPress: () => void;
}) {
  const theme = useTheme();
  const fg = theme.scheme === 'dark' ? theme.primary : theme.primaryPressed;
  return (
    <Pressable
      accessibilityRole="radio"
      accessibilityState={{ checked: selected }}
      accessibilityLabel={hint ? `${label}. ${hint}` : label}
      onPress={onPress}
      style={({ pressed }) => [
        styles.reason,
        divider && { borderBottomWidth: 1, borderBottomColor: theme.divider },
        { opacity: pressed ? 0.7 : 1 },
      ]}>
      <View style={[styles.reasonIcon, { backgroundColor: selected ? theme.surfaceAlt : theme.background }]}>
        <ReasonIcon size={20} color={selected ? fg : theme.muted} strokeWidth={2.2} />
      </View>
      <View style={{ flex: 1 }}>
        <Txt variant="bodyStrong">{label}</Txt>
        {hint ? (
          <Txt variant="caption" color="muted">
            {hint}
          </Txt>
        ) : null}
      </View>
      <View style={[styles.radio, { borderColor: selected ? theme.primary : theme.border, backgroundColor: selected ? theme.primary : 'transparent' }]}>
        {selected ? <Check size={14} color={theme.onPrimary} strokeWidth={3} /> : null}
      </View>
    </Pressable>
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

const styles = StyleSheet.create({
  anchor: { flex: 1, justifyContent: 'flex-end' },
  sheet: {
    borderTopLeftRadius: radius.sheet,
    borderTopRightRadius: radius.sheet,
    paddingHorizontal: space.lg,
    paddingTop: 10,
  },
  handle: { width: 40, height: 5, borderRadius: 5, alignSelf: 'center', marginBottom: space.md },
  reason: { flexDirection: 'row', alignItems: 'center', gap: space.sm, paddingVertical: 10, minHeight: 56 },
  reasonIcon: { width: 40, height: 40, borderRadius: 13, alignItems: 'center', justifyContent: 'center' },
  radio: { width: 24, height: 24, borderRadius: 12, borderWidth: 2, alignItems: 'center', justifyContent: 'center' },
  details: { minHeight: 64, textAlignVertical: 'top' },
  free: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: space.xs,
    borderRadius: radius.tile,
    paddingHorizontal: space.md,
    paddingVertical: space.sm,
    marginBottom: space.xs,
  },
});
