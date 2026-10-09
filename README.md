# Kuulis

Monorepo privado de Kuulis.

| Carpeta | Qué es | Stack |
| --- | --- | --- |
| [`docs/`](docs/README.md) | Arquitectura, decisiones, despliegue, roadmap, pendientes y bloqueos | Markdown |
| [`api/`](api/README.md) | API REST `/api/v1` + WebSockets + worker de tareas | FastAPI, SQLAlchemy 2, Alembic, PostgreSQL, Redis, Taskiq |
| [`admin/`](admin/README.md) | Panel de administración con roles | Nuxt 4, TypeScript, Nuxt UI, i18n |
| [`mobile/`](mobile/README.md) | App iOS y Android | React Native, Expo SDK 57, Expo Router, TypeScript, i18n |

## Entornos

| Rama | Entorno | URL |
| --- | --- | --- |
| `qa` | QA | https://kuulis-qa.top8.uk (admin) · https://kuulis-qa.top8.uk/api/v1 |
| `main` | Producción | https://kuulis-prod.top8.uk (admin) · https://kuulis-prod.top8.uk/api/v1 |

Coolify despliega automáticamente al hacer push. Flujo: `feature/*` → PR a `qa` → PR de `qa` a `main`.
Detalles en [docs/deployment.md](docs/deployment.md).
