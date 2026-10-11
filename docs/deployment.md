# Despliegue (Coolify)

Coolify: proyecto **kuulis** (uuid `cexs6860hwyfto1mwzjrsflw`), servidor `localhost`, GitHub App
existente de Carlos. No comparte nada con los proyectos NDS ni bidding-market.

## Entornos y recursos

> **Producción apagada (2026-10-09, pedido de Carlos).** API, worker, admin, Postgres y Redis de
> producción están detenidos, con el auto-deploy desactivado y el backup de Postgres pausado. No se borró nada.
> Para volver: iniciar Postgres y Redis, luego API, worker y admin; reactivar auto-deploy y el backup.

| Recurso | QA (entorno `qa-env`, rama `qa`) | Producción (entorno `production`, rama `main`) |
| --- | --- | --- |
| Dominio | `kuulis-qa.top8.uk` | `kuulis-prod.top8.uk` |
| API (`/api`) | `kuulis-api-qa` · `rayxgnveijwwq86tquloc3r8` | `kuulis-api-production` · `f14idkxf8c209b1hghrunmhb` |
| Worker | `kuulis-worker-qa` · `i10vqipywxmdafk5sjaowzya` | `kuulis-worker-production` · `f3eiht6l1r439xxp3401u2ur` |
| Admin (`/`) | `kuulis-admin-qa` · `m37iqum9dy4n0o5281n0tvu5` | `kuulis-admin-production` · `ru2e54bw4mn4igqvvdmkgrys` |
| PostgreSQL 17 | `kuulis-postgres-qa` · `v12h71ber6ifhpgcugm6adth` | `kuulis-postgres-production` · `pvx2gkfbo18zcld9x55t0tgp` |
| Redis 7.4 | `kuulis-redis-qa` · `miq3v8c99isk848ps719a7dn` | `kuulis-redis-production` · `mgtsa16kwmktv0jl55belww8` |
| Backup Postgres | diario 03:00, 7 días | cada 6 h, 14 días |
| OSRM (rutas) | `kuulis-osrm`, compartido (ver `infra/README.md`) | el mismo |
| Photon (direcciones) | `kuulis-photon`, compartido | el mismo |

Cada app usa `base_directory` (`/api` o `/admin`), su `Dockerfile` y `watch_paths` (`api/**`, `admin/**`),
así que solo se redepliega lo que cambió. Auto-deploy activado: hacer push a `qa` o `main` despliega.

## Flujo de trabajo
1. Rama `feature/<algo>` desde `qa`.
2. PR hacia `qa`. GitHub Actions (`.github/workflows/ci.yml`) corre lint, tipos, tests, migraciones y
   escaneo de secretos de las apps que cambiaron; el check `ci` debe estar en verde para fusionar.
3. Merge → Coolify despliega QA.
4. Smoke E2E contra QA (ver abajo) y validación en `https://kuulis-qa.top8.uk`.
5. PR de `qa` a `main` → mismo CI → merge → Coolify despliega producción.

### Protección de ramas (GitHub → Settings → Branches)
En `qa` y `main`: exigir PR antes de fusionar y el check obligatorio **`ci`** en verde. En `main`, además,
solo PRs que vienen de `qa`. Así Coolify (que despliega en cada push) solo recibe código que pasó CI.

### Smoke E2E
`scripts/smoke_e2e.py` recorre el flujo completo contra un entorno: registra pasajero y motorizado,
sube documentos, aprueba, conecta, cotiza, pide, acepta, llega, inicia, completa y califica. Marca ambas
cuentas como **cuentas de prueba** (no cuentan en métricas ni en la portada) y las cierra al final. Necesita el
worker encendido y una cuenta con rol `admin`:

```
SMOKE_ADMIN_EMAIL=... SMOKE_ADMIN_PASSWORD=... uv run scripts/smoke_e2e.py --base-url https://kuulis-qa.top8.uk
```

Tarda unos segundos y termina con código 0 si todo pasó. No usarlo contra producción sin motivo.

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

### Configuración de Redis y Postgres
Se pone en Coolify (base de datos → Configuration), igual en QA y producción. Requiere reiniciar la base.
- **Redis** (`redis.conf` personalizado): `appendonly yes`, `appendfsync everysec`, `save 900 1`,
  `save 300 100`, `maxmemory 512mb`, `maxmemory-policy noeviction`. Ahí viven sesiones (refresh tokens),
  la cola de tareas y el despacho: no se pueden perder en un reinicio ni desalojar por memoria. Con 5000
  usuarios activos se espera menos de 100 MB. Límite del contenedor: 768 MB.
- **Postgres** (`postgresql.conf` personalizado; Coolify reemplaza el archivo entero, así que
  `listen_addresses = '*'` es obligatorio): `max_connections = 150`, `shared_buffers = 256MB`,
  `effective_cache_size = 1GB`, `work_mem = 8MB`, `maintenance_work_mem = 128MB`, `random_page_cost = 1.1`,
  `shared_preload_libraries = 'pg_stat_statements'`, `log_min_duration_statement = 500`,
  `timezone = 'UTC'`. La extensión la crea una migración. Límite del contenedor: 1,5 GB.
- Conexiones: API `WEB_CONCURRENCY` 4 × (pool + overflow) más el worker deben quedar bajo 150.

### Límites de recursos (VM de Coolify: 8 núcleos, 10 GB de RAM, 100 GB de disco)
| Contenedor | RAM máx. | Nota |
| --- | --- | --- |
| API | 1 GB | por entorno |
| Worker | 512 MB | por entorno |
| Admin | 256 MB | por entorno |
| Postgres / Redis | 1,5 GB / 768 MB | por entorno |
| OSRM / Photon | 1,5 GB / 1 GB | compartidos |
| Compilador de APK | 6 GB | solo mientras compila; no compilar a la vez que OSRM o Photon |

