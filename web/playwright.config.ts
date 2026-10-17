import { defineConfig, devices } from '@playwright/test'

// End-to-end checks (docs/website-redesign, M0). Against a deployed site: E2E_BASE_URL=https://kuulis.top8.uk.
// Without it, runs the local production build (`pnpm build` first); pages then render without API data.
const baseURL = process.env.E2E_BASE_URL || 'http://localhost:3100'

export default defineConfig({
  testDir: 'tests/e2e',
  timeout: 30_000,
  fullyParallel: true,
  reporter: [['list']],
  use: { baseURL, ...devices['Desktop Chrome'] },
  webServer: process.env.E2E_BASE_URL
    ? undefined
    : {
        command: 'node .output/server/index.mjs',
        url: `${baseURL}/robots.txt`,
        env: { PORT: '3100', NUXT_PUBLIC_SITE_URL: baseURL },
        reuseExistingServer: true,
      },
})
