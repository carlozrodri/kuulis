/** QA and local are never indexed; production lists the sitemap. */
export default defineEventHandler((event) => {
  const config = useRuntimeConfig(event)
  setHeader(event, 'Content-Type', 'text/plain; charset=utf-8')
  if (config.public.appEnv !== 'production') return 'User-agent: *\nDisallow: /\n'
  return `User-agent: *\nDisallow: /verify-email\nDisallow: /reset-password\nDisallow: /i/\n\nSitemap: ${config.public.siteUrl}/sitemap.xml\n`
})
