# Kuulis Admin

Nuxt 4 + TypeScript + Nuxt UI admin panel with role-based access (staff / admin) and i18n (es / en).

```bash
pnpm install
cp .env.example .env
pnpm dev          # http://localhost:3000 (proxies /api to the FastAPI dev server on :8000)
pnpm lint && pnpm typecheck
pnpm build        # .output/ node server, used by the Dockerfile
```

- Login uses `POST /api/v1/auth/admin/login`, which only issues tokens to `staff` and `admin` users.
- `app/middleware/auth.global.ts` protects every route; pages can require roles with
  `definePageMeta({ roles: ['admin'] })`.
- Staff can read users and send notifications; only admins can edit users and roles (enforced by the API).
- Translations live in `i18n/locales/{es,en}.json`; API error codes map to `errors.<code>`.
- In QA/production the panel and the API share the domain (`https://<host>` and `https://<host>/api`),
  so no CORS is involved and tokens are first-party cookies.
