import * as ImagePicker from 'expo-image-picker';
import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Linking, Platform } from 'react-native';

import { Camera, Images, Trash } from '@/components/icons';
import { showToast } from '@/components/Toast';
import { Sheet } from '@/components/ui';
import { apiErrorMessage } from '@/i18n';
import { api } from '@/lib/api';
import { UploadError, uploadAvatar } from '@/lib/upload';
import { useAuth } from '@/providers/AuthProvider';

const PICKER_OPTIONS: ImagePicker.ImagePickerOptions = {
  mediaTypes: ['images'],
  // Square crop; re-encoded to a small JPEG (also converts HEIC).
  allowsEditing: true,
  aspect: [1, 1],
  quality: 0.6,
  exif: false,
};

/**
 * Profile photo: a sheet with camera / gallery / remove, the upload (presign → PUT → PATCH /users/me) and a
 * busy flag for the avatar. Render `sheet` once and call `open()` from the avatar.
 */
export function useAvatarPicker() {
  const { t } = useTranslation();
  const { user, refreshUser } = useAuth();
  const [visible, setVisible] = useState(false);
  const [busy, setBusy] = useState(false);

  async function choose(source: 'camera' | 'library') {
    try {
      if (source === 'camera') {
        const permission = await ImagePicker.requestCameraPermissionsAsync();
        if (!permission.granted) {
          showToast(t('profile.photo.cameraDenied'), 'danger');
          if (!permission.canAskAgain) void Linking.openSettings().catch(() => undefined);
          return;
        }
      }
      const result =
        source === 'camera'
          ? await ImagePicker.launchCameraAsync({ ...PICKER_OPTIONS, cameraType: ImagePicker.CameraType.front })
          : await ImagePicker.launchImageLibraryAsync(PICKER_OPTIONS);
      const asset = result.canceled ? null : result.assets?.[0];
      if (!asset) return;
      setBusy(true);
      const key = await uploadAvatar({
        uri: asset.uri,
        name: asset.fileName ?? 'avatar.jpg',
        mimeType: asset.mimeType ?? 'image/jpeg',
      });
      await api('/users/me', { method: 'PATCH', body: { avatar_key: key } });
      await refreshUser();
      showToast(t('profile.photo.saved'), 'success');
    } catch (error) {
      showToast(error instanceof UploadError ? t(`errors.${error.code}`) : apiErrorMessage(error), 'danger');
    } finally {
      setBusy(false);
    }
  }

  async function remove() {
    setBusy(true);
    try {
      await api('/users/me', { method: 'PATCH', body: { avatar_key: null } });
      await refreshUser();
    } catch (error) {
      showToast(apiErrorMessage(error), 'danger');
    } finally {
      setBusy(false);
    }
  }

  const sheet = (
    <Sheet
      visible={visible}
      title={t('profile.photo.title')}
      subtitle={t('profile.photo.subtitle')}
      onClose={() => setVisible(false)}
      options={[
        // The browser has no camera capture in the picker; the gallery covers it there.
        ...(Platform.OS === 'web' ? [] : [{ label: t('profile.photo.camera'), icon: Camera, onPress: () => void choose('camera') }]),
        { label: t('profile.photo.library'), icon: Images, onPress: () => void choose('library') },
        ...(user?.avatar_key
          ? [{ label: t('profile.photo.remove'), icon: Trash, destructive: true, onPress: () => void remove() }]
          : []),
      ]}
    />
  );

  return { open: () => setVisible(true), busy, sheet };
}
