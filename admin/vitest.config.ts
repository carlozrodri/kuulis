import { fileURLToPath } from 'node:url'
import { defineConfig } from 'vitest/config'

// Unit tests for plain modules (utils, locales). Nuxt auto-imports are not available here, so tested
// files import what they use explicitly.
export default defineConfig({
  resolve: {
    alias: {
      '~': fileURLToPath(new URL('./app', import.meta.url)),
    },
  },
  test: {
    include: ['tests/**/*.test.ts'],
  },
})
