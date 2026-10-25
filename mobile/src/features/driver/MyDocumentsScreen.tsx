import { router } from 'expo-router';
import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { RefreshControl, StyleSheet, View } from 'react-native';

import { ErrorState } from '@/components/ErrorState';
import { Calendar, ChevronLeft, FileText, Plus, RefreshCw } from '@/components/icons';
import { Button, Card, ErrorText, IconButton, IconTile, Notice, Row, Screen, Skeleton, StatusPill, Txt } from '@/components/ui';
import { useAppConfig, useDriverProfile, useSetDocumentExpiry } from '@/hooks/useDriver';
import { apiErrorMessage } from '@/i18n';
import { isoToDisplayDate } from '@/lib/driver';
import {
  documentBadge,
  type MyDocumentItem,
  myDocuments,
  onlineBlock,
  warningWindow,
} from '@/lib/verification';
import { radius, space, useTheme } from '@/theme';

import { ExpirySheet } from './ExpirySheet';
import { DOCUMENT_ICONS } from './meta';
import { CameraDeniedNotice, useDocumentUpload } from './useDocumentUpload';

const back = () => (router.canGoBack() ? router.back() : router.replace('/'));

/**
 * "Mis documentos" (doc 12): the approved driver's documents in use, each with its expiry ("Vence en 12 días",
 * "Vencido", "Falta la fecha", "En revisión") and a way to renew it. A renewal waits for review while the
 * current file stays in use; an expired one keeps the driver offline until the new one is approved.
 */
export function MyDocumentsScreen() {
  const { t } = useTranslation();
  const profile = useDriverProfile();
  const { config } = useAppConfig();
  const setExpiry = useSetDocumentExpiry();
  const { start, elements, error, cameraDenied, busy, uploadingKind } = useDocumentUpload();
  const [dating, setDating] = useState<MyDocumentItem | null>(null);
  const [dateError, setDateError] = useState<string>();

  const items = myDocuments(profile.data, config);
  const block = onlineBlock(profile.data?.verification);
  const expired = block?.reason === 'document_expired' ? block : null;

  const saveExpiry = (iso: string) => {
    if (!dating?.inUse) return;
    setDateError(undefined);
    setExpiry.mutate(
      { id: dating.inUse.id, expiresOn: iso },
      { onSuccess: () => setDating(null), onError: (e) => setDateError(apiErrorMessage(e)) },
    );
  };

  return (
    <Screen
      header={
        <Row style={{ paddingTop: space.xs, paddingBottom: space.md }}>
          <IconButton icon={ChevronLeft} label={t('common.back')} onPress={back} />
        </Row>
      }
      refreshControl={<RefreshControl refreshing={profile.isRefetching} onRefresh={() => void profile.refetch()} />}>
      <View style={{ alignItems: 'flex-start', gap: space.sm, marginBottom: space.lg }}>
        <IconTile icon={FileText} tone="accent" size={56} />
        <Txt variant="title" accessibilityRole="header">
          {t('verification.myDocs.title')}
        </Txt>
        <Txt color="muted">{t('verification.myDocs.subtitle', { days: warningWindow(config) })}</Txt>
      </View>

      {expired ? (
        <Notice
          tone={expired.renewalPending ? 'info' : 'danger'}
          title={expired.renewalPending ? t('verification.myDocs.expiredPendingTitle') : t('verification.myDocs.expiredTitle')}
          style={{ marginBottom: space.md }}>
          {expired.renewalPending ? t('verification.myDocs.expiredPendingBody') : t('verification.myDocs.expiredBody')}
        </Notice>
      ) : null}

      {profile.isPending ? (
        <View style={{ gap: space.sm }}>
          {[0, 1, 2].map((i) => (
            <Skeleton key={i} height={128} radius={radius.card} />
          ))}
        </View>
      ) : profile.isError ? (
        <ErrorState inline error={profile.error} onRetry={() => profile.refetch()} />
      ) : (
        <View style={{ gap: space.sm }}>
          {items.map((item) => (
            <DocumentCard
              key={item.kind}
              item={item}
              uploading={uploadingKind === item.kind}
              disabled={busy}
              onUpdate={() => start(item.kind)}
              onSetExpiry={() => {
                setDateError(undefined);
                setDating(item);
              }}
            />
          ))}
        </View>
      )}

      {cameraDenied ? <CameraDeniedNotice style={{ marginTop: space.md }} /> : null}
      <View style={{ marginTop: space.md }}>
        <ErrorText>{error}</ErrorText>
      </View>
      <Notice tone="info" style={{ marginTop: space.xs }}>
        {t('verification.myDocs.how')}
      </Notice>

      {elements}
      <ExpirySheet
        visible={!!dating}
        title={dating ? t(`driver.doc.${dating.kind}.title`) : ''}
        confirmLabel={t('verification.expiry.save')}
        loading={setExpiry.isPending}
        error={dateError}
        onSubmit={saveExpiry}
        onClose={() => setDating(null)}
      />
    </Screen>
  );
}

