import { englishPath } from '../../i18n/pages'

// Every public page in both languages, each <url> listing its alternates (docs/website-redesign/06 §5).
const PAGES = ['/', '/motorizados', '/seguridad', '/descargar', '/ayuda', '/contacto', '/eliminar-cuenta', '/legal', '/legal/terms', '/legal/privacy', '/legal/community', '/legal/driver_terms', '/legal/wallet']
  .map(path => ({ es: path, en: englishPath(path) }))

/** Published help articles (doc 13) in each language, so search engines find them; none when the API is down. */
async function helpPages(apiBase: string): Promise<{ es?: string, en?: string }[]> {
  const slugs = async (locale: string) => {
    try {
      const articles = await $fetch<{ slug: string }[]>('/help/articles', { baseURL: apiBase, query: { locale }, timeout: 5000 })
      return new Set(articles.map(article => article.slug))
    }
    catch {
      return new Set<string>()
    }
  }
  const [es, en] = await Promise.all([slugs('es'), slugs('en')])
  return [...new Set([...es, ...en])].map(slug => ({
    es: es.has(slug) ? `/ayuda/${slug}` : undefined,
    en: en.has(slug) ? englishPath(`/ayuda/${slug}`) : undefined,
  }))
}

export default defineEventHandler(async (event) => {
  const config = useRuntimeConfig(event)
  const site = config.public.siteUrl.replace(/\/$/, '')
  const apiBase = config.apiInternal || absoluteApiBase(config.public.apiBase, getRequestURL(event).origin)
  const pages = [...PAGES, ...(await helpPages(apiBase))]
  const urls = pages.flatMap((page) => {
    const links = [
      page.es && `<xhtml:link rel="alternate" hreflang="es-VE" href="${site}${page.es}"/>`,
      page.en && `<xhtml:link rel="alternate" hreflang="en" href="${site}${page.en}"/>`,
      page.es && `<xhtml:link rel="alternate" hreflang="x-default" href="${site}${page.es}"/>`,
    ].filter(Boolean).join('')
    return [page.es, page.en].filter(Boolean).map(path => `  <url><loc>${site}${path}</loc>${links}</url>`)
  })
  setHeader(event, 'Content-Type', 'application/xml; charset=utf-8')
  return `<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9" xmlns:xhtml="http://www.w3.org/1999/xhtml">\n${urls.join('\n')}\n</urlset>\n`
})
