import type { PresignedUpload } from '~/types/api'

/**
 * Uploads a file the way the apps do (doc 13 attachments): ask the API for a presigned link in the
 * "uploads" folder, PUT the bytes straight to storage, and hand back the key to send with the message.
 */
export function useUpload() {
  const { request } = useApi()

  async function upload(file: File): Promise<string> {
    const presigned = await request<PresignedUpload>('/files/presign-upload', {
      method: 'POST',
      body: { filename: file.name || 'foto.jpg', content_type: file.type, size: file.size, folder: 'uploads' },
    })
    await $fetch(presigned.upload_url, { method: presigned.method ?? 'PUT', body: file, headers: presigned.headers })
    return presigned.key
  }

  return { upload }
}
