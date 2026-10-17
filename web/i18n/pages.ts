/**
 * English paths of the pages whose Spanish path differs (docs/website-redesign/06 §4). Read by the i18n module
 * (nuxt.config.ts) for routing and by server/routes/sitemap.xml.ts, so both always agree. Pages not listed keep
 * their path under /en (/en/legal, /en/legal/terms).
 */
export const LOCALIZED_PAGES = {
  'motorizados': { es: '/motorizados', en: '/drivers' },
  'seguridad': { es: '/seguridad', en: '/safety' },
  'descargar': { es: '/descargar', en: '/download' },
  'ayuda': { es: '/ayuda', en: '/help' },
  'ayuda-slug': { es: '/ayuda/[slug]', en: '/help/[slug]' },
  'contacto': { es: '/contacto', en: '/contact' },
} as const

/** The /en path of a Spanish path: /motorizados → /en/drivers, /ayuda/x → /en/help/x, /legal → /en/legal. */
export function englishPath(path: string): string {
  if (path === '/') return '/en'
  for (const { es, en } of Object.values(LOCALIZED_PAGES)) {
    const pattern = new RegExp(`^${es.replace(/\[\w+\]/g, '([^/]+)')}$`)
    const match = path.match(pattern)
    if (match) return `/en${en.replace(/\[\w+\]/, match[1] ?? '')}`
  }
  return `/en${path}`
}
