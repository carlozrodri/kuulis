import AxeBuilder from '@axe-core/playwright'
import { expect, test } from '@playwright/test'

// Smoke test of the public pages (docs/website-redesign/08): each page loads in both languages, has one h1,
// the right <html lang>, no horizontal scroll on a small phone or a desktop, no console errors and no serious
// accessibility violations.
const PAGES = ['/', '/motorizados', '/descargar', '/ayuda', '/contacto', '/legal']
const WIDTHS = [320, 1440]
const LOCALES = ['es', 'en'] as const

// Injected by the CDN in front of QA, blocked by our CSP on purpose: not the site's error.
const IGNORED_CONSOLE = [/cloudflareinsights/]

// Known violations of the current site, each with the milestone that removes it. Delete the entry with the fix.
const KNOWN_AXE: Record<string, string> = {}

for (const locale of LOCALES) {
  for (const width of WIDTHS) {
    for (const path of PAGES) {
      test(`${locale} ${width}px ${path}`, async ({ page, context, baseURL }) => {
        await context.addCookies([{ name: 'kuulis_locale', value: locale, url: baseURL! }])
        await page.setViewportSize({ width, height: 900 })
        const errors: string[] = []
        page.on('console', (message) => {
          if (message.type() === 'error' && !IGNORED_CONSOLE.some(re => re.test(message.text()))) errors.push(message.text())
        })

        const response = await page.goto(path, { waitUntil: 'networkidle' })
        expect(response?.status()).toBe(200)
        await expect(page.locator('html')).toHaveAttribute('lang', locale)
        await expect(page.locator('h1')).toHaveCount(1)
        const overflow = await page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth)
        expect(overflow).toBeLessThanOrEqual(0)

        const axe = await new AxeBuilder({ page }).withTags(['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa', 'wcag22aa']).analyze()
        const serious = axe.violations.filter(v => (v.impact === 'serious' || v.impact === 'critical') && !KNOWN_AXE[v.id])
        expect(serious.map(v => `${v.id}: ${v.nodes.map(n => n.target.join(' ')).join(', ')}`)).toEqual([])
        expect(errors).toEqual([])
      })
    }
  }
}
