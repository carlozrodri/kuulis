import type { FetchOptions } from 'ofetch'
import type { ApiErrorBody } from '~/types/api'

/** $fetch wrapper: base URL, bearer token, one transparent retry after refreshing on 401. */
export function useApi() {
  const config = useRuntimeConfig()
  const auth = useAuth()
  // $i18n (not useI18n) so this also works in route middleware, outside component setup.
  const { $i18n } = useNuxtApp()

  async function request<T>(path: string, options: FetchOptions<'json'> = {}): Promise<T> {
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

  return { request }
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
