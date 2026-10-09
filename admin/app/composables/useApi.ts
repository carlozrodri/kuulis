import type { FetchOptions } from 'ofetch'
import type { ApiErrorBody } from '~/types/api'

/** $fetch wrapper: base URL, bearer token, one transparent retry after refreshing on 401. */
export function useApi() {
  const config = useRuntimeConfig()
  const auth = useAuth()
  // $i18n (not useI18n) so this also works in route middleware, outside component setup.
  const { $i18n } = useNuxtApp()

  async function request<T>(path: string, options: FetchOptions<'json'> | FetchOptions<'blob'> = {}): Promise<T> {
    const call = () =>
      $fetch<T>(path, {
        baseURL: config.public.apiBase,
        ...options,
        headers: {
          'Accept-Language': $i18n.locale.value,
          ...(auth.accessToken.value ? { Authorization: `Bearer ${auth.accessToken.value}` } : {}),
          ...(options.headers as Record<string, string> | undefined),
        },
      } as never) as Promise<T>

    try {
      return await call()
    }
    catch (error: unknown) {
      const status = (error as { status?: number }).status
      if (status === 401 && (await auth.refresh())) {
        return await call()
      }
      if (status === 401) {
        auth.clearSession()
        await navigateTo('/login')
      }
      throw error
    }
  }

  /**
   * Downloads a file that needs the auth header (CSV exports): fetches it as a blob and triggers a save.
   * The API sends a UTF-8 BOM so Excel opens it correctly; the blob keeps the bytes as they came.
   */
  async function download(path: string, filename: string, query: Record<string, string | undefined> = {}) {
    let blob: Blob
    try {
      blob = await request<Blob>(path, { query, responseType: 'blob' })
    }
    catch (error: unknown) {
      // Error bodies arrive as a Blob too: parse the JSON envelope so useApiError() can translate it.
      const err = error as { data?: unknown }
      if (err.data instanceof Blob) {
        try {
          err.data = JSON.parse(await err.data.text())
        }
        catch {
          err.data = undefined
        }
      }
      throw error
    }
    const url = URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.href = url
    link.download = filename
    document.body.appendChild(link)
    link.click()
    link.remove()
    setTimeout(() => URL.revokeObjectURL(url), 1000)
  }

  return { request, download }
}

/** Translates the API error envelope ({error: {code, message}}) into a user-facing message. */
export function useApiError() {
  const { t, te } = useI18n()
  return (error: unknown): string => {
    const body = (error as { data?: ApiErrorBody }).data
    const code = body?.error?.code
    if (code && te(`errors.${code}`)) return t(`errors.${code}`)
    return body?.error?.message ?? t('errors.generic')
  }
}
