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

  const blob = await (await fetch(file.uri)).blob();
  const presign = await api<PresignResponse>('/drivers/me/documents/presign', {
    method: 'POST',
    body: { kind, filename, content_type: contentType, size: blob.size },
  });

  const response = await fetch(presign.upload_url, {
    method: presign.method ?? 'PUT',
    headers: { 'Content-Type': contentType, ...presign.headers },
    body: blob,
  });
  if (!response.ok) throw new UploadError('upload_failed');

  return api<DriverProfile>('/drivers/me/documents', { method: 'POST', body: { kind, key: presign.key } });
}
