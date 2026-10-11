# Kuulis Web

Public website (doc 08): Nuxt 4 with server rendering, plain CSS, i18n (es / en). Home, drivers, download,
legal texts, and the pages the emails link to (`/verify-email`, `/reset-password`).

```bash
pnpm install
cp .env.example .env
pnpm dev          # http://localhost:3001 (proxies /api to the FastAPI dev server on :8000)
pnpm lint && pnpm typecheck && pnpm test
pnpm build        # .output/ node server, used by the Dockerfile
```

- Data comes from the API: `GET /public/site` (cities, driver requirements, fee tiers) and `GET /legal`.
- In QA/production the site and the API share the domain (`https://<host>` and `https://<host>/api`), so the
  browser needs no CORS. The server renderer reaches the API at `NUXT_API_INTERNAL` when set.
- `robots.txt` blocks crawlers unless `NUXT_PUBLIC_APP_ENV=production`.
- Keep it light: no UI library, no client-side state store; the target is cheap Android phones on slow data.
