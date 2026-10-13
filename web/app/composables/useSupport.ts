import type { PublicConfig } from '~/utils/types'

/** Support contact details from GET /config/public: WhatsApp, email and the response promise. */
export async function useSupport() {
  const { locale } = useI18n()
  const runtime = useRuntimeConfig()
  const { request } = useApi()
  const { data } = await useAsyncData('public-config', () => request<PublicConfig>('/config/public').catch(() => null))

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
