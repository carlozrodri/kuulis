import type { PublicConfig } from '~/utils/types'

/** GET /config/public, fetched once per page and shared; null when the API is unreachable. */
function usePublicConfig() {
  const { request } = useApi()
  return useAsyncData('public-config', () => request<PublicConfig>('/config/public').catch(() => null))
}

/** Support contact details from GET /config/public: WhatsApp, email and the response promise. */
export async function useSupport() {
  const { locale } = useI18n()
  const runtime = useRuntimeConfig()
  const { data } = await usePublicConfig()

  const whatsapp = computed(() => {
    const digits = (data.value?.app_links?.support_whatsapp ?? '').replace(/\D/g, '')
    return digits ? `https://wa.me/${digits}` : null
  })
  const email = computed(() => data.value?.app_links?.support_email || runtime.public.supportEmail || null)
  const promise = computed(() => {
    const support = data.value?.support
    return (locale.value === 'en' ? support?.response_promise_en : support?.response_promise_es) || null
  })
  return { whatsapp, email, promise }
}

/** Trip safety settings the home page quotes: the cities with a start PIN and the emergency number (911 by default, as in the app). */
export async function useSafetySettings() {
  const { data } = await usePublicConfig()
  const pinAreas = computed(() => data.value?.safety?.pin_areas ?? [])
  const emergency = computed(() => data.value?.app_links?.emergency_number || '911')
  return { pinAreas, emergency }
}
