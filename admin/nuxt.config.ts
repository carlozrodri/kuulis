// https://nuxt.com/docs/api/configuration/nuxt-config
export default defineNuxtConfig({
  // Internal admin panel: SPA served by the Nitro node server, no SEO needed.
  modules: ['@nuxt/ui', '@nuxtjs/i18n', '@nuxt/eslint'],
  ssr: false, devtools: { enabled: true },

  app: {
    head: {
      title: 'Kuulis Admin',
      meta: [{ name: 'robots', content: 'noindex, nofollow' }],
    },
  },
  css: ['~/assets/css/main.css'],

  runtimeConfig: {
    public: {
      // Same origin in QA/production (https://<host>/api/v1). Override with NUXT_PUBLIC_API_BASE.
      apiBase: '/api/v1',
      appEnv: 'local',
      // Git commit of the build (NUXT_PUBLIC_COMMIT, set from Coolify's SOURCE_COMMIT in the Dockerfile).
      commit: '',
      // Raster tiles for the ride maps (Leaflet). OpenStreetMap's standard tiles are fine for a
      // low-volume internal panel per https://operations.osmfoundation.org/policies/tiles/ (attribution
      // required, no bulk downloads). Point NUXT_PUBLIC_MAP_TILE_URL at a self-hosted/commercial server if usage grows.
      mapTileUrl: 'https://tile.openstreetmap.org/{z}/{x}/{y}.png',
      mapTileAttribution: '&copy; <a href="https://www.openstreetmap.org/copyright" target="_blank" rel="noopener">OpenStreetMap</a> contributors',
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
        'Cross-Origin-Opener-Policy': 'same-origin',
        // Scripts only from this origin ('unsafe-inline' for the small bootstrap scripts Nuxt and
        // the color mode inline in the SPA shell). Images also from https: (map tiles and the
        // short-lived S3 links of driver documents). The API is same-origin (/api).
        'Content-Security-Policy': [
          'default-src \'self\'',
          'script-src \'self\' \'unsafe-inline\'',
          'style-src \'self\' \'unsafe-inline\'',
          'img-src \'self\' data: blob: https:',
          'font-src \'self\' data:',
          'connect-src \'self\'',
          'object-src \'none\'',
          'base-uri \'self\'',
          'form-action \'self\'',
          'frame-ancestors \'none\'',
        ].join('; '),
      },
    },
  },
  compatibilityDate: '2026-10-01',

  nitro: {
    // Local dev: forward /api to the FastAPI dev server.
    devProxy: {
      '/api': { target: 'http://localhost:8000/api', changeOrigin: true, ws: true },
    },
  },

  typescript: { strict: true },
  eslint: { config: { stylistic: true } },

  i18n: {
    defaultLocale: 'es',
    strategy: 'no_prefix',
    locales: [
      { code: 'es', language: 'es-ES', name: 'Español', file: 'es.json' },
      { code: 'en', language: 'en-US', name: 'English', file: 'en.json' },
    ],
    detectBrowserLanguage: { useCookie: true, cookieKey: 'kuulis_locale', fallbackLocale: 'es' },
  },

  // Every icon ships in the bundle (scanned from the source): no requests to api.iconify.design,
  // which the CSP's connect-src would block anyway.
  icon: {
    // .ts too: the menu's icons live in app/utils/nav.ts.
    clientBundle: { scan: { globInclude: ['**/*.{vue,ts}'] }, sizeLimitKb: 512 },
    fallbackToApi: false,
  },
})
