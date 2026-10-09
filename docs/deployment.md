# Despliegue (Coolify)

Coolify: proyecto **kuulis** (uuid `cexs6860hwyfto1mwzjrsflw`), servidor `localhost`, GitHub App
existente de Carlos. No comparte nada con los proyectos NDS ni bidding-market.

## Entornos y recursos

| Recurso | QA (entorno `qa-env`, rama `qa`) | Producción (entorno `production`, rama `main`) |
| --- | --- | --- |
| Dominio | `kuulis-qa.top8.uk` | `kuulis-prod.top8.uk` |
| API (`/api`) | `kuulis-api-qa` · `rayxgnveijwwq86tquloc3r8` | `kuulis-api-production` · `f14idkxf8c209b1hghrunmhb` |
| Worker | `kuulis-worker-qa` · `i10vqipywxmdafk5sjaowzya` | `kuulis-worker-production` · `f3eiht6l1r439xxp3401u2ur` |
| Admin (`/`) | `kuulis-admin-qa` · `m37iqum9dy4n0o5281n0tvu5` | `kuulis-admin-production` · `ru2e54bw4mn4igqvvdmkgrys` |
| PostgreSQL 17 | `kuulis-postgres-qa` · `v12h71ber6ifhpgcugm6adth` | `kuulis-postgres-production` · `pvx2gkfbo18zcld9x55t0tgp` |
| Redis 7.4 | `kuulis-redis-qa` · `miq3v8c99isk848ps719a7dn` | `kuulis-redis-production` · `mgtsa16kwmktv0jl55belww8` |
| Backup Postgres | diario 03:00, 7 días | cada 6 h, 14 días |

Cada app usa `base_directory` (`/api` o `/admin`), su `Dockerfile` y `watch_paths` (`api/**`, `admin/**`),
así que solo se redepliega lo que cambió. Auto-deploy activado: hacer push a `qa` o `main` despliega.

## Flujo de trabajo
1. Rama `feature/<algo>` desde `qa`.
2. PR hacia `qa` → merge → Coolify despliega QA.
3. Validar en `https://kuulis-qa.top8.uk`.
4. PR de `qa` a `main` → merge → Coolify despliega producción.

## Dominios (Nginx Proxy Manager)
Carlos crea en su NPM los proxy hosts `kuulis-qa.top8.uk` y `kuulis-prod.top8.uk` igual que los que ya
funcionan (por ejemplo `testqa.top8.uk`), apuntando al Traefik de Coolify. Importante:
- Activar **Websockets Support** (la app usa `wss://<host>/api/v1/ws`).
- Reenviar el host original (NPM lo hace por defecto) para que Traefik enrute por dominio.
- Traefik enruta `/api/*` a la API y todo lo demás al admin.

## Variables de entorno
Están puestas en Coolify (no en el repo). Lista completa en `api/.env.example` y `admin/.env.example`.

| Variable | API | Worker | Notas |
| --- | --- | --- | --- |
| `APP_ENV` | ✓ | ✓ | `qa` o `production` |
| `PROCESS_TYPE` | `api` | `worker` | misma imagen |
| `SECRET_KEY` | ✓ | ✓ | aleatoria por entorno |
| `DATABASE_URL`, `REDIS_URL` | ✓ | ✓ | URLs internas de Coolify |
| `AWS_*`, `STORAGE_PREFIX` | ✓ | ✓ | S3 del homelab, prefijo por entorno |
| `RESEND_API_KEY`, `EMAIL_FROM` | ✓ | ✓ | remitente `no-reply@email.top8.uk` (dominio verificado en Resend) |
| `FIRST_SUPERUSER_EMAIL/PASSWORD` | ✓ | | crea el primer admin al desplegar (idempotente) |
| `WEB_CONCURRENCY` | 4 | | workers gunicorn |
| `WORKER_CONCURRENCY`, `DB_POOL_SIZE`, `DB_MAX_OVERFLOW` | | 2 / 5 / 5 | |
| `SENTRY_ENABLED` | false | false | instalado, apagado |
| `NUXT_PUBLIC_APP_ENV`, `NUXT_PUBLIC_API_BASE` | | | solo admin |

La contraseña del primer admin está en la variable `FIRST_SUPERUSER_PASSWORD` de la app API de cada entorno
en Coolify. Conviene cambiarla desde el panel (Mi perfil) tras el primer login.

## Migraciones
La API ejecuta `alembic upgrade head` al arrancar (`RUN_MIGRATIONS=true`). Para crear una:
`cd api && uv run python manage.py makemigrations "mensaje"`, revisar el archivo y commitear.
Regla: migraciones compatibles hacia atrás (añadir columnas nullable, borrar en un segundo despliegue),
porque Coolify hace rolling update y la versión vieja convive unos segundos con el esquema nuevo.

## Health checks
- `GET /api/health/live` → proceso vivo (usado por Coolify).
- `GET /api/health/ready` → comprueba Postgres y Redis (503 si falla algo).

## Rollback
Coolify → app → Deployments → elegir un despliegue anterior → Redeploy. Si una migración rompió algo,
crear una migración nueva que lo revierta (no editar migraciones ya aplicadas).

## Backups
Configurados en Coolify para cada Postgres. **Pendiente de Carlos:** activar "Save to S3" y elegir su S3
en cada backup (la API de Coolify 4.1.2 no expone el id del S3, ver `blockers.md`).
Restaurar: Coolify → base de datos → Backups → Restore, o `pg_restore` del dump descargado de S3.
