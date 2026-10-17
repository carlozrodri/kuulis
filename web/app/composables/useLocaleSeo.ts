/** Pages that act on a private link or token: never indexed, so they get no canonical or language alternates. */
export const PRIVATE_PAGES = new Set(['v-token', 'i-code', 'verify-email', 'reset-password'])

const OG_LOCALE: Record<string, string> = { es: 'es_VE', en: 'en_US' }

/**
 * Canonical URL, hreflang alternates (es-VE, en, x-default → Spanish) and og:locale for the current page, absolute
 * with NUXT_PUBLIC_SITE_URL (docs/website-redesign/06 §5). The query string is left out of all of them.
 */
export function useLocaleSeo() {
  const { locale, locales } = useI18n()
  const route = useRoute()
  const routeBaseName = useRouteBaseName()
  const switchLocalePath = useSwitchLocalePath()
  const site = useRuntimeConfig().public.siteUrl.replace(/\/$/, '')
  const absolute = (path: string) => `${site}${path.split('?')[0]!.split('#')[0]}`

  const indexable = computed(() => !PRIVATE_PAGES.has(String(routeBaseName(route) ?? '')))

  useHead(() => {
    if (!indexable.value) return {}
    const alternates = locales.value.map(({ code, language }) => ({
      rel: 'alternate' as const, hreflang: language ?? code, href: absolute(switchLocalePath(code)),
    }))
    return {
      link: [
        { rel: 'canonical', href: absolute(switchLocalePath(locale.value)) },
        ...alternates,
        { rel: 'alternate' as const, hreflang: 'x-default', href: absolute(switchLocalePath('es')) },
      ],
    }
  })
  useSeoMeta({
    ogLocale: () => OG_LOCALE[locale.value],
    ogLocaleAlternate: () => Object.entries(OG_LOCALE).filter(([code]) => code !== locale.value).map(([, value]) => value),
    ogUrl: () => (indexable.value ? absolute(switchLocalePath(locale.value)) : undefined),
  })
}
