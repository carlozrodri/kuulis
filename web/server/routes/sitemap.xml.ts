const PAGES = ['/', '/motorizados', '/descargar', '/legal', '/legal/terms', '/legal/privacy', '/legal/community', '/legal/driver_terms', '/legal/wallet']

export default defineEventHandler((event) => {
  const site = useRuntimeConfig(event).public.siteUrl.replace(/\/$/, '')
  setHeader(event, 'Content-Type', 'application/xml; charset=utf-8')
  const urls = PAGES.map(path => `  <url><loc>${site}${path}</loc></url>`).join('\n')
  return `<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n${urls}\n</urlset>\n`
})
