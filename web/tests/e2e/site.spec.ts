import { expect, test } from '@playwright/test'

// Whole-site checks over every page in the sitemap (docs/website-redesign/08 §5 and §8): each has its own title and
// description, and no internal link anywhere leads to an error.
test.use({ locale: 'es-VE' })

async function sitemapPaths(request: import('@playwright/test').APIRequestContext) {
  const xml = await (await request.get('/sitemap.xml')).text()
  return [...xml.matchAll(/<loc>([^<]+)<\/loc>/g)].map(match => new URL(match[1]!).pathname)
}

test('every page in the sitemap has its own title and description in its language', async ({ page, request }) => {
  const seen = new Map<string, string>()
  for (const path of await sitemapPaths(request)) {
    await page.goto(path)
    const locale = path === '/en' || path.startsWith('/en/') ? 'en' : 'es'
    const title = await page.title()
    const description = await page.locator('meta[name="description"]').getAttribute('content')
    expect(description, path).toBeTruthy()
    // "Legal" is the same word in both languages, so titles only need to differ within one.
    for (const value of [`${locale} title: ${title}`, `description: ${description}`]) {
      expect(seen.get(value), `${path} repeats the ${value} of ${seen.get(value)}`).toBeUndefined()
      seen.set(value, path)
    }
  }
})

test('no internal link on any page leads to an error', async ({ page, request }) => {
  test.setTimeout(180_000)
  const links = new Set<string>()
  for (const path of await sitemapPaths(request)) {
    await page.goto(path)
    const hrefs = await page.locator('a[href^="/"]').evaluateAll(anchors => anchors.map(a => a.getAttribute('href')!))
    hrefs.forEach(href => links.add(href.split('#')[0]!))
  }
  const broken: string[] = []
  for (const href of links) {
    // API links (the APK) go to the API: a deployed site serves it, a local build reads it from E2E_API_URL or has
    // none. The redirect to the file is enough.
    const api = href.startsWith('/api/')
    const apiBase = process.env.E2E_API_URL ?? (process.env.E2E_BASE_URL ? '' : undefined)
    if (api && apiBase === undefined) continue
    const response = await request.get(api ? `${apiBase}${href}` : href, { maxRedirects: api ? 0 : 5 })
    if (response.status() >= 400) broken.push(`${href} ${response.status()}`)
  }
  expect(broken).toEqual([])
})
