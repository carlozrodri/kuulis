import * as Haptics from 'expo-haptics';
import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Linking } from 'react-native';
import type { StyleProp, ViewStyle } from 'react-native';

import { Camera, FileText, Image, RotateCcw, ScanFace } from '@/components/icons';
import { Button, Notice, Sheet, type SheetOption, Txt } from '@/components/ui';
import { useAppConfig, useUploadDocument } from '@/hooks/useDriver';
import { apiErrorMessage } from '@/i18n';
import { PHOTO_ONLY_KINDS } from '@/lib/driver';
import type { DocumentKind } from '@/lib/types';
import { type LocalFile, UploadError } from '@/lib/upload';
import { needsExpiry } from '@/lib/verification';

import { ExpirySheet } from './ExpirySheet';
import { PermissionDenied, pickFile, type PickSource } from './pickFile';

/** Message for an upload failure: the picker's own errors or the API's code. */
export function uploadErrorMessage(error: unknown, t: (key: string) => string): string {
  if (error instanceof UploadError) {
    return t(error.code === 'file_type_not_allowed' ? 'errors.file_type_not_allowed' : 'errors.upload_failed');
  }
  return apiErrorMessage(error);
}

/** "Sin acceso a la cámara" with a shortcut to the app settings. */
export function CameraDeniedNotice({ style, library = true }: { style?: StyleProp<ViewStyle>; library?: boolean }) {
  const { t } = useTranslation();
  return (
    <Notice tone="warning" title={t('driver.documents.cameraDeniedTitle')} style={style}>
      <Txt variant="caption" style={{ fontSize: 14, lineHeight: 20 }}>
        {library ? t('driver.documents.cameraDenied') : t('verification.selfie.cameraDenied')}
      </Txt>
      <Button
        title={t('common.openSettings')}
        variant="secondary"
        size="sm"
        icon={RotateCcw}
        style={{ alignSelf: 'flex-start' }}
        onPress={() => void Linking.openSettings()}
      />
    </Notice>
  );
}

/**
 * Picking and uploading one document: camera, gallery or PDF, then "¿Cuándo vence?" for expiring kinds
 * (doc 12) before sending. Used by the onboarding step and by "Mis documentos" (renewals).
 */
export function useDocumentUpload({ onUploaded }: { onUploaded?: (kind: DocumentKind) => void } = {}) {
  const { t } = useTranslation();
  const { config } = useAppConfig();
  const upload = useUploadDocument();
  const [sheetKind, setSheetKind] = useState<DocumentKind | null>(null);
  // A picked file waiting for its expiry date.
  const [dated, setDated] = useState<{ kind: DocumentKind; file: LocalFile } | null>(null);
  const [dateError, setDateError] = useState<string>();
  const [error, setError] = useState<string>();
  const [cameraDenied, setCameraDenied] = useState(false);

  async function send(kind: DocumentKind, file: LocalFile, expiresOn?: string) {
    setDateError(undefined);
    try {
      await upload.mutateAsync({ kind, file, expiresOn });
      void Haptics.notificationAsync(Haptics.NotificationFeedbackType.Success).catch(() => undefined);
      setDated(null);
      onUploaded?.(kind);
    } catch (e) {
      // With the date sheet open the error shows there (e.g. document_already_expired).
      if (expiresOn) setDateError(uploadErrorMessage(e, t));
      else setError(uploadErrorMessage(e, t));
    }
  }

  async function choose(kind: DocumentKind, source: PickSource) {
    setError(undefined);
    setCameraDenied(false);
    try {
      const file = await pickFile(source);
      if (!file) return;
      if (needsExpiry(kind, config)) {
        setDateError(undefined);
        setDated({ kind, file });
        return;
      }
      await send(kind, file);
    } catch (e) {
      if (e instanceof PermissionDenied) setCameraDenied(true);
      else setError(uploadErrorMessage(e, t));
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

  const start = (kind: DocumentKind) => {
    setError(undefined);
    setCameraDenied(false);
    setSheetKind(kind);
  };

  const elements = (
    <>
      <Sheet
        visible={!!sheetKind}
        title={sheetKind ? t(`driver.doc.${sheetKind}.title`) : ''}
        subtitle={sheetKind ? t(`driver.doc.${sheetKind}.hint`) : undefined}
        options={sheetKind ? sheetOptions(sheetKind) : []}
        onClose={() => setSheetKind(null)}
      />
      <ExpirySheet
        visible={!!dated}
        title={dated ? t(`driver.doc.${dated.kind}.title`) : ''}
        file={dated?.file}
        confirmLabel={t('verification.expiry.upload')}
        loading={upload.isPending}
        error={dateError}
        onSubmit={(iso) => dated && void send(dated.kind, dated.file, iso)}
        onClose={() => setDated(null)}
      />
    </>
  );

  return {
    start,
    elements,
    error,
    setError,
    cameraDenied,
    busy: upload.isPending,
    uploadingKind: upload.isPending ? upload.variables?.kind : undefined,
  };
}
