import { router, useLocalSearchParams } from 'expo-router';
import { useTranslation } from 'react-i18next';
import { ActivityIndicator, Pressable, View } from 'react-native';

import { Camera, Image, Plus, Trash, Upload } from '@/components/icons';
import { Button, Card, ErrorText, ListRow, Notice, StatusPill, Txt } from '@/components/ui';
import { DOCUMENT_ICONS, DOCUMENT_STATE_TONE } from '@/features/driver/meta';
import { goBack, StepScreen } from '@/features/driver/StepScreen';
import { CameraDeniedNotice, useDocumentUpload } from '@/features/driver/useDocumentUpload';
import { useAppConfig, useDeleteDocument, useDriverProfile } from '@/hooks/useDriver';
import { apiErrorMessage } from '@/i18n';
import {
  type DocumentChecklistItem,
  documentChecklist,
  isDocumentDone,
  isoToDisplayDate,
  MAX_VEHICLE_PHOTOS,
} from '@/lib/driver';
import { needsExpiry, optionalChecklist } from '@/lib/verification';
import { space, useTheme } from '@/theme';

export default function DocumentsStep() {
  const { t } = useTranslation();
  const theme = useTheme();
  const { from } = useLocalSearchParams<{ from?: string }>();
  const { data: profile } = useDriverProfile();
  const { config } = useAppConfig();
  const remove = useDeleteDocument();
  const { start, elements, error, setError, cameraDenied, busy, uploadingKind } = useDocumentUpload();

  const items = documentChecklist(profile, config);
  // Doc 12: optional documents (certificado de antecedentes) never block the submit.
  const optional = optionalChecklist(profile, config);
  const done = items.filter(isDocumentDone).length;
  const allDone = done === items.length;

  /** The hint, or "Vence el 12/05/2027" once an expiring document was sent with its date. */
  function subtitleFor(item: DocumentChecklistItem) {
    if (item.state === 'rejected') return item.rejectionReason ?? t('driver.documents.rejectedHint');
    const expiresOn = item.documents[0]?.expires_on;
    if (item.state !== 'missing' && expiresOn) return t('verification.expiresOn', { date: isoToDisplayDate(expiresOn) });
    if (item.state === 'missing' && needsExpiry(item.kind, config)) {
      return `${t(`driver.doc.${item.kind}.hint`)} · ${t('verification.asksExpiry')}`;
    }
    return t(`driver.doc.${item.kind}.hint`);
  }

  function actionFor(item: DocumentChecklistItem) {
    if (uploadingKind === item.kind) return <ActivityIndicator color={theme.primary} accessibilityLabel={t('driver.documents.uploading')} />;
    if (item.kind === 'vehicle_photo') return <StatusPill label={t(`driver.docState.${item.state}`)} tone={DOCUMENT_STATE_TONE[item.state]} />;
    if (item.state === 'missing') {
      return (
        <Button
          title={item.kind === 'selfie' ? t('driver.documents.take') : t('driver.documents.upload')}
          size="sm"
          icon={item.kind === 'selfie' ? Camera : Upload}
          style={{ marginTop: 0 }}
          disabled={busy}
          accessibilityLabel={`${t('driver.documents.upload')}: ${t(`driver.doc.${item.kind}.title`)}`}
          onPress={() => start(item.kind)}
        />
      );
    }
    return <StatusPill label={t(`driver.docState.${item.state}`)} tone={DOCUMENT_STATE_TONE[item.state]} />;
  }

  const photos = items.find((item) => item.kind === 'vehicle_photo');

  return (
    <StepScreen
      step="documents"
      title={t('driver.documents.title')}
      subtitle={t('driver.documents.subtitle')}
      footer={
        <>
          {!allDone ? (
            <Txt variant="caption" color="muted" align="center">
              {t('driver.documents.progress', { done, total: items.length })}
            </Txt>
          ) : null}
          <Button
            title={from === 'review' ? t('common.done') : t('common.continue')}
            disabled={!allDone || busy}
            onPress={() => (from === 'review' ? goBack() : router.push('/driver/review'))}
          />
        </>
      }>
      <Card style={{ paddingVertical: space.xxs }}>
        {items
          .filter((item) => item.kind !== 'vehicle_photo')
          .map((item, index, list) => {
            const replaceable = item.state !== 'missing' && !busy;
            return (
              <View key={item.kind}>
                <ListRow
                  icon={DOCUMENT_ICONS[item.kind]}
                  iconTone={item.state === 'rejected' ? 'danger' : item.state === 'missing' ? 'neutral' : 'primary'}
                  title={t(`driver.doc.${item.kind}.title`)}
                  subtitle={subtitleFor(item)}
                  right={actionFor(item)}
                  chevron={false}
                  onPress={replaceable ? () => start(item.kind) : undefined}
                  accessibilityHint={replaceable ? t('driver.documents.replaceHint') : undefined}
                  divider={index < list.length - 1}
                />
              </View>
            );
          })}
      </Card>

      {photos ? (
        <>
          <Txt variant="overline" color="muted" style={{ marginTop: space.xl, marginBottom: space.xs }}>
            {t('driver.doc.vehicle_photo.title')}
          </Txt>
          <Card style={{ gap: space.sm }}>
            <View style={{ flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', gap: space.sm }}>
              <View style={{ flex: 1 }}>
                <Txt variant="bodyStrong">{t('driver.documents.photosCount', { count: photos.uploaded, required: photos.required })}</Txt>
                <Txt variant="caption" color="muted">
                  {t('driver.doc.vehicle_photo.hint')}
                </Txt>
              </View>
              {actionFor(photos)}
            </View>
            {photos.documents.map((doc, index) => (
              <View key={doc.id} style={{ flexDirection: 'row', alignItems: 'center', gap: space.sm }}>
                <View style={{ flex: 1 }}>
                <ListRow
                  icon={Image}
                  iconTone={doc.status === 'rejected' ? 'danger' : 'primary'}
                  title={t('driver.documents.photoN', { n: photos.documents.length - index })}
                  subtitle={doc.status === 'rejected' ? doc.rejection_reason ?? t('driver.docState.rejected') : t(`driver.docState.${doc.status}`)}
                  chevron={false}
                />
                </View>
                <Pressable
                  accessibilityRole="button"
                  accessibilityLabel={t('driver.documents.deletePhoto', { n: photos.documents.length - index })}
                  hitSlop={8}
                  disabled={remove.isPending}
                  onPress={() => {
                    setError(undefined);
                    remove.mutate(doc.id, { onError: (e) => setError(apiErrorMessage(e)) });
                  }}
                  style={({ pressed }) => ({ padding: space.xs, opacity: pressed || remove.isPending ? 0.5 : 1 })}>
                  <Trash size={20} color={theme.danger} strokeWidth={2} />
                </Pressable>
              </View>
            ))}
            {photos.documents.length < MAX_VEHICLE_PHOTOS ? (
              <Button
                title={photos.documents.length ? t('driver.documents.addPhoto') : t('driver.documents.addFirstPhoto')}
                variant="secondary"
                icon={Plus}
                disabled={busy}
                loading={uploadingKind === 'vehicle_photo'}
                onPress={() => start('vehicle_photo')}
              />
            ) : null}
          </Card>
        </>
      ) : null}

      {optional.length ? (
        <>
          <View style={{ flexDirection: 'row', alignItems: 'center', gap: space.xs, marginTop: space.xl, marginBottom: space.xs }}>
            <Txt variant="overline" color="muted" style={{ flex: 1 }}>
              {t('verification.optional.title')}
            </Txt>
            <StatusPill label={t('verification.badge.optional')} tone="neutral" />
          </View>
          <Card style={{ paddingVertical: space.xxs }}>
            {optional.map((item, index) => {
              const replaceable = item.state !== 'missing' && !busy;
              return (
                <ListRow
                  key={item.kind}
                  icon={DOCUMENT_ICONS[item.kind]}
                  iconTone={item.state === 'rejected' ? 'danger' : item.state === 'missing' ? 'neutral' : 'primary'}
                  title={t(`driver.doc.${item.kind}.title`)}
                  subtitle={item.state === 'missing' ? t('verification.optional.hint') : subtitleFor(item)}
                  right={
                    item.state === 'missing' && uploadingKind !== item.kind ? (
                      <Button
                        title={t('verification.optional.add')}
                        size="sm"
                        variant="secondary"
                        icon={Plus}
                        style={{ marginTop: 0 }}
                        disabled={busy}
                        accessibilityLabel={`${t('verification.optional.add')}: ${t(`driver.doc.${item.kind}.title`)}`}
                        onPress={() => start(item.kind)}
                      />
                    ) : (
                      actionFor(item)
                    )
                  }
                  chevron={false}
                  onPress={replaceable ? () => start(item.kind) : undefined}
                  accessibilityHint={replaceable ? t('driver.documents.replaceHint') : undefined}
                  divider={index < optional.length - 1}
                />
              );
            })}
          </Card>
        </>
      ) : null}

      {cameraDenied ? <CameraDeniedNotice style={{ marginTop: space.md }} /> : null}
      <View style={{ marginTop: space.md }}>
        <ErrorText>{error}</ErrorText>
      </View>
      <Notice tone="info" style={{ marginTop: space.sm }}>
        {t('driver.documents.tips')}
      </Notice>

      {elements}
    </StepScreen>
  );
}
