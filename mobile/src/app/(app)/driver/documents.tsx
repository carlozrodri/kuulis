import * as Haptics from 'expo-haptics';
import { router, useLocalSearchParams } from 'expo-router';
import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { ActivityIndicator, Linking, Pressable, View } from 'react-native';

import { Camera, FileText, Image, Plus, RotateCcw, ScanFace, Trash, Upload } from '@/components/icons';
import {
  Button,
  Card,
  ErrorText,
  ListRow,
  Notice,
  Sheet,
  type SheetOption,
  StatusPill,
  Txt,
} from '@/components/ui';
import { DOCUMENT_ICONS, DOCUMENT_STATE_TONE } from '@/features/driver/meta';
import { PermissionDenied, pickFile, type PickSource } from '@/features/driver/pickFile';
import { goBack, StepScreen } from '@/features/driver/StepScreen';
import { useAppConfig, useDeleteDocument, useDriverProfile, useUploadDocument } from '@/hooks/useDriver';
import { apiErrorMessage } from '@/i18n';
import {
  type DocumentChecklistItem,
  documentChecklist,
  isDocumentDone,
  MAX_VEHICLE_PHOTOS,
  PHOTO_ONLY_KINDS,
} from '@/lib/driver';
import type { DocumentKind } from '@/lib/types';
import { UploadError } from '@/lib/upload';
import { space, useTheme } from '@/theme';

export default function DocumentsStep() {
  const { t } = useTranslation();
  const theme = useTheme();
  const { from } = useLocalSearchParams<{ from?: string }>();
  const { data: profile } = useDriverProfile();
  const { config } = useAppConfig();
  const upload = useUploadDocument();
  const remove = useDeleteDocument();
  const [sheetKind, setSheetKind] = useState<DocumentKind | null>(null);
  const [error, setError] = useState<string>();
  const [cameraDenied, setCameraDenied] = useState(false);

  const items = documentChecklist(profile, config);
  const done = items.filter(isDocumentDone).length;
  const allDone = done === items.length;
  const uploadingKind = upload.isPending ? upload.variables?.kind : undefined;

  async function choose(kind: DocumentKind, source: PickSource) {
    setError(undefined);
    setCameraDenied(false);
    try {
      const file = await pickFile(source);
      if (!file) return;
      await upload.mutateAsync({ kind, file });
      void Haptics.notificationAsync(Haptics.NotificationFeedbackType.Success).catch(() => undefined);
    } catch (e) {
      if (e instanceof PermissionDenied) {
        setCameraDenied(true);
      } else if (e instanceof UploadError) {
        setError(t(e.code === 'file_type_not_allowed' ? 'errors.file_type_not_allowed' : 'errors.upload_failed'));
      } else {
        setError(apiErrorMessage(e));
      }
    }
  }

  function sheetOptions(kind: DocumentKind): SheetOption[] {
    const options: SheetOption[] = [];
    if (kind === 'selfie') {
      options.push({ label: t('driver.documents.takeSelfie'), icon: ScanFace, onPress: () => choose(kind, 'selfie') });
    } else {
      options.push({ label: t('driver.documents.takePhoto'), icon: Camera, onPress: () => choose(kind, 'camera') });
    }
    options.push({ label: t('driver.documents.fromLibrary'), icon: Image, onPress: () => choose(kind, 'library') });
    if (!PHOTO_ONLY_KINDS.includes(kind)) {
      options.push({
        label: t('driver.documents.fromFiles'),
        hint: t('driver.documents.fromFilesHint'),
        icon: FileText,
        onPress: () => choose(kind, 'pdf'),
      });
    }
    return options;
  }

  function actionFor(item: DocumentChecklistItem) {
    const busy = uploadingKind === item.kind;
    if (busy) return <ActivityIndicator color={theme.primary} accessibilityLabel={t('driver.documents.uploading')} />;
    if (item.kind === 'vehicle_photo') return <StatusPill label={t(`driver.docState.${item.state}`)} tone={DOCUMENT_STATE_TONE[item.state]} />;
    if (item.state === 'missing') {
      return (
        <Button
          title={item.kind === 'selfie' ? t('driver.documents.take') : t('driver.documents.upload')}
          size="sm"
          icon={item.kind === 'selfie' ? Camera : Upload}
          style={{ marginTop: 0 }}
          disabled={upload.isPending}
          accessibilityLabel={`${t('driver.documents.upload')}: ${t(`driver.doc.${item.kind}.title`)}`}
          onPress={() => setSheetKind(item.kind)}
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
            disabled={!allDone || upload.isPending}
            onPress={() => (from === 'review' ? goBack() : router.push('/driver/review'))}
          />
        </>
      }>
      <Card style={{ paddingVertical: space.xxs }}>
        {items
          .filter((item) => item.kind !== 'vehicle_photo')
          .map((item, index, list) => {
            const replaceable = item.state !== 'missing' && uploadingKind !== item.kind && !upload.isPending;
            return (
              <View key={item.kind}>
                <ListRow
                  icon={DOCUMENT_ICONS[item.kind]}
                  iconTone={item.state === 'rejected' ? 'danger' : item.state === 'missing' ? 'neutral' : 'primary'}
                  title={t(`driver.doc.${item.kind}.title`)}
                  subtitle={item.state === 'rejected' ? item.rejectionReason ?? t('driver.documents.rejectedHint') : t(`driver.doc.${item.kind}.hint`)}
                  right={actionFor(item)}
                  chevron={false}
                  onPress={replaceable ? () => setSheetKind(item.kind) : undefined}
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
                disabled={upload.isPending}
                loading={uploadingKind === 'vehicle_photo'}
                onPress={() => setSheetKind('vehicle_photo')}
              />
            ) : null}
          </Card>
        </>
      ) : null}

      {cameraDenied ? (
        <Notice tone="warning" title={t('driver.documents.cameraDeniedTitle')} style={{ marginTop: space.md }}>
          <Txt variant="caption" style={{ fontSize: 14, lineHeight: 20 }}>
            {t('driver.documents.cameraDenied')}
          </Txt>
          <Button title={t('common.openSettings')} variant="secondary" size="sm" icon={RotateCcw} style={{ alignSelf: 'flex-start' }} onPress={() => void Linking.openSettings()} />
        </Notice>
      ) : null}
      <View style={{ marginTop: space.md }}>
        <ErrorText>{error}</ErrorText>
      </View>
      <Notice tone="info" style={{ marginTop: space.sm }}>
        {t('driver.documents.tips')}
      </Notice>

      <Sheet
        visible={!!sheetKind}
        title={sheetKind ? t(`driver.doc.${sheetKind}.title`) : ''}
        subtitle={sheetKind ? t(`driver.doc.${sheetKind}.hint`) : undefined}
        options={sheetKind ? sheetOptions(sheetKind) : []}
        onClose={() => setSheetKind(null)}
      />
    </StepScreen>
  );
}
