// Renders the link-preview images (og:image) for the main pages, one per language: 1200×630 JPEG in public/og/
// (Kuulis de noche: the night photo, the poster headline, the yellow route). The headline comes from the page's own
// title in i18n/locales, so a copy change only needs `pnpm og` again. Uses the Playwright Chromium the e2e tests
// already need.
import { readFileSync, statSync } from 'node:fs'
import { dirname, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'
import { chromium } from '@playwright/test'

const root = resolve(dirname(fileURLToPath(import.meta.url)), '..')
// Inlined: a page set with setContent may not load file:// fonts or images.
const inline = (path, type) => `data:${type};base64,${readFileSync(resolve(root, path)).toString('base64')}`
const jakarta = inline('node_modules/@fontsource-variable/plus-jakarta-sans/files/plus-jakarta-sans-latin-wght-normal.woff2', 'font/woff2')
const poster = inline('public/fonts/archivo-poster.woff2', 'font/woff2')
const photo = inline('public/img/fotos/caracas-noche-1280.webp', 'image/webp')
// The «K punto» logo in its negative version (white on the night photo).
const logo = inline('public/brand/kuulis-horizontal-negativo.svg', 'image/svg+xml')

/** Page key (the file name) → where its headline lives in the locale file. Keep in sync with OG_PAGES in useLocaleSeo. */
const PAGES = { home: 'home.hero.title', drivers: 'drivers.title', safety: 'safety.title', download: 'download.title' }
const MAX_BYTES = 160 * 1024

const escape = text => text.replace(/&/g, '&amp;').replace(/</g, '&lt;')
/** The final full stop as the yellow dot, like the headlines on the site. */
const headline = title => escape(title).replace(/\.$/, '<span class="dot"></span>')

const html = title => `<!doctype html><html><head><style>
@font-face { font-family: Jakarta; src: url(${jakarta}) format('woff2'); font-weight: 200 800; }
@font-face { font-family: Poster; src: url(${poster}) format('woff2'); font-weight: 800 900; font-stretch: 62% 75%; }
* { margin: 0; box-sizing: border-box; }
body { width: 1200px; height: 630px; background: #07120e url(${photo}) 60% 40% / cover; color: #fff; font-family: Jakarta; position: relative; overflow: hidden; }
body::before { content: ''; position: absolute; inset: 0; background: linear-gradient(90deg, rgb(7 18 14 / 94%) 0%, rgb(7 18 14 / 75%) 55%, rgb(7 18 14 / 35%) 100%); }
.logo { position: absolute; left: 80px; top: 64px; height: 44px; }
h1 { position: absolute; left: 80px; bottom: 110px; width: 820px; font-family: Poster; font-size: 104px; font-weight: 900; font-stretch: 66%; line-height: 0.9; text-transform: uppercase; text-wrap: balance; }
.dot { display: inline-block; width: 0.2em; height: 0.2em; margin-left: 0.05em; border-radius: 50%; background: #ffc83d; }
.route { position: absolute; left: 0; bottom: 0; width: 1200px; height: 90px; }
</style></head><body>
<img class="logo" src="${logo}" alt="Kuulis">
<h1>${headline(title)}</h1>
<svg class="route" viewBox="0 0 1200 90" preserveAspectRatio="none" fill="none">
  <path d="M-20 70 C 220 76, 330 26, 560 40 S 900 80, 1220 18" stroke="#ffc83d" stroke-width="5" stroke-linecap="round" />
</svg>
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
      if (!document.fonts.check('800 44px Jakarta')) throw new Error('Plus Jakarta Sans did not load')
      if (!document.fonts.check('900 104px Poster')) throw new Error('The poster face did not load')
    })
    const file = resolve(root, `public/og/${key}-${locale}.jpg`)
    await page.screenshot({ path: file, type: 'jpeg', quality: 82 })
    const bytes = statSync(file).size
    failed ||= bytes > MAX_BYTES
    console.log(`${bytes > MAX_BYTES ? '✗' : '✓'} public/og/${key}-${locale}.jpg ${(bytes / 1024).toFixed(0)} KB`)
  }
}
await browser.close()
if (failed) {
  console.error(`At least one image is over ${MAX_BYTES / 1024} KB.`)
  process.exit(1)
}
