import { LOCALIZED_PAGES } from './i18n/pages'

// https://nuxt.com/docs/api/configuration/nuxt-config
export default defineNuxtConfig({
  // Public website (doc 08): server rendered for fast first paint on slow Android phones and for
  // link previews (WhatsApp reads the Open Graph tags), with very little JavaScript.
  modules: ['@nuxtjs/i18n', '@nuxt/eslint'],
  devtools: { enabled: false },

  app: {
    head: {
      htmlAttrs: { lang: 'es' },
      meta: [
        { name: 'viewport', content: 'width=device-width, initial-scale=1' },
        { name: 'theme-color', content: '#0E7C5A' },
        { property: 'og:site_name', content: 'Kuulis' },
        { property: 'og:type', content: 'website' },
        { name: 'twitter:card', content: 'summary_large_image' },
      ],
      link: [
        { rel: 'icon', type: 'image/svg+xml', href: '/favicon.svg' },
        { rel: 'apple-touch-icon', href: '/icon-192.png' },
      ],
    },
  },
  css: ['@fontsource-variable/plus-jakarta-sans/wght.css', '~/assets/css/main.css'],

  runtimeConfig: {
    // Where the server renderer reaches the API (e.g. http://kuulis-api-qa:8000/api/v1 on the Docker
    // network). Empty: the same host the visitor used (https://<host>/api/v1).
    apiInternal: '',
    public: {
      // The browser always calls the API on the same origin (/api is routed to it).
      apiBase: '/api/v1',
      appEnv: 'local',
      // Canonical origin for links in sitemap.xml and Open Graph (NUXT_PUBLIC_SITE_URL).
      siteUrl: 'http://localhost:3001',
      // Shown in the footer and the help section when set (NUXT_PUBLIC_SUPPORT_EMAIL).
      supportEmail: '',
      // Map tiles for the live ride page (OSM's tile policy: light use, attribution, a Referer). Point
      // NUXT_PUBLIC_MAP_TILE_URL at a self-hosted or commercial server if usage grows.
      mapTileUrl: 'https://tile.openstreetmap.org/{z}/{x}/{y}.png',
    },
  },

  routeRules: {
    '/**': {
      headers: {
        'X-Frame-Options': 'DENY',
        'X-Content-Type-Options': 'nosniff',
        'Referrer-Policy': 'strict-origin-when-cross-origin',
        'Permissions-Policy': 'camera=(), microphone=(), geolocation=(), payment=()',
        'Strict-Transport-Security': 'max-age=31536000',
        'Content-Security-Policy': [
          'default-src \'self\'',
          'script-src \'self\' \'unsafe-inline\'',
          'style-src \'self\' \'unsafe-inline\'',
          'img-src \'self\' data: https:',
          'font-src \'self\' data:',
          'connect-src \'self\'',
          'object-src \'none\'',
          'base-uri \'self\'',
          'form-action \'self\'',
          'frame-ancestors \'none\'',
        ].join('; '),
      },
    },
    // Pages that act on a one-time token: never cached, never indexed (also their English variants).
    '/verify-email': { headers: { 'Cache-Control': 'no-store', 'X-Robots-Tag': 'noindex' } },
    '/reset-password': { headers: { 'Cache-Control': 'no-store', 'X-Robots-Tag': 'noindex' } },
    '/en/verify-email': { headers: { 'Cache-Control': 'no-store', 'X-Robots-Tag': 'noindex' } },
    '/en/reset-password': { headers: { 'Cache-Control': 'no-store', 'X-Robots-Tag': 'noindex' } },
    // Live ride links (doc 11): private, change every few seconds.
    '/v/**': { headers: { 'Cache-Control': 'no-store', 'X-Robots-Tag': 'noindex' } },
    '/en/v/**': { headers: { 'Cache-Control': 'no-store', 'X-Robots-Tag': 'noindex' } },
  },
  compatibilityDate: '2026-10-01',

  nitro: {
    compressPublicAssets: true,
    // Local dev: forward /api to the FastAPI dev server.
    devProxy: {
      '/api': { target: 'http://localhost:8000/api', changeOrigin: true },
    },
  },

  typescript: { strict: true },
  eslint: { config: { stylistic: true } },

  // Spanish at /, English at /en with English paths (docs/website-redesign/06 §4), so both get indexed. Only the
  // root redirects by language: to the visitor's last choice (kuulis_locale cookie) or, on a first visit, to the
  // browser's language. Links from emails and the app have no prefix; middleware/utility-locale.global.ts sends
  // them to the right language.
  i18n: {
    defaultLocale: 'es',
    strategy: 'prefix_except_default',
    customRoutes: 'config',
    pages: LOCALIZED_PAGES,
    locales: [
      { code: 'es', language: 'es-VE', name: 'Español', file: 'es.json' },
      { code: 'en', language: 'en', name: 'English', file: 'en.json' },
    ],
    detectBrowserLanguage: { useCookie: true, cookieKey: 'kuulis_locale', redirectOn: 'root', alwaysRedirect: true, fallbackLocale: 'es' },
  },
})