## Migraciones
La API ejecuta `alembic upgrade head` al arrancar (`RUN_MIGRATIONS=true`). Para crear una:
`cd api && uv run python manage.py makemigrations "mensaje"`, revisar el archivo y commitear.
Regla: migraciones compatibles hacia atrás (añadir columnas nullable, borrar en un segundo despliegue),
porque Coolify hace rolling update y la versión vieja convive unos segundos con el esquema nuevo.

## Health checks
- `GET /api/health/live` → proceso vivo (usado por Coolify), con `env` y `commit` (12 caracteres). Coolify
  pasa el commit con **"Include source commit in build"** activado en cada app.
- `GET /api/health/ready` → comprueba Postgres y Redis (503 si falla algo) y además OSRM y Photon en
  `providers` (`true`, `false`, o `null` si no están configurados). Si solo cae un proveedor responde 200 con
  `status: degraded`: la cotización usa la línea recta × 1,3 y la búsqueda no sugiere direcciones.
- En el admin, Configuración muestra al pie el commit de la API y del admin.

## Encender producción (lista)
Orden a seguir; no saltar pasos.
1. Postgres y Redis de producción con la configuración de arriba; iniciar ambos.
2. Variables obligatorias de la API y el worker (tabla de arriba) con `APP_ENV=production`,
   `OSRM_URL=http://<uuid de kuulis-osrm>:5000` y `PHOTON_URL=http://<uuid de kuulis-photon>:2322`.
3. Iniciar API, worker y admin; reactivar el auto-deploy.
4. `GET https://<dominio>/api/health/ready` → `status: ok`, base, Redis, OSRM y Photon en `true`, y el
   commit igual al último de `main`.
5. Entrar al admin con el primer admin y cambiar su contraseña.
6. Configuración inicial: área de servicio solo Caracas, tarifas, tramos de la cuota, tasas y Binance.
7. Reactivar el backup de Postgres (cada 6 h, con S3) y lanzar uno a mano.
8. Smoke E2E contra producción una sola vez (sus cuentas quedan marcadas como prueba y cerradas).
9. Para apagar otra vez: detener API, worker y admin, luego Postgres y Redis; pausar auto-deploy y backup.

## Cada despliegue (lista)
1. PR con el check `ci` en verde y migraciones compatibles hacia atrás.
2. Tras el merge, cuando Coolify termine, comprobar en `/api/health/live` que el `commit` es el nuevo. Si
   sale el anterior, Coolify dejó el contenedor viejo sirviendo junto al nuevo: Coolify → app → Restart.
3. `/api/health/ready` en `ok`.
4. Smoke E2E contra QA; en producción, una prueba manual corta desde el admin y la app.
5. Si algo falla: rollback (abajo).

## Contingencia del homelab
Todo corre en el servidor de casa de Carlos. Si se va la luz o internet, la app deja de responder hasta que
vuelva; no se pierden datos (Postgres y Redis persisten en disco).
- Aviso a los usuarios: página de estado externa (ver `docs/produccion/03-observabilidad-y-alertas.md`).
- Si la caída va a durar horas: VPS de 5–10 USD/mes (decidido: preparado pero apagado) con Coolify,
  restaurar el último backup de Postgres desde S3, desplegar las mismas apps y apuntar el DNS de Cloudflare
  al VPS. Las sesiones de Redis se pierden en ese caso (los usuarios vuelven a entrar).

## Rollback
Coolify → app → Deployments → elegir un despliegue anterior → Redeploy. Si una migración rompió algo,
crear una migración nueva que lo revierta (no editar migraciones ya aplicadas).

## Backups
Configurados en Coolify para cada Postgres. **Pendiente de Carlos:** activar "Save to S3" y elegir su S3
en cada backup (la API de Coolify 4.1.2 no expone el id del S3, ver `blockers.md`).
Restaurar: Coolify → base de datos → Backups → Restore, o `pg_restore` del dump descargado de S3.

## Compilador de APK (`kuulis-builder-qa`)
App de Coolify en QA que compila el APK en nuestro servidor, sin la cola de EAS Build (~25 min).
- Imagen: `mobile/builder/Dockerfile` (base `/mobile`), con JDK 17, Android SDK 36 y NDK 27.
- Al arrancar compila con `eas build --local --profile qa` (mismas credenciales y variables de EAS que en
  la nube) y sube el APK a S3 en `builds/qa/` (con fecha y hash) y como `builds/qa/kuulis-qa-qa-latest.apk`.
  El enlace firmado de 7 días queda en los logs del contenedor.
- `watch_paths`: solo archivos que cambian la parte nativa (`package.json`, `app.config.ts`, `eas.json`,
  `plugins/`, `builder/`). Para un APK con cambios solo de JS, redeplegar la app a mano.
- Variables: `EXPO_TOKEN`, `EXPO_OWNER` (las mismas de `kuulis-expo-qa`) y las `AWS_*` de la API de QA.
- Volumen persistente en `/cache` (caché de Gradle y npm): acelera las siguientes compilaciones y evita
  recompilar el mismo código si el contenedor se reinicia.
- Necesita unos 6 GB de RAM libres mientras compila; la imagen ocupa ~10 GB.

## Build de desarrollo (Android)
Perfil `qa-dev` de `eas.json`: APK de desarrollo (`uk.top8.kuulis.qa`) que carga el JS desde
`https://kuulis-expo.top8.uk`. Los cambios solo de JS llegan al cerrar y abrir la app, sin APK nuevo. Hace
falta un build nuevo solo cuando cambia algo nativo (dependencias nativas, plugins, permisos).
