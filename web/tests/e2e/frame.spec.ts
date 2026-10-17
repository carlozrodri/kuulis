import AxeBuilder from '@axe-core/playwright'
import { expect, test } from '@playwright/test'

// The site frame (docs/website-redesign/07 M2): the mobile menu keeps focus inside, makes the page inert, closes
// with Escape and on navigation; every footer link exists. The language link is covered by i18n.spec.ts.
test.use({ locale: 'es-VE' })

test('mobile menu: focus trap, inert page, Escape and close on navigation', async ({ page }) => {
  await page.setViewportSize({ width: 360, height: 740 })
  await page.goto('/motorizados', { waitUntil: 'networkidle' })
  const toggle = page.locator('button[aria-controls="mobile-menu"]')
  await expect(toggle).toHaveAttribute('aria-expanded', 'false')

  await toggle.focus()
  await page.keyboard.press('Enter')
  await expect(toggle).toHaveAttribute('aria-expanded', 'true')
  await expect(page.locator('#mobile-menu a').first()).toBeFocused()
  expect(await page.evaluate(() => document.querySelector('main')!.inert)).toBe(true)

  const axe = await new AxeBuilder({ page }).include('#mobile-menu').withTags(['wcag2a', 'wcag2aa', 'wcag22aa']).analyze()
  expect(axe.violations.filter(v => v.impact === 'serious' || v.impact === 'critical').map(v => v.id)).toEqual([])

  // Tabbing past the last item comes back to the menu button, never into the page behind.
  const stops = await page.locator('#mobile-menu a[href], #mobile-menu button').count()
  for (let i = 0; i < stops; i++) await page.keyboard.press('Tab')
  await expect(toggle).toBeFocused()
  await page.keyboard.press('Shift+Tab')
  expect(await page.evaluate(() => !!document.activeElement?.closest('#mobile-menu'))).toBe(true)

  await page.keyboard.press('Escape')
  await expect(toggle).toHaveAttribute('aria-expanded', 'false')
  await expect(toggle).toBeFocused()
  expect(await page.evaluate(() => document.querySelector('main')!.inert)).toBe(false)

  await toggle.click()
  await page.locator('#mobile-menu a[href="/ayuda"]').click()
  await page.waitForURL('**/ayuda')
  await expect(toggle).toHaveAttribute('aria-expanded', 'false')
})

test('every footer link answers 200', async ({ page, request }) => {
  await page.goto('/', { waitUntil: 'networkidle' })
  const hrefs = await page.locator('footer a[href^="/"]').evaluateAll(links => links.map(a => a.getAttribute('href')!))
  expect(hrefs.length).toBeGreaterThan(5)
  // Legal texts come from the API, which a local build has not got: they are checked only against a deployed site.
  const checked = process.env.E2E_BASE_URL ? hrefs : hrefs.filter(href => !href.startsWith('/legal/'))
  for (const href of new Set(checked)) expect((await request.get(href)).status(), href).toBe(200)
})
