/** Calls the Kuulis API: same origin in the browser, the internal address while server rendering. */
export function useApi() {
  const config = useRuntimeConfig()
  const base = import.meta.server
    ? (config.apiInternal || `${useRequestURL().origin}${config.public.apiBase}`)
    : config.public.apiBase
  return {
    request: <T>(path: string, options: Parameters<typeof $fetch>[1] = {}) =>
      $fetch<T>(path, { baseURL: base, timeout: 8000, ...options }) as Promise<T>,
  }
}

/** The error code the API answered ({"error": {"code": ...}}), if any. */
export function apiErrorCode(error: unknown): string | null {
  const data = (error as { data?: { error?: { code?: string } } })?.data
  return data?.error?.code ?? null
}
