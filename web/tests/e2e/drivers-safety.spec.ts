import { expect, test } from '@playwright/test'

// Drivers and safety pages (docs/website-redesign/07 M6): the fee example agrees with the fee table, the ink hero
// header, and the safety page's phases, emergency notice and community link. Without the API (a local build) the
// figures are left out instead of guessed.
test.use({ locale: 'es-VE' })

test('drivers: the header wears the ink hero, then turns light', async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 900 })
  await page.goto('/motorizados', { waitUntil: 'networkidle' })
  const header = page.locator('header')
  await expect(header).toHaveClass(/on-ink/)
  await page.locator('.faq').scrollIntoViewIfNeeded()
  await expect(header).not.toHaveClass(/on-hero/)
})

test('drivers: the fee example charges what the table says for $250', async ({ page }) => {
  await page.goto('/motorizados', { waitUntil: 'networkidle' })
  const example = page.locator('.example')
  test.skip(await example.count() === 0, 'no fee tiers without the API')
  const [, fee, rest] = (await example.innerText()).match(/\$250.*?(\$\d+).*?(\$\d+)/) ?? []
  const rows = await page.locator('.fees tbody tr').evaluateAll(trs => trs.map(tr => [...tr.querySelectorAll('td')].map(td => td.textContent!.trim())))
  const row = rows.find(([range]) => {
    const [from, to] = (range!.match(/\d+/g) ?? []).map(Number)
    return 250 > from! && (to === undefined || 250 <= to)
  })
  expect(row?.[1]).toBe(fee)
  expect(Number(rest!.slice(1))).toBe(250 - Number(fee!.slice(1)))
})

test('safety: four phases, the emergency notice and the community guidelines', async ({ page }) => {
  await page.goto('/seguridad', { waitUntil: 'networkidle' })
  await expect(page.locator('.phase h2')).toHaveText(['Antes', 'Durante', 'Si algo pasa', 'Después'])
  await expect(page.locator('.notice')).toContainText('911')
  await expect(page.locator('main a[href="/legal/community"]')).toBeVisible()
})

test('without the API the PIN row and the fee figures are left out', async ({ page }) => {
  test.skip(!!process.env.E2E_BASE_URL, 'a deployed site has the API')
  await page.goto('/seguridad', { waitUntil: 'networkidle' })
  await expect(page.locator('.phase h3', { hasText: 'PIN' })).toHaveCount(0)
  await expect(page.locator('.pin')).toHaveCount(0)
  await page.goto('/motorizados', { waitUntil: 'networkidle' })
  await expect(page.locator('.example')).toHaveCount(0)
  await expect(page.locator('.fees table')).toHaveCount(0)
})

test('the safety page is linked from the header, footer and home', async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 900 })
  await page.goto('/', { waitUntil: 'networkidle' })
  await expect(page.locator('header .nav a[href="/seguridad"]')).toBeVisible()
  await expect(page.locator('footer a[href="/seguridad"]')).toBeVisible()
  await expect(page.locator('.safety a[href="/seguridad"]')).toBeVisible()
})
