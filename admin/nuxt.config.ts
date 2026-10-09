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
