import * as FileSystem from 'expo-file-system/legacy';
import { Platform } from 'react-native';

import { api } from './api';
import { contentTypeFor } from './driver';
import type { DocumentKind, DriverProfile, PresignResponse } from './types';

export interface LocalFile {
  uri: string;
  name?: string | null;
  mimeType?: string | null;
}

export class UploadError extends Error {
  constructor(public code: 'file_type_not_allowed' | 'upload_failed') {
    super(code);
  }
}

/**
 * Uploads one driver document: presign → PUT the bytes to storage with the returned headers → register.
 * Returns the updated DriverProfile.
 */
export async function uploadDriverDocument(kind: DocumentKind, file: LocalFile): Promise<DriverProfile> {
  const filename = file.name || file.uri.split('/').pop() || `${kind}.jpg`;
  const contentType = contentTypeFor(filename, file.mimeType);
  if (!contentType) throw new UploadError('file_type_not_allowed');

  const size = await fileSize(file.uri);
  const presign = await api<PresignResponse>('/drivers/me/documents/presign', {
    method: 'POST',
    body: { kind, filename, content_type: contentType, size },
  });

  const headers = { 'Content-Type': contentType, ...presign.headers };
  const status = await putFile(presign.upload_url, presign.method ?? 'PUT', file.uri, headers);
  if (status < 200 || status >= 300) throw new UploadError('upload_failed');

  return api<DriverProfile>('/drivers/me/documents', { method: 'POST', body: { kind, key: presign.key } });
}

/** Profile photo: presign in the avatars folder → PUT → returns the key to save with PATCH /users/me. */
export async function uploadAvatar(file: LocalFile): Promise<string> {
  const filename = file.name || file.uri.split('/').pop() || 'avatar.jpg';
  const contentType = contentTypeFor(filename, file.mimeType);
  if (!contentType || contentType === 'application/pdf') throw new UploadError('file_type_not_allowed');

  const size = await fileSize(file.uri);
  const presign = await api<PresignResponse>('/files/presign-upload', {
    method: 'POST',
    body: { filename, content_type: contentType, size, folder: 'avatars' },
  });
  const headers = { 'Content-Type': contentType, ...presign.headers };
  const status = await putFile(presign.upload_url, presign.method ?? 'PUT', file.uri, headers);
  if (status < 200 || status >= 300) throw new UploadError('upload_failed');
  return presign.key;
}

async function fileSize(uri: string): Promise<number> {
  if (Platform.OS === 'web') return (await (await fetch(uri)).blob()).size;
  const info = await FileSystem.getInfoAsync(uri);
  if (!info.exists) throw new UploadError('upload_failed');
  return info.size;
}

/**
 * Sends the file bytes as the request body. On the phone this goes through the native uploader:
 * React Native's fetch cannot reliably send a Blob read from a local file (Android fails with
 * "Network request failed"), which showed up as a connection error on every photo.
 */
async function putFile(url: string, method: string, uri: string, headers: Record<string, string>): Promise<number> {
  if (Platform.OS === 'web') {
    const blob = await (await fetch(uri)).blob();
    return (await fetch(url, { method, headers, body: blob })).status;
  }
  const result = await FileSystem.uploadAsync(url, uri, {
    httpMethod: method === 'POST' ? 'POST' : 'PUT',
    uploadType: FileSystem.FileSystemUploadType.BINARY_CONTENT,
    headers,
  });
  return result.status;
}
