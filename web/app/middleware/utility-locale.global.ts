import { PRIVATE_PAGES } from '~/composables/useLocaleSeo'

/**
 * Emails and the app link to the private pages without a language prefix (/verify-email?token=…, /v/…, /i/…).
 * Someone who reads the site in English (kuulis_locale cookie or, without one, a browser whose first language is English)
 * is sent to the /en variant, token and query intact, as the site did before English URLs existed.
 */
export default defineNuxtRouteMiddleware((to) => {
  // Only the first, server-rendered request comes from outside; links inside the site already carry the language.
  if (import.meta.client) return
  // Spanish variants only (the route's own language: the i18n locale has not switched yet during the redirect).
  if (to.path.startsWith('/en/') || !PRIVATE_PAGES.has(String(useRouteBaseName()(to) ?? ''))) return
  // The cookie as the visitor sent it: the i18n module has already set it to this page's language for the reply.
  const headers = useRequestHeaders(['cookie', 'accept-language'])
  const cookie = headers.cookie?.match(/(?:^|;\s*)kuulis_locale=(\w+)/)?.[1]
  const firstLanguage = headers['accept-language']?.split(',')[0]?.trim().toLowerCase() ?? ''
  const wantsEnglish = cookie ? cookie === 'en' : firstLanguage.startsWith('en')
  if (wantsEnglish) return navigateTo(useLocalePath()(to.fullPath, 'en'), { redirectCode: 302 })
})
