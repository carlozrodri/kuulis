# Decisiones técnicas

Formato: decisión, alternativas consideradas y motivo. Fecha: 2026-10-09 salvo que se indique.

1. **Monorepo** (`api/`, `admin/`, `mobile/`, `docs/`). Un solo repo privado `carlozrodri/kuulis`; Coolify
   despliega cada app con `base_directory` y `watch_paths`, así un cambio en `admin/` no redepliega la API.
2. **Ramas = entornos.** `main` → producción, `qa` → QA. Se trabaja en ramas `feature/*` con PR hacia `qa`;
   cuando QA está validado se hace PR de `qa` a `main`. Auto-deploy en push (CI/CD = Coolify).
3. **FastAPI con estructura Django.** Apps autocontenidas, settings por entorno y `manage.py`. Lógica en
   `services.py`, routers finos.
4. **PostgreSQL + SQLAlchemy 2 async + Alembic.** asyncpg es el driver async más rápido para Postgres.
5. **Taskiq (no Celery ni ARQ)** para tareas en background. Es async nativo (comparte código con la API sin
   envolver en `asyncio.run`), usa Redis Streams con confirmación y tiene scheduler. Celery es síncrono y ARQ
   está en modo mantenimiento.
6. **Refresh tokens en Redis**, no en Postgres: lecturas O(1), TTL automático, revocación inmediata.
7. **WebSockets con Redis pub/sub** en vez de sticky sessions: cualquier worker puede emitir a cualquier usuario.
8. **Expo Push Service** para iOS y Android: un solo endpoint, sin gestionar APNs/FCM directamente desde la API.
9. **Archivos con URLs prefirmadas**: la API no carga con el ancho de banda de las subidas.
10. **Admin en Nuxt 4 + Nuxt UI, modo SPA**: es interno, no necesita SEO; Nitro sirve los estáticos y el
    runtime config por entorno.
11. **Mismo dominio para admin y API** (`/` y `/api`): sin CORS para el admin y cookies first-party. Coolify
    quita el prefijo `/api` al enrutar; la API lo vuelve a poner (`RestoreApiPrefixMiddleware`).
12. **Postgres y Redis de Coolify** (plantillas oficiales), uno por entorno, sin puertos públicos.
13. **Sentry instalado pero apagado** en esta etapa, como pidió Carlos.
14. **El entorno QA en Coolify se llama `qa-env`**: Coolify exige nombres de 3+ caracteres.