/** One document: its badge, what it means and the action it needs. */
function DocumentCard({
  item,
  uploading,
  disabled,
  onUpdate,
  onSetExpiry,
}: {
  item: MyDocumentItem;
  uploading: boolean;
  disabled: boolean;
  onUpdate: () => void;
  onSetExpiry: () => void;
}) {
  const { t, i18n } = useTranslation();
  const theme = useTheme();
  const badge = documentBadge(item);
  const title = t(`driver.doc.${item.kind}.title`);
  const badgeLabel = t(badge.key, { count: badge.count });
  const sentOn = (iso: string) => new Date(iso).toLocaleDateString(i18n.language, { day: 'numeric', month: 'long' });

  const lines: { text: string; tone?: 'danger' | 'muted' }[] = [];
  if (item.inUse?.expires_on) {
    const date = isoToDisplayDate(item.inUse.expires_on);
    lines.push({
      text: item.daysLeft !== null && item.daysLeft < 0 ? t('verification.expiredOn', { date }) : t('verification.expiresOn', { date }),
      tone: item.state === 'expired' ? 'danger' : 'muted',
    });
  }
  if (item.state === 'missing_expiry') lines.push({ text: t('verification.myDocs.missingExpiry') });
  if (item.state === 'in_review' && item.renewal) {
    lines.push({ text: t('verification.myDocs.inReview', { date: sentOn(item.renewal.created_at) }) });
  }
  if (item.state === 'rejected') {
    lines.push({
      text: item.renewal?.rejection_reason
        ? t('verification.myDocs.rejected', { reason: item.renewal.rejection_reason })
        : t('verification.myDocs.rejectedNoReason'),
      tone: 'danger',
    });
  }
  if (item.state === 'not_added') {
    lines.push({ text: item.optional ? t('verification.optional.hint') : t(`driver.doc.${item.kind}.hint`) });
  }
  if (item.state === 'valid' && !item.needsExpiry) lines.push({ text: t('verification.myDocs.noExpiry') });

  const iconTone = badge.tone === 'neutral' ? 'neutral' : badge.tone === 'success' ? 'primary' : badge.tone;
  const updateLabel = item.state === 'not_added' ? t('verification.optional.add') : t('verification.myDocs.update');

  return (
    <Card
      style={[
        styles.card,
        (item.state === 'expired' || item.state === 'rejected') && { borderColor: theme.danger },
      ]}
      accessibilityLabel={`${title}: ${badgeLabel}`}>
      <View style={styles.head}>
        <IconTile icon={DOCUMENT_ICONS[item.kind]} tone={iconTone} size={44} />
        <View style={{ flex: 1, gap: 2 }}>
          <Txt variant="bodyStrong" numberOfLines={2}>
            {title}
          </Txt>
          {lines.map((line) => (
            <Txt key={line.text} variant="caption" color={line.tone === 'danger' ? 'danger' : 'muted'}>
              {line.text}
            </Txt>
          ))}
        </View>
        <StatusPill label={badgeLabel} tone={badge.tone} dot={badge.tone !== 'neutral' && badge.tone !== 'success'} />
      </View>
      <View style={styles.actions}>
        {item.canSetExpiry ? (
          <Button
            title={t('verification.myDocs.setExpiry')}
            size="sm"
            icon={Calendar}
            style={styles.action}
            disabled={disabled}
            accessibilityLabel={`${t('verification.myDocs.setExpiry')}: ${title}`}
            onPress={onSetExpiry}
          />
        ) : null}
        <Button
          title={updateLabel}
          size="sm"
          variant={item.state === 'expired' || item.state === 'expiring' || item.state === 'rejected' ? 'primary' : 'secondary'}
          icon={item.state === 'not_added' ? Plus : RefreshCw}
          style={styles.action}
          loading={uploading}
          disabled={disabled}
          accessibilityLabel={`${updateLabel}: ${title}`}
          onPress={onUpdate}
        />
      </View>
    </Card>
  );
}

const styles = StyleSheet.create({
  card: { gap: space.md, padding: space.md },
  head: { flexDirection: 'row', alignItems: 'flex-start', gap: space.sm },
  actions: { flexDirection: 'row', justifyContent: 'flex-end', flexWrap: 'wrap', gap: space.xs },
  action: { marginTop: 0 },
});
