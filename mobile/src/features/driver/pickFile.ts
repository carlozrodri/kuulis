import * as DocumentPicker from 'expo-document-picker';
import * as ImagePicker from 'expo-image-picker';

import type { LocalFile } from '@/lib/upload';

export type PickSource = 'camera' | 'selfie' | 'library' | 'pdf';

export class PermissionDenied extends Error {
  constructor(public permission: 'camera') {
    super(`${permission}_denied`);
  }
}

const IMAGE_OPTIONS: ImagePicker.ImagePickerOptions = {
  mediaTypes: ['images'],
  // Re-encodes to JPEG (also converts HEIC) and keeps uploads small on mobile data.
  quality: 0.7,
  exif: false,
};

/** Opens the camera, the photo library or the document picker. Returns null if the user cancels. */
export async function pickFile(source: PickSource): Promise<LocalFile | null> {
  if (source === 'pdf') {
    const result = await DocumentPicker.getDocumentAsync({ type: ['application/pdf', 'image/*'], copyToCacheDirectory: true });
    if (result.canceled || !result.assets?.[0]) return null;
    const asset = result.assets[0];
    return { uri: asset.uri, name: asset.name, mimeType: asset.mimeType };
  }

  let result: ImagePicker.ImagePickerResult;
  if (source === 'library') {
    // The system photo picker needs no library permission on iOS 14+ / Android 13+.
    result = await ImagePicker.launchImageLibraryAsync(IMAGE_OPTIONS);
  } else {
    const permission = await ImagePicker.requestCameraPermissionsAsync();
    if (!permission.granted) throw new PermissionDenied('camera');
    result = await ImagePicker.launchCameraAsync({
      ...IMAGE_OPTIONS,
      cameraType: source === 'selfie' ? ImagePicker.CameraType.front : ImagePicker.CameraType.back,
    });
  }
  if (result.canceled || !result.assets?.[0]) return null;
  const asset = result.assets[0];
  return { uri: asset.uri, name: asset.fileName ?? 'photo.jpg', mimeType: asset.mimeType ?? 'image/jpeg' };
}
