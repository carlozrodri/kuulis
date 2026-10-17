/** Pages that act on a private link or token: never indexed, so they get no canonical or language alternates. */
export const PRIVATE_PAGES = new Set(['v-token', 'i-code', 'verify-email', 'reset-password'])

const OG_LOCALE: Record<string, string> = { es: 'es_VE', en: 'en_US' }

/**
 * Route name → its link-preview image in public/og/ (made by `pnpm og`, docs/website-redesign/05 A8) and the title
 * it shows, for the alt text. Every other page shares the home image.
 */
export const OG_PAGES: Record<string, { image: string, title: string }> = {
  index: { image: 'home', title: 'home.hero.title' },
  motorizados: { image: 'drivers', title: 'drivers.title' },
  seguridad: { image: 'safety', title: 'safety.title' },
  descargar: { image: 'download', title: 'download.title' },
}

/**
 * Canonical URL, hreflang alternates (es-VE, en, x-default → Spanish), og:locale and og:image for the current page,
 * absolute with NUXT_PUBLIC_SITE_URL (docs/website-redesign/06 §5). The query string is left out of all of them.
 */
export function useLocaleSeo() {
  const { locale, locales, t } = useI18n()
  const route = useRoute()
  const routeBaseName = useRouteBaseName()
  const switchLocalePath = useSwitchLocalePath()
  const site = useRuntimeConfig().public.siteUrl.replace(/\/$/, '')
  const absolute = (path: string) => `${site}${path.split('?')[0]!.split('#')[0]}`

  const indexable = computed(() => !PRIVATE_PAGES.has(String(routeBaseName(route) ?? '')))
  const og = computed(() => OG_PAGES[String(routeBaseName(route) ?? '')] ?? OG_PAGES.index!)

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
    // Link previews (WhatsApp, Telegram) need an absolute image URL.
    ogImage: () => `${site}/og/${og.value.image}-${locale.value}.png`,
    ogImageWidth: 1200,
    ogImageHeight: 630,
    ogImageType: 'image/png',
    ogImageAlt: () => t(og.value.title),
  })
}
