import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Image, KeyboardAvoidingView, Modal, Platform, Pressable, StyleSheet, View } from 'react-native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';

import { Calendar, FileText, X } from '@/components/icons';
import { Button, ErrorText, Field, IconButton, IconTile, Row, Txt } from '@/components/ui';
import { isoToDisplayDate, maskDateInput } from '@/lib/driver';
import type { LocalFile } from '@/lib/upload';
import { parseExpiryInput } from '@/lib/verification';
import { radius, space, useTheme } from '@/theme';

const isImage = (file: LocalFile) =>
  (file.mimeType ?? '').startsWith('image/') || /\.(jpe?g|png|webp|heic)$/i.test(file.name ?? file.uri);

/**
 * "¿Cuándo vence?" (doc 12): the expiry date of a license, medical certificate or registration, typed as
 * DD/MM/AAAA. Shows the picked file so the driver can read the date off it.
 */
export function ExpirySheet({
  visible,
  title,
  file,
  initialIso,
  confirmLabel,
  loading,
  error,
  onSubmit,
  onClose,
}: {
  visible: boolean;
  /** The document's name ("Licencia de conducir"). */
  title: string;
  file?: LocalFile | null;
  initialIso?: string | null;
  confirmLabel: string;
  loading?: boolean;
  /** An API error to show (e.g. document_already_expired). */
  error?: string;
  onSubmit: (iso: string) => void;
  onClose: () => void;
}) {
  const theme = useTheme();
  const insets = useSafeAreaInsets();
  const { t } = useTranslation();
  return (
    <Modal visible={visible} transparent animationType="slide" onRequestClose={loading ? undefined : onClose} statusBarTranslucent>
      <Pressable
        accessibilityRole="button"
        accessibilityLabel={t('common.close')}
        style={[StyleSheet.absoluteFill, { backgroundColor: theme.backdrop }]}
        onPress={loading ? undefined : onClose}
      />
      <KeyboardAvoidingView behavior={Platform.OS === 'ios' ? 'padding' : undefined} style={styles.anchor} pointerEvents="box-none">
        <View style={[styles.sheet, { backgroundColor: theme.surface, paddingBottom: Math.max(insets.bottom, space.md) + space.xs }]}>
          <View style={[styles.handle, { backgroundColor: theme.border }]} />
          <Row style={{ alignItems: 'flex-start' }}>
            <View style={{ flex: 1, gap: 4 }}>
              <Txt variant="overline" color="muted">
                {title}
              </Txt>
              <Txt variant="heading" accessibilityRole="header">
                {t('verification.expiry.title')}
              </Txt>
              <Txt color="muted">{t('verification.expiry.body')}</Txt>
            </View>
            <IconButton icon={X} label={t('common.close')} onPress={loading ? undefined : onClose} tone="plain" size={40} />
          </Row>

          {file ? (
            <View style={[styles.file, { backgroundColor: theme.surfaceAlt }]}>
              {isImage(file) ? (
                <Image source={{ uri: file.uri }} style={styles.thumb} accessibilityIgnoresInvertColors />
              ) : (
                <IconTile icon={FileText} size={56} />
              )}
              <View style={{ flex: 1 }}>
                <Txt variant="bodyStrong" numberOfLines={1}>
                  {isImage(file) ? t('verification.expiry.photoReady') : file.name || t('verification.expiry.pdfReady')}
                </Txt>
                <Txt variant="caption" color="muted">
                  {t('verification.expiry.fileHint')}
                </Txt>
              </View>
            </View>
          ) : null}

          {/* Mounted only while visible, so each opening starts from `initialIso`. */}
          <ExpiryForm initialIso={initialIso} autoFocus={!file} confirmLabel={confirmLabel} loading={loading} error={error} onSubmit={onSubmit} />
        </View>
      </KeyboardAvoidingView>
    </Modal>
  );
}

function ExpiryForm({
  initialIso,
  autoFocus,
  confirmLabel,
  loading,
  error,
  onSubmit,
}: {
  initialIso?: string | null;
  autoFocus: boolean;
  confirmLabel: string;
  loading?: boolean;
  error?: string;
  onSubmit: (iso: string) => void;
}) {
  const { t } = useTranslation();
  const [value, setValue] = useState(() => isoToDisplayDate(initialIso));
  const [fieldError, setFieldError] = useState<string>();

  const submit = () => {
    const parsed = parseExpiryInput(value);
    if (parsed.error) {
      setFieldError(t(parsed.error === 'past' ? 'verification.expiry.past' : 'verification.expiry.invalid'));
      return;
    }
    setFieldError(undefined);
    onSubmit(parsed.iso);
  };

  return (
    <>
      <View style={{ marginTop: space.md }}>
        <Field
          label={t('verification.expiry.label')}
          icon={Calendar}
          value={value}
          onChangeText={(text) => {
            setValue(maskDateInput(text));
            setFieldError(undefined);
          }}
          placeholder={t('verification.expiry.placeholder')}
          keyboardType="number-pad"
          maxLength={10}
          autoFocus={autoFocus}
          returnKeyType="done"
          onSubmitEditing={submit}
          error={fieldError}
        />
      </View>
      <ErrorText>{error}</ErrorText>
      <Button title={confirmLabel} loading={loading} onPress={submit} />
    </>
  );
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
  file: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: space.sm,
    borderRadius: radius.tile,
    padding: space.sm,
    marginTop: space.md,
  },
  thumb: { width: 56, height: 56, borderRadius: radius.field },
});
