const PAGES = ['/', '/motorizados', '/descargar', '/ayuda', '/contacto', '/legal', '/legal/terms', '/legal/privacy', '/legal/community', '/legal/driver_terms', '/legal/wallet']

/** Published help articles (doc 13), so search engines find them; none when the API is down. */
async function helpPaths(apiBase: string): Promise<string[]> {
  try {
    const articles = await $fetch<{ slug: string }[]>('/help/articles', { baseURL: apiBase, query: { locale: 'es' }, timeout: 5000 })
    return [...new Set(articles.map(article => `/ayuda/${article.slug}`))]
  }
  catch {
    return []
  }
}

export default defineEventHandler(async (event) => {
  const config = useRuntimeConfig(event)
  const site = config.public.siteUrl.replace(/\/$/, '')
  const apiBase = config.apiInternal || `${getRequestURL(event).origin}${config.public.apiBase}`
  const paths = [...PAGES, ...(await helpPaths(apiBase))]
  setHeader(event, 'Content-Type', 'application/xml; charset=utf-8')
  const urls = paths.map(path => `  <url><loc>${site}${path}</loc></url>`).join('\n')
  return `<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n${urls}\n</urlset>\n`
})
