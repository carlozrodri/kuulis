import AxeBuilder from '@axe-core/playwright'
import { expect, test } from '@playwright/test'
import { englishPath } from '../../i18n/pages'
import { revealAll } from './helpers'

// Polish checks (docs/website-redesign/08 §2–§4): every width of the checklist without sideways scroll, headings
// without skipped levels, axe in dark mode, no Spanish left on English pages, sections that appear once on scroll,
// and nothing moving with reduced motion.
test.use({ locale: 'es-VE' })

const PAGES = ['/', '/motorizados', '/seguridad', '/descargar', '/ayuda', '/contacto', '/legal', '/legal/terms']
const WIDTHS = [320, 360, 414, 768, 1024, 1440, 1920]

for (const path of PAGES) {
  for (const locale of ['es', 'en']) {
    const url = locale === 'en' ? englishPath(path) : path
    test(`${url}: no sideways scroll at any width and no skipped heading level`, async ({ page }) => {
      for (const width of WIDTHS) {
        await page.setViewportSize({ width, height: 800 })
        await page.goto(url, { waitUntil: 'networkidle' })
        const overflow = await page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth)
        expect(overflow, `${width}px`).toBeLessThanOrEqual(0)
      }
      const levels = await page.locator('h1, h2, h3, h4, h5, h6').evaluateAll(headings => headings.map(h => Number(h.tagName[1])))
      expect(levels[0]).toBe(1)
      levels.forEach((level, i) => expect(level - (levels[i - 1] ?? 0), levels.join(' ')).toBeLessThanOrEqual(1))
    })
  }
}

test.describe('dark mode', () => {
  test.use({ colorScheme: 'dark' })
  for (const path of PAGES) {
    for (const width of [360, 1440]) {
      test(`${path} at ${width}px has no serious axe violation`, async ({ page }) => {
        await page.setViewportSize({ width, height: 900 })
        await page.goto(path, { waitUntil: 'networkidle' })
        await revealAll(page)
        const axe = await new AxeBuilder({ page }).withTags(['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa', 'wcag22aa']).analyze()
        const serious = axe.violations.filter(v => v.impact === 'serious' || v.impact === 'critical')
        expect(serious.map(v => `${v.id}: ${v.nodes.map(n => n.target.join(' ')).join(', ')}`)).toEqual([])
      })
    }
  }
})

// Words that only a Spanish page would show; legal texts are fetched from the API in Spanish on purpose.
const SPANISH = /\b(Descarga|Descargar|Inicio|Motorizados|Seguridad|Ayuda|Contacto|viaje|precio|también|cuota|tarifa)\b/
test('on a phone, every control outside running text is at least 44 px tall', async ({ page }) => {
  await page.setViewportSize({ width: 360, height: 800 })
  for (const path of ['/', '/motorizados', '/seguridad', '/descargar', '/ayuda', '/contacto', '/en']) {
    await page.goto(path, { waitUntil: 'networkidle' })
    const small = await page.locator('a, button, summary, input, select, textarea').evaluateAll(controls => controls
      .filter((control) => {
        const box = control.getBoundingClientRect()
        // Links inside a sentence are exempt (WCAG 2.5.8), and so is the skip link until it is focused.
        if (!control.checkVisibility({ visibilityProperty: true }) || control.classList.contains('sr-only') || control.closest('p')) return false
        // The header button draws its 44 px target with ::before around a 40 px pill.
        const extra = control.classList.contains('cta') ? 4 : 0
        return box.height + extra < 44
      })
      .map(control => `${control.textContent?.trim()} ${Math.round(control.getBoundingClientRect().height)}px`))
    expect(small, path).toEqual([])
  }
})

test('English pages show no Spanish', async ({ page }) => {
  for (const path of PAGES.filter(p => p !== '/legal/terms')) {
    await page.goto(englishPath(path), { waitUntil: 'networkidle' })
    const text = await page.locator('body').innerText()
    expect(text.match(SPANISH)?.[0], englishPath(path)).toBeUndefined()
  }
})

test('sections below the fold appear when scrolled to, once', async ({ page }) => {
  await page.setViewportSize({ width: 360, height: 740 })
  await page.goto('/', { waitUntil: 'networkidle' })
  // On screen when the page opens: never hidden.
  await expect(page.locator('#hero.reveal-pending')).toHaveCount(0)
  const faq = page.locator('.faq')
  await expect(faq).toHaveClass(/reveal-pending/)
  await faq.scrollIntoViewIfNeeded()
  await expect(faq).not.toHaveClass(/reveal-pending/)
  await page.evaluate(() => window.scrollTo(0, 0))
  await expect(faq).not.toHaveClass(/reveal-pending/)
})

test('without JavaScript every section is visible', async ({ browser }) => {
  const context = await browser.newContext({ javaScriptEnabled: false, locale: 'es-VE' })
  const page = await context.newPage()
  await page.goto('/')
  await expect(page.locator('.reveal-pending')).toHaveCount(0)
  await expect(page.locator('.faq h2')).toBeVisible()
  await context.close()
})

test('with reduced motion nothing animates and nothing waits to appear', async ({ browser }) => {
  const context = await browser.newContext({ reducedMotion: 'reduce', locale: 'es-VE' })
  const page = await context.newPage()
  for (const path of ['/', '/motorizados', '/seguridad', '/descargar']) {
    await page.goto(path, { waitUntil: 'networkidle' })
    await expect(page.locator('.reveal-pending'), path).toHaveCount(0)
    await page.locator('footer').scrollIntoViewIfNeeded()
    const moving = await page.evaluate(() => document.getAnimations().map(a => (a as CSSAnimation).animationName ?? a.constructor.name))
    expect(moving, path).toEqual([])
  }
  await context.close()
})
