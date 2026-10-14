import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Image, Linking, Pressable, ScrollView, StyleSheet, View } from 'react-native';

import { Camera, Images, X } from '@/components/icons';
import { showToast } from '@/components/Toast';
import { Sheet } from '@/components/ui';
import { PermissionDenied, pickFile } from '@/features/driver/pickFile';
import { apiErrorMessage } from '@/i18n';
import { MAX_ATTACHMENTS } from '@/lib/support';
import { type LocalFile, UploadError, uploadSupportPhoto } from '@/lib/upload';
import { radius, space, useTheme } from '@/theme';

/** Message for a failed upload (bad type, network) or API error. */
export const uploadErrorMessage = (error: unknown, t: (key: string) => string) =>
  error instanceof UploadError ? t(`errors.${error.code}`) : apiErrorMessage(error);

/**
 * Up to 4 photos for a support message (doc 13): a camera / gallery sheet, the thumbnails with a remove
 * button, and `upload()` that sends them (presign in "uploads" → PUT) and returns their keys. `max` lowers the
 * limit (a top-up claim takes 3).
 */
export function usePhotoAttachments(max: number = MAX_ATTACHMENTS) {
  const { t } = useTranslation();
  const [photos, setPhotos] = useState<LocalFile[]>([]);
  const [visible, setVisible] = useState(false);
  const full = photos.length >= max;

  const choose = async (source: 'camera' | 'library') => {
    try {
      const file = await pickFile(source);
      if (file) setPhotos((current) => (current.length >= max ? current : [...current, file]));
    } catch (error) {
      if (error instanceof PermissionDenied) {
        showToast(t('support.photos.cameraDenied'), 'danger');
        void Linking.openSettings().catch(() => undefined);
      } else showToast(apiErrorMessage(error), 'danger');
    }
  };

  const open = () => {
    if (full) showToast(t('support.photos.max', { max }));
    else setVisible(true);
  };

  const remove = (index: number) => setPhotos((current) => current.filter((_, i) => i !== index));
  const clear = () => setPhotos([]);
  const upload = async () => Promise.all(photos.map((photo) => uploadSupportPhoto(photo)));

  const sheet = (
    <Sheet
      visible={visible}
      title={t('support.photos.title')}
      subtitle={t('support.photos.subtitle', { max })}
      onClose={() => setVisible(false)}
      options={[
        { label: t('support.photos.camera'), icon: Camera, onPress: () => void choose('camera') },
        { label: t('support.photos.library'), icon: Images, onPress: () => void choose('library') },
      ]}
    />
  );

  return { photos, full, open, remove, clear, upload, sheet };
}

/** The chosen photos as small thumbnails, each with a remove button. */
export function PhotoStrip({ photos, onRemove, disabled }: { photos: LocalFile[]; onRemove: (index: number) => void; disabled?: boolean }) {
  const { t } = useTranslation();
  const theme = useTheme();
  if (!photos.length) return null;
  return (
    <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={styles.strip} keyboardShouldPersistTaps="handled">
      {photos.map((photo, index) => (
        <View key={`${photo.uri}-${index}`}>
          <Image source={{ uri: photo.uri }} style={[styles.thumb, { backgroundColor: theme.surfaceAlt }]} accessibilityIgnoresInvertColors />
          {!disabled ? (
            <Pressable
              accessibilityRole="button"
              accessibilityLabel={t('support.photos.remove', { n: index + 1 })}
              hitSlop={8}
              onPress={() => onRemove(index)}
              style={[styles.remove, { backgroundColor: theme.text }]}>
              <X size={14} color={theme.background} strokeWidth={3} />
            </Pressable>
          ) : null}
        </View>
      ))}
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  strip: { gap: space.xs, paddingVertical: space.xxs, paddingRight: space.xs },
  thumb: { width: 64, height: 64, borderRadius: radius.field },
  remove: {
    position: 'absolute',
    top: -6,
    right: -6,
    width: 24,
    height: 24,
    borderRadius: 12,
    alignItems: 'center',
    justifyContent: 'center',
  },
});
