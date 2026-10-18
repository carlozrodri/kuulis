import { expect, test } from '@playwright/test'

// Language URLs (docs/website-redesign/07 M5): Spanish at /, English at /en with English paths, only the root
// redirects by language, the language link keeps the page and the query, and links from emails and the app
// (no prefix) reach the visitor's language with their token intact.
test.describe('Spanish browser', () => {
  test.use({ locale: 'es-VE' })

  test('the language link keeps the page and the query, and the choice is remembered', async ({ page }) => {
    // Without an API (local build) /api/* would be answered by the site itself, resetting the language cookie.
    await page.route('**/api/**', route => route.fulfill({ status: 503 }))
    await page.setViewportSize({ width: 1440, height: 900 })
    await page.goto('/ayuda?q=pago', { waitUntil: 'networkidle' })
    const link = page.locator('header a.lang.desktop-only')
    await expect(link).toHaveText('English')
    await link.click()
    await page.waitForURL('**/en/help?q=pago')
    await expect(page.locator('html')).toHaveAttribute('lang', 'en')
    await expect(link).toHaveText('Español')

    await page.goto('/', { waitUntil: 'networkidle' })
    await expect(page).toHaveURL(/\/en$/)

    await page.locator('header a.lang.desktop-only').click()
    await page.waitForURL(url => new URL(url).pathname === '/')
    await page.goto('/', { waitUntil: 'networkidle' })
    await expect(page.locator('html')).toHaveAttribute('lang', 'es')
  })

  test('/ stays in Spanish and /en is English, without a cookie', async ({ page }) => {
    await page.goto('/')
    await expect(page.locator('html')).toHaveAttribute('lang', 'es')
    await page.goto('/en')
    await expect(page.locator('html')).toHaveAttribute('lang', 'en')
  })

  test('canonical and hreflang are absolute and reciprocal', async ({ page, request }) => {
    const alternates = async (path: string) => {
      await page.goto(path)
      return page.locator('link[rel="alternate"][hreflang]').evaluateAll(links =>
        Object.fromEntries(links.map(link => [link.getAttribute('hreflang'), new URL(link.getAttribute('href')!).pathname])))
    }
    const spanish = await alternates('/motorizados')
    expect(spanish).toEqual({ 'es-VE': '/motorizados', 'en': '/en/drivers', 'x-default': '/motorizados' })
    expect(await page.locator('link[rel="canonical"]').getAttribute('href')).toMatch(/^https?:\/\/[^/]+\/motorizados$/)
    expect(await alternates('/en/drivers')).toEqual(spanish)
    expect(await page.locator('link[rel="canonical"]').getAttribute('href')).toMatch(/\/en\/drivers$/)

    const sitemap = await (await request.get('/sitemap.xml')).text()
    expect(sitemap).toContain('/en/drivers</loc>')
    expect(sitemap).toContain('hreflang="x-default"')
  })

  test('each main page shares its own image, in the page language', async ({ page, request }) => {
    const pages = [
      ['/', 'home-es'], ['/en', 'home-en'], ['/motorizados', 'drivers-es'], ['/en/drivers', 'drivers-en'],
      ['/seguridad', 'safety-es'], ['/en/safety', 'safety-en'], ['/descargar', 'download-es'], ['/en/download', 'download-en'],
      ['/ayuda', 'home-es'],
    ]
    for (const [path, image] of pages) {
      await page.goto(path)
      const url = new URL((await page.locator('meta[property="og:image"]').getAttribute('content'))!)
      expect(url.pathname, path).toBe(`/og/${image}.jpg`)
      expect(await page.locator('meta[property="og:image:alt"]').getAttribute('content'), path).toBeTruthy()
      const file = await request.get(url.pathname)
      expect(file.status(), path).toBe(200)
      expect(file.headers()['content-type']).toBe('image/jpeg')
    }
  })

  test('every internal link on an English page stays in English', async ({ page }) => {
    await page.goto('/en/drivers', { waitUntil: 'networkidle' })
    const hrefs = await page.locator('a[href^="/"]:not([hreflang])').evaluateAll(links => links.map(a => a.getAttribute('href')!))
    expect(hrefs.length).toBeGreaterThan(5)
    expect(hrefs.filter(href => href !== '/en' && !href.startsWith('/en/'))).toEqual([])
  })

  test('private links stay in Spanish and are not given alternates', async ({ page }) => {
    await page.goto('/verify-email?token=abc')
    await expect(page).toHaveURL(/\/verify-email\?token=abc$/)
    await expect(page.locator('link[rel="canonical"], link[hreflang]')).toHaveCount(0)
  })
})

test.describe('English browser', () => {
  test.use({ locale: 'en-US' })

  test('the root redirects to /en on the first visit', async ({ page }) => {
    await page.goto('/')
    await expect(page).toHaveURL(/\/en$/)
  })

  test('links from emails and the app keep their token', async ({ page }) => {
    for (const path of ['/verify-email?token=abc.def', '/reset-password?token=xyz', '/i/AB3K7Q', '/v/tok123']) {
      await page.goto(path)
      expect(new URL(page.url()).pathname + new URL(page.url()).search).toBe(`/en${path}`)
    }
  })
})

test('an English cookie wins over a Spanish browser on links from emails', async ({ browser, baseURL }) => {
  const context = await browser.newContext({ locale: 'es-VE' })
  await context.addCookies([{ name: 'kuulis_locale', value: 'en', url: baseURL! }])
  const page = await context.newPage()
  await page.goto('/reset-password?token=xyz')
  await expect(page).toHaveURL(/\/en\/reset-password\?token=xyz$/)
  await context.close()
})
