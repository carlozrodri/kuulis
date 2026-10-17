import { expect, test } from '@playwright/test'

// Home hero (docs/website-redesign/07 M3): the headline, lead and main button fit a 360×640 phone; the header wears
// the hero's green until the hero scrolls past; with reduced motion the route is drawn without animation.
test.use({ locale: 'es-VE' })

test('headline, lead and download button fit a 360×640 screen', async ({ page }) => {
  await page.setViewportSize({ width: 360, height: 640 })
  await page.goto('/', { waitUntil: 'networkidle' })
  const button = page.locator('.hero .btn-primary')
  await expect(button).toBeInViewport({ ratio: 1 })
  await expect(page.locator('h1')).toHaveText('En moto por Caracas. Precio claro, y punto.')
})

test('the header is green over the hero and light after it', async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 900 })
  await page.goto('/', { waitUntil: 'networkidle' })
  const header = page.locator('header')
  await expect(header).toHaveClass(/on-hero/)
  await page.mouse.wheel(0, 1200)
  await expect(header).not.toHaveClass(/on-hero/)
  await page.mouse.wheel(0, -1200)
  await expect(header).toHaveClass(/on-hero/)
  await page.goto('/ayuda', { waitUntil: 'networkidle' })
  await expect(header).not.toHaveClass(/on-hero/)
})

test('on a phone the header turns light after a jump past the hero, and green again at the top', async ({ page }) => {
  await page.setViewportSize({ width: 360, height: 740 })
  await page.goto('/', { waitUntil: 'networkidle' })
  const header = page.locator('header')
  await page.locator('.faq').scrollIntoViewIfNeeded()
  await expect(header).not.toHaveClass(/on-hero/)
  await page.evaluate(() => window.scrollTo(0, 0))
  await expect(header).toHaveClass(/on-hero/)
})

test('with reduced motion the route is not animated', async ({ browser }) => {
  const context = await browser.newContext({ reducedMotion: 'reduce', locale: 'es-VE' })
  const page = await context.newPage()
  await page.goto('/', { waitUntil: 'networkidle' })
  const animation = await page.locator('.hero .route .line').evaluate(line => getComputedStyle(line).animationName)
  expect(animation).toBe('none')
  await context.close()
})

test('without the API the home page leaves out the figures it cannot back', async ({ page }) => {
  test.skip(!!process.env.E2E_BASE_URL, 'a deployed site has its API')
  await page.goto('/', { waitUntil: 'networkidle' })
  await expect(page.locator('.drivers .fees')).toHaveCount(0)
  await expect(page.locator('.drivers .body')).not.toContainText('$')
  await expect(page.locator('.price .chips')).toHaveCount(0)
  await expect(page.locator('h3', { hasText: 'PIN de inicio' })).toHaveCount(0)
})
