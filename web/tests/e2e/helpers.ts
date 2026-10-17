import { expect, type Page } from '@playwright/test'

/** Scrolls to each v-reveal section still waiting, so all are shown before a check reads the whole page. */
export async function revealAll(page: Page) {
  const count = await page.locator('.reveal-pending').count()
  for (let i = 0; i < count; i++) {
    await page.locator('.reveal').nth(i).evaluate(el => el.scrollIntoView({ block: 'center' }))
    await expect(page.locator('.reveal').nth(i)).not.toHaveClass(/reveal-pending/)
  }
  await page.evaluate(() => window.scrollTo(0, 0))
  await page.waitForTimeout(400)
}
