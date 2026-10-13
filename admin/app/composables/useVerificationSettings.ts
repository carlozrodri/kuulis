import type { AppConfig, VerificationSettings } from '~/types/api'

/** Doc 12 settings from the public config (verifiers may lack config.view); API defaults as fallback. */
export function useVerificationSettings() {
  const { request } = useApi()
  const { data } = useAsyncData('verification-settings', () =>
    request<AppConfig>('/config/public').catch(() => null),
  )
  return computed<VerificationSettings>(() => ({ ...DEFAULT_VERIFICATION, ...data.value?.verification }))
}
