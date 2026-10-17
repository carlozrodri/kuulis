// Renders the link-preview images (og:image) for the main pages, one per language: 1200×630 PNG in public/og/
// (docs/website-redesign/05 A8). The headline comes from the page's own title in i18n/locales, so a copy change
// only needs `pnpm og` again. Uses the Playwright Chromium the e2e tests already need.
import { readFileSync, statSync } from 'node:fs'
import { dirname, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'
import { chromium } from '@playwright/test'

const root = resolve(dirname(fileURLToPath(import.meta.url)), '..')
// Inlined: a page set with setContent may not load file:// fonts.
const font = `data:font/woff2;base64,${readFileSync(resolve(root, 'node_modules/@fontsource-variable/plus-jakarta-sans/files/plus-jakarta-sans-latin-wght-normal.woff2')).toString('base64')}`
const ridge = readFileSync(resolve(root, 'app/components/brand/AvilaRidge.vue'), 'utf8').match(/<path d="([^"]+)"/)[1]

/** Page key (the file name) → where its headline lives in the locale file. Keep in sync with OG_PAGES in useLocaleSeo. */
const PAGES = { home: 'home.hero.title', drivers: 'drivers.title', safety: 'safety.title', download: 'download.title' }
const MAX_BYTES = 120 * 1024

const escape = text => text.replace(/&/g, '&amp;').replace(/</g, '&lt;')
/** The final period in yellow, like the headlines on the site. */
const headline = title => escape(title).replace(/\.$/, '<span class="dot">.</span>')

const html = title => `<!doctype html><html><head><style>
@font-face { font-family: Jakarta; src: url(${font}) format('woff2'); font-weight: 200 800; }
* { margin: 0; box-sizing: border-box; }
body { width: 1200px; height: 630px; background: #0e7c5a; color: #fff; font-family: Jakarta; position: relative; overflow: hidden; }
.wordmark { position: absolute; left: 80px; top: 64px; font-size: 44px; font-weight: 800; letter-spacing: -0.03em; }
.dot { color: #ffc83d; }
h1 { position: absolute; left: 80px; bottom: 170px; width: 720px; font-size: 76px; line-height: 1.04; font-weight: 800; letter-spacing: -0.035em; text-wrap: balance; }
.route { position: absolute; right: 70px; top: 70px; width: 300px; height: 350px; }
.ridge { position: absolute; left: 0; bottom: 0; width: 1200px; height: 110px; fill: #0a5c43; }
</style></head><body>
<div class="wordmark">kuulis<span class="dot">.</span></div>
<h1>${headline(title)}</h1>
<svg class="route" viewBox="40 20 400 520" fill="none">
  <path d="M84 500C84 420 150 392 228 380S392 344 392 262 300 170 300 112 344 60 396 60" stroke="#fff" stroke-width="8" stroke-linecap="round" stroke-dasharray="2 18" />
  <circle cx="84" cy="500" r="18" fill="#0e7c5a" stroke="#fff" stroke-width="8" />
  <circle cx="396" cy="60" r="22" fill="#ffc83d" />
</svg>
<svg class="ridge" viewBox="0 0 1440 120" preserveAspectRatio="none"><path d="${ridge}" /></svg>
</body></html>`

const browser = await chromium.launch(process.env.CHROMIUM_PATH ? { executablePath: process.env.CHROMIUM_PATH } : {})
const page = await browser.newPage({ viewport: { width: 1200, height: 630 } })
let failed = false
for (const locale of ['es', 'en']) {
  const messages = JSON.parse(readFileSync(resolve(root, `i18n/locales/${locale}.json`), 'utf8'))
  for (const [key, path] of Object.entries(PAGES)) {
    const title = path.split('.').reduce((node, part) => node[part], messages)
    await page.setContent(html(title))
    await page.evaluate(async () => {
      await document.fonts.ready
      if (!document.fonts.check('800 76px Jakarta')) throw new Error('Plus Jakarta Sans did not load')
    })
    const file = resolve(root, `public/og/${key}-${locale}.png`)
    await page.screenshot({ path: file, type: 'png' })
    const bytes = statSync(file).size
    failed ||= bytes > MAX_BYTES
    console.log(`${bytes > MAX_BYTES ? '✗' : '✓'} public/og/${key}-${locale}.png ${(bytes / 1024).toFixed(0)} KB`)
  }
}
await browser.close()
if (failed) {
  console.error(`At least one image is over ${MAX_BYTES / 1024} KB.`)
  process.exit(1)
}
