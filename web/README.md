# Kuulis Web

Public website (doc 08): Nuxt 4 with server rendering, plain CSS, i18n (es at `/`, en at `/en`). Home, drivers,
safety, download, help, contact, legal texts, and the pages the emails and the app link to (`/verify-email`,
`/reset-password`, `/v/{token}`, `/i/{code}`). Design system and rules: `docs/website-redesign/` (02 visual
system, 06 implementation, 08 checklist).

```bash
pnpm install
cp .env.example .env
pnpm dev          # http://localhost:3001 (proxies /api to the FastAPI dev server on :8000)
pnpm lint && pnpm typecheck && pnpm test
pnpm build        # .output/ node server, used by the Dockerfile
pnpm e2e          # Playwright + axe on the build (or E2E_BASE_URL=https://kuulis.top8.uk E2E_API_URL=https://kuulis.top8.uk pnpm e2e)
pnpm og           # regenerate the link-preview images in public/og/ after a headline changes
```

- Data comes from the API: `GET /public/site` (cities, driver requirements, fee tiers) and `GET /legal`.
- In QA/production the site and the API share the domain (`https://<host>` and `https://<host>/api`), so the
  browser needs no CORS. The server renderer reaches the API at `NUXT_API_INTERNAL` when set.
- `robots.txt` blocks crawlers unless `NUXT_PUBLIC_APP_ENV=production`.
- `pnpm e2e` needs Chromium once: `pnpm exec playwright install chromium`. Not part of CI yet.
- Keep it light: no UI library, no client-side state store; the target is cheap Android phones on slow data.
- Colors live only in `app/assets/css/tokens.css`; `tests/contrast.test.ts` fails if a pair drops under AA.
  Never yellow on a light background. Headlines go through `<BrandHeadline>` (the final period is the brand dot).
- `v-reveal` (`app/plugins/reveal.ts`) fades a section in once; it hides nothing on the server, without
  JavaScript or with reduced motion. Checks that read the whole page call `revealAll` first (`tests/e2e/helpers.ts`).
- No figure on the site is written in the code: cities, fees, free months, requirements and the APK come from the
  API, so they stay true when the admin changes them.
