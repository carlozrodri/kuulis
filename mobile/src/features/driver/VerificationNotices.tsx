import { router } from 'expo-router';
import { useTranslation } from 'react-i18next';
import { Modal, Pressable, StyleSheet, View } from 'react-native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';

import { CalendarClock, CalendarX, FileClock, type Icon, ScanFace } from '@/components/icons';
import { Button, IconTile, type Tone, toneColors, Txt } from '@/components/ui';
import type { DocumentKind } from '@/lib/types';
import { blockHref, type DashboardAlert, expiryLabel, type OnlineBlock } from '@/lib/verification';
import { radius, space, useTheme } from '@/theme';

/** "Licencia de conducir, Certificado médico". */
function useDocNames() {
  const { t } = useTranslation();
  return (kinds: DocumentKind[]) => kinds.map((kind) => t(`driver.doc.${kind}.title`)).join(', ');
}

const MY_DOCUMENTS = { pathname: '/driver/my-documents' } as const;

/**
 * Doc 12 banner on the driver dashboard: a document expiring within 30 days, expired or without a date, or a
 * live selfie / re-verification to send. One at a time, the most urgent, with its direct action.
 */
export function VerificationBanner({ alert }: { alert: DashboardAlert }) {
  const { t } = useTranslation();
  const theme = useTheme();
  const names = useDocNames();

  let tone: Tone = 'warning';
  let icon: Icon = CalendarClock;
  let title: string;
  let body: string;
  let action: string;
  let href: Parameters<typeof router.push>[0] = MY_DOCUMENTS;
  switch (alert.reason) {
    case 'selfie_required':
      icon = ScanFace;
      title = t('verification.banner.selfieTitle');
      body = t(alert.checkKind === 'reverification' ? 'verification.banner.reverificationBody' : 'verification.banner.selfieBody');
      action = t('verification.banner.selfieAction');
      href = blockHref(alert);
      break;
    case 'document_expired':
      tone = alert.renewalPending ? 'info' : 'danger';
      icon = alert.renewalPending ? FileClock : CalendarX;
      title = alert.renewalPending ? t('verification.banner.expiredPendingTitle') : t('verification.banner.expiredTitle');
      body = t(alert.renewalPending ? 'verification.banner.expiredPendingBody' : 'verification.banner.expiredBody', {
        docs: names(alert.kinds),
      });
      action = alert.renewalPending ? t('verification.banner.see') : t('verification.myDocs.update');
      break;
    case 'missing_expiry':
      title = t('verification.banner.missingTitle');
      body = t('verification.banner.missingBody', { docs: names(alert.kinds) });
      action = t('verification.banner.missingAction');
      break;
    case 'expiring':
    default: {
      const label = expiryLabel(alert.daysLeft);
      title = `${names([alert.kind])}: ${t(label.key, { count: label.count }).toLocaleLowerCase()}`;
      body = t('verification.banner.expiringBody');
      action = t('verification.myDocs.update');
      break;
    }
  }
  const colors = toneColors(theme, tone);
  const BannerIcon = icon;

  return (
    <View accessibilityRole="alert" style={[styles.banner, { backgroundColor: colors.bg }]}>
      <BannerIcon size={20} color={colors.fg} strokeWidth={2.2} style={{ marginTop: 2 }} />
      <View style={{ flex: 1, gap: 2 }}>
        <Txt variant="label" style={{ color: colors.fg }}>
          {title}
        </Txt>
        <Txt variant="caption" style={{ color: theme.text }}>
          {body}
        </Txt>
      </View>
      <Button
        title={action}
        size="sm"
        variant={tone === 'danger' ? 'primary' : 'secondary'}
        style={{ marginTop: 0, alignSelf: 'center' }}
        accessibilityLabel={`${action}: ${title}`}
        onPress={() => router.push(href)}
      />
    </View>
  );
}

/**
 * Going online answered 403 document_expired or selfie_required: says why and opens the screen that solves
 * it, instead of a generic error toast.
 */
export function OnlineBlockSheet({ block, onClose }: { block: OnlineBlock | null; onClose: () => void }) {
  const { t } = useTranslation();
  const theme = useTheme();
  const insets = useSafeAreaInsets();
  const names = useDocNames();

  const selfie = block?.reason === 'selfie_required';
  const reverification = selfie && block.checkKind === 'reverification';
  const title = !block
    ? ''
    : selfie
      ? t(reverification ? 'verification.block.reverificationTitle' : 'verification.block.selfieTitle')
      : t('verification.block.expiredTitle');
  const body = !block
    ? ''
    : block.reason === 'selfie_required'
      ? t(reverification ? 'verification.block.reverificationBody' : 'verification.block.selfieBody')
      : block.kinds.length
        ? t('verification.block.expiredBody', { docs: names(block.kinds) })
        : t('verification.block.expiredBodyGeneric');
  const action = selfie ? t(reverification ? 'verification.block.reverificationAction' : 'verification.block.selfieAction') : t('verification.block.expiredAction');

  return (
    <Modal visible={!!block} transparent animationType="slide" onRequestClose={onClose} statusBarTranslucent>
      <Pressable
        accessibilityRole="button"
        accessibilityLabel={t('common.close')}
        style={[StyleSheet.absoluteFill, { backgroundColor: theme.backdrop }]}
        onPress={onClose}
      />
      <View style={[styles.sheet, { backgroundColor: theme.surface, paddingBottom: Math.max(insets.bottom, space.md) + space.xs }]}>
        <View style={[styles.handle, { backgroundColor: theme.border }]} />
        <IconTile icon={selfie ? ScanFace : CalendarX} tone={selfie ? 'warning' : 'danger'} size={64} />
        <View style={{ gap: space.xs }}>
          <Txt variant="heading" accessibilityRole="header">
            {title}
          </Txt>
          <Txt color="muted">{body}</Txt>
        </View>
        <View>
          <Button
            title={action}
            icon={selfie ? ScanFace : undefined}
            onPress={() => {
              if (!block) return;
              onClose();
              router.push(blockHref(block));
            }}
          />
          <Button title={t('verification.block.later')} variant="ghost" onPress={onClose} />
        </View>
      </View>
    </Modal>
  );
}

const styles = StyleSheet.create({
  banner: {
    flexDirection: 'row',
    alignItems: 'flex-start',
    gap: space.xs,
    borderRadius: radius.tile,
    paddingLeft: space.sm,
    paddingRight: space.xs,
    paddingVertical: space.sm,
  },
  sheet: {
    position: 'absolute',
    left: 0,
    right: 0,
    bottom: 0,
    borderTopLeftRadius: radius.sheet,
    borderTopRightRadius: radius.sheet,
    paddingHorizontal: space.lg,
    paddingTop: 10,
    gap: space.md,
  },
  handle: { width: 40, height: 5, borderRadius: 5, alignSelf: 'center', marginBottom: space.xs },
});
