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
})
