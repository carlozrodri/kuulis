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
| Admin (`admin.top8.uk` en QA) | `kuulis-admin-qa` · `m37iqum9dy4n0o5281n0tvu5` | `kuulis-admin-production` · `ru2e54bw4mn4igqvvdmkgrys` |
| Web pública | `Kuulis web` · `p4lpainpky5a5tf5oe9ggthm` en `kuulis.top8.uk` (y `www.`) | por crear |
| PostgreSQL 17 | `kuulis-postgres-qa` · `v12h71ber6ifhpgcugm6adth` | `kuulis-postgres-production` · `pvx2gkfbo18zcld9x55t0tgp` |
| Redis 7.4 | `kuulis-redis-qa` · `miq3v8c99isk848ps719a7dn` | `kuulis-redis-production` · `mgtsa16kwmktv0jl55belww8` |
| Backup Postgres | diario 03:00, 7 días | cada 6 h, 14 días |
| OSRM (rutas) | `kuulis-osrm` · `nqbbvoaqqvzkthxeq6vts7zc`, compartido (ver `infra/README.md`) | el mismo |
| Photon (direcciones) | `kuulis-photon` · `owcfbizidzhgftvwksyxqkis`, compartido | el mismo |

Cada app usa `base_directory` (`/api`, `/admin` o `/web`), su `Dockerfile` y `watch_paths` (`api/**`, `admin/**`, `web/**`),
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
- Traefik enruta `/api/*` a la API.
- En QA el admin sigue en el dominio principal (`kuulis-qa.top8.uk`) y la web pública vive en
  `kuulis.top8.uk`. Ese dominio también apunta a la API en `/api`, así la web la llama en su mismo origen.
- El admin de QA vive en `admin.top8.uk` (un solo nivel, lo cubre el certificado `*.top8.uk`); el de
  producción está por decidir. La app API tiene también el dominio `https://admin.top8.uk/api`, así el admin
  sigue llamando a la API en su mismo origen, sin CORS.

### App web en Coolify
Crear `kuulis-web-<entorno>` desde el UI: repositorio `carlozrodri/kuulis`, rama `qa` o `main`, build pack
Dockerfile, `base_directory` `/web`, puerto 3000, `watch_paths` `web/**`, dominio de la web.
Variables: `NUXT_PUBLIC_APP_ENV` (`qa`/`production`), `NUXT_PUBLIC_SITE_URL` (`https://<dominio>`),
`NUXT_API_INTERNAL` (`http://<contenedor de la API>:8000/api/v1`, opcional) y `NUXT_PUBLIC_SUPPORT_EMAIL`.

### Web pública en Cloudflare (producción)
En producción la web pública (`web/`) corre en Cloudflare Workers en `kuulis.com`: gratis, cerca de Venezuela y
arriba aunque el homelab se caiga. La API y el admin siguen en Coolify. La web llama a la API en su propio host
(`api.kuulis.com`): el navegador con CORS, el render del servidor directo. Así la API ve la IP real de cada
visitante (los límites de uso dependen de ella); por eso **no** se reenvía `/api` a través del Worker.

Una vez, en el panel de Cloudflare (el dominio ya está en la cuenta):
1. **Workers & Pages → Create → Import a repository** → `carlozrodri/kuulis`. Nombre `kuulis`, rama de
   producción `main` (mientras producción esté apagada, `qa`; ver abajo).
2. Build: directorio raíz `web`, comando de build `pnpm install --frozen-lockfile && pnpm build:cloudflare`,
   comando de deploy `npx wrangler deploy` (lee `web/wrangler.jsonc`).
3. **Variables de build**: `NUXT_PUBLIC_API_BASE` (la CSP se escribe al compilar) y `PNPM_VERSION=10.18.0`.
4. **Variables del Worker** (Settings → Variables): `NUXT_PUBLIC_APP_ENV=production`,
   `NUXT_PUBLIC_SITE_URL=https://kuulis.com`, `NUXT_PUBLIC_API_BASE` y `NUXT_API_INTERNAL` (las dos
   `https://api.kuulis.com/api/v1`), `NUXT_PUBLIC_SUPPORT_EMAIL`.
5. **Settings → Domains & Routes → Custom domain**: `kuulis.com` y `www.kuulis.com`. Si el DNS tiene un registro
   para `kuulis.com` o `www` que apunta al homelab, se borra antes; el comodín `*` de NPM sigue para el resto.
6. La API acepta la web por CORS (`CORS_ORIGINS` de producción ya incluye `https://kuulis.com` y `www`).

API en `api.kuulis.com`: proxy host en NPM con Websockets Support hacia Traefik, y en Coolify el dominio
`https://api.kuulis.com/api` en la app de la API. Dejar ese registro en **solo DNS** (nube gris): con el proxy
de Cloudflare la API vería IPs de Cloudflare hasta que NPM restaure `CF-Connecting-IP`.

**Mientras producción esté apagada** (para tener `kuulis.com` ya, por ejemplo para Google Play): rama `qa` y las
dos variables de la API en `https://kuulis.top8.uk/api/v1` (también la de build), y añadir
`https://kuulis.com,https://www.kuulis.com` a `CORS_ORIGINS` de `kuulis-api-qa` en Coolify. Muestra los datos y
los textos legales de QA. Al encender producción se cambian rama y variables y se vuelve a desplegar.

Probar en local: `pnpm build:cloudflare` y `npx wrangler dev --var NUXT_API_INTERNAL:<api> --var
NUXT_PUBLIC_API_BASE:<api>` (con `NUXT_PUBLIC_API_BASE=<api>` también en el build).

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
| `SENTRY_ENABLED`, `SENTRY_DSN` | ✓ | ✓ | errores a GlitchTip (ver Monitoreo) |
| `ALERT_TELEGRAM_BOT_TOKEN` | ✓ | ✓ | bot de alertas; el chat se toma del primer mensaje privado al bot |
| `ALERT_TELEGRAM_CHAT_ID` | opcional | opcional | fija el chat de alertas |
| `ALERT_EMAILS` | ✓ | ✓ | resumen diario 08:00 (y alertas si no hay Telegram), separados por coma |
| `METRICS_TOKEN` | ✓ | | token de `/api/metrics` (sin él, 404) |
| `BACKUP_ENABLED`, `BACKUP_S3_*`, `BACKUP_PASSPHRASE` | | ✓ | backups a Cloudflare R2 (ver Backups) |
| `ADMIN_TOTP_REQUIRED` | opcional | | `true` por defecto: el equipo entra al admin con 2FA (ver Acceso del equipo) |
| `FORWARDED_ALLOW_IPS` | opcional | | redes de los proxies en las que se confía para `X-Forwarded-For` (por defecto las privadas; ver Límites de uso) |
| `NUXT_PUBLIC_APP_ENV`, `NUXT_PUBLIC_API_BASE` | | | solo admin |
| `FRONTEND_URL`, `ADMIN_URL` | opcional | opcional | web pública (enlaces de los emails) y admin (invitaciones); por defecto los dominios de cada entorno |

La contraseña del primer admin está en la variable `FIRST_SUPERUSER_PASSWORD` de la app API de cada entorno
en Coolify. Conviene cambiarla desde el panel (Mi perfil) tras el primer login.

### Inventario de secretos
Solo nombres y dónde viven; los valores están en Coolify (o en la cuenta del servicio) y nunca en el repo, el
chat ni los logs. Revisado el 2026-10-11 comparando huellas, sin leer valores.

| Secreto | Dónde | QA y prod | Última rotación | Al rotarlo |
| --- | --- | --- | --- | --- |
| `SECRET_KEY` | API y worker | distinta (verificado) | alta del entorno (2026-10) | cierra todas las sesiones y anula el 2FA guardado: en la misma ventana, `DELETE FROM user_totp;` y el equipo vuelve a dar de alta su app |
| `DATABASE_URL` (clave de Postgres) | API y worker | distinta | alta | cambiarla en la base y en ambas apps a la vez |
| `REDIS_URL` | API y worker | distinta | alta | igual que la anterior |
| `AWS_ACCESS_KEY_ID` / `AWS_SECRET_ACCESS_KEY` | API y worker | **la misma** | alta | ver hallazgo M3 en `docs/produccion/revision-seguridad.md`: una clave por entorno limitada a su prefijo |
| `RESEND_API_KEY` | API y worker | la misma | alta | crear la nueva en Resend, cambiarla y borrar la vieja |
| `BACKUP_S3_*` (R2) | worker | por entorno | 2026-10-11 (alta en QA) | token de R2 con permiso solo de escritura y lectura en su bucket |
| `BACKUP_PASSPHRASE` | worker + gestor de contraseñas de Carlos | por entorno | 2026-10-11 | **guardar la anterior**: los backups viejos solo se abren con ella |
| `FIRST_SUPERUSER_PASSWORD` | API | distinta | alta | cambiar la contraseña desde Mi perfil; la variable solo sirve para el primer arranque |
| `BINANCE_API_KEY` / `BINANCE_API_SECRET` | API y worker (solo QA por ahora) | — | alta | de solo lectura (confirmado por Carlos el 2026-10-11) |
| `METRICS_TOKEN` | API | por entorno | aún sin poner | cambiarlo aquí y en el scraper |
| `UPDATES_SIGNING_KEY` | API + gestor de contraseñas de Carlos | por entorno (prod aún sin crear) | 2026-10-12 (alta en QA) | exige APK nuevo con el certificado nuevo (ver «Clave de firma de las OTA») |
| `ALERT_TELEGRAM_BOT_TOKEN` | API y worker | el mismo bot | 2026-10-11 (alta en QA) | `/revoke` en BotFather |
| `SENTRY_DSN` | API y worker | por entorno | pendiente (GlitchTip listo el 2026-10-11) | nuevo DSN en GlitchTip |
| Token de Expo (EAS) | cuenta de Expo de Carlos, `EXPO_ACCESS_TOKEN` | — | **pendiente**: se pegó en un chat; Carlos lo rota | revocarlo en expo.dev y crear otro |

Reglas: un secreto por entorno (QA nunca debe abrir datos de producción), rotar al salir alguien del
equipo o ante cualquier sospecha, y anotar aquí la fecha de cada rotación.

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

## Acceso del equipo (2FA)
- Todo staff y admin entra al panel con contraseña y un código de su app de autenticación (Google
  Authenticator, Aegis). La primera vez el panel muestra un QR para configurarla y 10 códigos de recuperación
  de un solo uso.
- Las sesiones abiertas desde la app móvil con una cuenta de staff no tienen permisos de admin.
- Cambiar roles, crear usuarios, ajustar saldos y reiniciar el 2FA de alguien piden un código nuevo (vale
  10 min en esa sesión).
- Si alguien pierde el teléfono y sus códigos: un admin entra a su ficha → "Reiniciar 2FA"; lo configura de
  nuevo al entrar. Si el único admin pierde ambos, se borra su fila en `user_totp` desde la base.
- Las claves de 2FA se guardan cifradas con una clave derivada de `SECRET_KEY`: si se rota `SECRET_KEY`,
  todo el equipo configura su autenticador de nuevo (borrar las filas de `user_totp`).
- Cada usuario ve y cierra sus sesiones (app: Perfil → Sesiones activas; admin: Mi perfil). Cerrar una
  sesión corta también su token de acceso al instante.
- Permisos (doc 06): cada staff tiene un rol del equipo (Soporte, Verificador, Finanzas, Operaciones o uno
  nuevo) y solo ve y usa lo que ese rol permite; la API responde 403 `permission_denied` con
  `details.permission`. Un staff sin rol no puede usar el admin. Los admins pueden todo, y configuración,
  tramos, equipo, roles y auditoría son solo suyos.
- Altas: Equipo → Invitar. Llega un correo con un enlace de 3 días (`/accept-invite`) para crear la contraseña;
  al entrar configura el 2FA. Cambiar el rol o desactivar a alguien cierra sus sesiones.

## Límites de uso
- La IP del cliente la resuelve uvicorn desde `X-Forwarded-For` confiando solo en las redes privadas (NPM y
  Traefik): toma la última dirección que no es de un proxy, así que una IP inventada por el cliente no cuenta.
  Cada línea del log de peticiones trae `ip`; si alguna vez sale una IP privada para todos, el proxy está
  borrando la cabecera y hay que revisar NPM o Traefik.
- Traefik de Coolify (servidor `localhost`) confía en NPM: su configuración lleva
  `--entrypoints.http.forwardedHeaders.trustedIPs=192.168.0.148/32` y lo mismo para `https` (puesto el
  2026-10-11; si se regenera la configuración del proxy en Coolify hay que volver a ponerlo). Sin eso Traefik
  reemplaza la cabecera y la API ve a todos los anónimos con la IP de NPM.
- Con sesión: límite por usuario (120/min general). Sin sesión: por IP (120/min general, 20/min en login,
  registro y restablecer contraseña).
- Límites propios: cotizar 30/min, pedir viaje 6/min, mensajes del chat 30/min, reportes 10/h, subir archivos
  30/h, transferencias 10/h, correo de restablecer contraseña 1/min por dirección.
- Login con contraseña: tras 5 fallos seguidos con el mismo correo, bloqueo de 1, 5 y 15 min (los siguientes
  en 24 h) y un correo al dueño en el primero. Respuesta `429 login_locked` con `retry_after`.
- WebSocket: mensajes de hasta 4 KB y 10 por segundo; la conexión dura lo que el token de acceso (la app lo
  renueva al recibir `auth.expiring`).
- Código del 2FA: además de 5 intentos por reto, 10 códigos errados por cuenta en 15 min la bloquean hasta que
  pase la ventana (`429 login_locked`), aunque se pida un reto nuevo.

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

## Monitoreo y alertas
- Cada proceso de fondo del worker (despacho, tasas, Binance, cuotas, borrado de cuentas) deja un latido en
  Redis. Cada minuto, un proceso (API o worker, con lock en Redis) revisa servicios, latidos, colas, errores
  500, tasas vencidas, disco y viajes sin motorizado, y avisa por Telegram. No repite la misma alerta antes de
  30 min y avisa cuando se resuelve. Corre también en la API, así que un worker detenido se detecta.
- Admin → **Sistema** muestra todo eso en vivo; la portada avisa si hay alertas abiertas.
- `GET /api/metrics` (Prometheus) con `Authorization: Bearer <METRICS_TOKEN>`.
- Los logs JSON llevan `request_id`, `user_id` y `ride_id` cuando aplican.
- Monitor externo (fuera del homelab): UptimeRobot sobre `/api/health/live` de QA (puesto por Carlos el
  2026-10-11).
- Telegram: bot `@Kuulis_bot`; el token está en API y worker de QA. El chat de alertas es el último chat privado
  que le escribió al bot (o `ALERT_TELEGRAM_CHAT_ID`).
- Errores: GlitchTip propio en `https://glitchtip.top8.uk` (servicio `GlitchTip` · `ltics19o8wipo8ri1sxrkpog`,
  servidor `localhost`, entorno QA). Su dominio en Coolify lleva el puerto del contenedor
  (`https://glitchtip.top8.uk:8000`); sin el puerto Traefik responde 502. El DSN del proyecto va en `SENTRY_DSN`.
- Prueba automática completa (`scripts/smoke_e2e.py`): la cuenta `SMOKE_ADMIN_*` (marcada como de prueba) tiene
  su correo, contraseña y clave 2FA guardados como variables de la API de QA en Coolify; no se usan en la app.

## Encender producción (lista)
Orden a seguir; no saltar pasos.
1. Postgres y Redis de producción con la configuración de arriba; iniciar ambos.
2. Variables obligatorias de la API y el worker (tabla de arriba) con `APP_ENV=production`,
   `OSRM_URL=http://kuulis-osrm:5000` y `PHOTON_URL=http://kuulis-photon:2322` (alias de red, ver
   `infra/README.md`).
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
  restaurar el último backup de Postgres desde R2 (ver Backups), desplegar las mismas apps y apuntar el DNS de Cloudflare
  al VPS. Las sesiones de Redis se pierden en ese caso (los usuarios vuelven a entrar).

## Rollback
Coolify → app → Deployments → elegir un despliegue anterior → Redeploy. Si una migración rompió algo,
crear una migración nueva que lo revierta (no editar migraciones ya aplicadas).

## Backups
Los hace el worker (`api/apps/backups`), no Coolify, y van a un bucket de **Cloudflare R2** fuera del homelab.
Todo se cifra con `openssl enc -aes-256-cbc -pbkdf2` y `BACKUP_PASSPHRASE`, bajo `<APP_ENV>/` en el bucket:

| Qué | Cuándo | Dónde |
| --- | --- | --- |
| Dump de Postgres (`pg_dump -Fc`) | cada `BACKUP_EVERY_MINUTES` (15) | `postgres/recent/AAAA/MM/DD/…dump.enc` |
| Primer dump del día (copia) | diario | `postgres/daily/AAAA/MM/…dump.enc` |
| Libro contable en CSV (billeteras, movimientos, recargas, cobros de cuota) | diario, 03:00 Caracas | `ledger/AAAA/MM/AAAA-MM-DD.tar.gz.enc` |
| Copia de documentos y avatares del S3 de la app | diario, 03:00 Caracas | `files/…enc` |
| Prueba de restauración (base temporal, cuenta filas, la borra) | domingos 04:00 Caracas | — |

El estado se ve en el admin (Sistema → Backups) y hay alerta si no hay dump en 35 min, si falla un trabajo o
si falla la prueba de restauración. Un trabajo diario o semanal que falla se reintenta a los 15 min (no al día
siguiente), así la alerta se cierra sola si fue un corte pasajero de R2. La app **nunca borra dumps ni el libro contable**; solo borra en `files/`
la copia de un archivo borrado en la app (borrado de cuentas).

### Configurar (una vez por entorno)
1. Cloudflare → R2 → crear el bucket `kuulis-backups`.
2. Bucket → Settings → **Object lifecycle rules** (retención), una regla por prefijo y entorno (`qa/`,
   `production/`; R2 no acepta comodines):
   - `<entorno>/postgres/recent/`: borrar a los 2 días;
   - `<entorno>/postgres/daily/`: borrar a los 14 días (producción) o 7 (QA);
   - `<entorno>/ledger/`: borrar a los 365 días.
3. Bucket → Settings → **Bucket lock rules** con los mismos prefijos y plazos, para que nadie los pueda borrar
   antes (ni con las credenciales de la app).
4. R2 → Manage API tokens → token **Object Read & Write** solo para ese bucket.
5. En el **worker** del entorno: `BACKUP_ENABLED=true`, `BACKUP_S3_ENDPOINT=https://<account_id>.r2.cloudflarestorage.com`,
   `BACKUP_S3_BUCKET=kuulis-backups`, `BACKUP_S3_ACCESS_KEY_ID`, `BACKUP_S3_SECRET_ACCESS_KEY` y
   `BACKUP_PASSPHRASE` (larga y aleatoria, distinta por entorno). **Guardar la frase también fuera de Coolify**
   (gestor de contraseñas): sin ella los backups no se pueden leer.
6. Redeploy del worker y revisar Sistema → Backups a los pocos minutos.

### Restaurar Postgres
Necesita `openssl`, `pg_restore` 17 y la frase (`export BACKUP_PASSPHRASE=…`, sin pegarla en el historial).
1. Descargar el dump elegido de R2 (panel de Cloudflare o `aws s3 cp --endpoint-url …`). Para volver a un
   momento concreto, el último dump anterior a ese momento (hay uno cada 15 min de los últimos 2 días).
2. Descifrar: `openssl enc -d -aes-256-cbc -pbkdf2 -pass env:BACKUP_PASSPHRASE -in X.dump.enc -out X.dump`
3. Detener el worker y la API en Coolify (que nadie escriba durante la restauración).
4. Restaurar:
   - a una base nueva para recuperar filas sueltas: `createdb kuulis_rescate` y
     `pg_restore --no-owner --no-acl -d "$URL/kuulis_rescate" X.dump`, y copiar lo necesario;
   - o encima de la base: `pg_restore --no-owner --no-acl --clean --if-exists -d "$DATABASE_URL" X.dump`.
5. Encender API y worker; revisar `/api/health/ready` y el resumen del admin.

La misma herramienta descifra el libro contable (`tar xzf` después) y los archivos.

### Desastre (servidor perdido)
1. Coolify en otro servidor (VPS de contingencia), con Postgres 16+, Redis y las apps de este repo (mismas
   variables, ver arriba).
2. Restaurar Postgres desde R2 como arriba y subir de nuevo `files/` descifrado al S3 nuevo si el de la app
   también se perdió.
3. Apuntar el DNS de Cloudflare al servidor nuevo.

Redis no se respalda: tiene AOF (02) y lo que se perdería se rehace solo. Las sesiones (los usuarios vuelven
a entrar), las ubicaciones en vivo (los motorizados las reenvían en segundos), los turnos de despacho
(`reconcile` del despacho reprograma las ofertas de viajes en búsqueda) y los contadores de monitoreo.

## Compilador de APK (`kuulis-builder-qa`)
App de Coolify en QA que compila el APK en nuestro servidor, sin la cola de EAS Build (~25 min).
- Imagen: `mobile/builder/Dockerfile` (base `/mobile`), con JDK 17, Android SDK 37 y NDK 27.
- Al arrancar compila con `eas build --local --profile qa` (mismas credenciales y variables de EAS que en
  la nube) y sube el APK a S3 en `builds/qa/` (con fecha y hash) y como `builds/qa/kuulis-qa-qa-latest.apk`.
  El enlace firmado de 7 días queda en los logs del contenedor.
- Antes de compilar calcula el **runtime** de `expo-updates` (huella del código nativo: dependencias nativas,
  plugins, `app.config.ts`, `eas.json`). Si ya hay un APK en S3 con ese runtime, no compila: exporta una
  **actualización de JS (OTA)** en un par de minutos y la deja como candidata (ver «Publicar una
  actualización OTA»). Si el runtime es nuevo, compila el APK. `FORCE_APK=1` fuerza el APK.
- `watch_paths`: `mobile/**` para que cada cambio de la app genere su OTA o su APK.
- Variables: `EXPO_TOKEN`, `EXPO_OWNER` (las mismas de `kuulis-expo-qa`) y las `AWS_*` de la API de QA.
- Volumen persistente en `/cache` (caché de Gradle y npm): acelera las siguientes compilaciones y evita
  recompilar el mismo código si el contenedor se reinicia.
- Compila solo para teléfonos (ARM: `armeabi-v7a`, `arm64-v8a`), no para emuladores, y con 4 hilos de Gradle
  como máximo. Necesita unos 6 GB de RAM libres mientras compila; la imagen ocupa ~10 GB. Si se queda quieto en
  el mismo paso de Gradle mucho rato, casi siempre es falta de memoria en la VM.
- Junto a cada APK sube `<nombre>.json` con versión, build (`versionCode`), tamaño, SHA-256, MD5 y runtime.
  El perfil `qa` sube el build en cada compilación (`autoIncrement`, numerado por EAS).

## Publicar una versión del APK (doc 09)
1. El compilador deja el APK en `builds/<entorno>/` (ver arriba).
2. En el admin, **Versiones → Compilaciones disponibles → Publicar**: canal, notas y si es **obligatoria**.
   Desde ese momento las apps del canal ven «Hay una versión nueva» y la página Descargar de la web ofrece
   ese APK.
3. Obligatoria = versión mínima: las builds anteriores no pueden pedir ni aceptar viajes ni conectarse
   (426 `app_update_required`) hasta actualizar. Usarla solo cuando una versión vieja ya no funciona bien.
4. Para revertir, **Retirar** la versión: vuelve a ofrecerse la anterior (y deja de bloquear si era
   obligatoria). Ojo: Android no deja instalar una build menor encima de una mayor, así que quien ya
   actualizó se queda con la retirada hasta que salga una nueva.

## Publicar una actualización OTA (doc 09)
Las OTA cambian solo el JS y las imágenes; llegan a las apps instaladas sin descargar un APK.
1. El compilador sube cada archivo una vez a `updates/<entorno>/assets/<sha256>` y la candidata a
   `updates/<entorno>/candidates/`.
2. En el admin, **Versiones → Actualizaciones de JS → Publicar**: canal, porcentaje y mensaje. La API
   (`GET /api/v1/updates/manifest`, protocolo Expo Updates v1) entrega a cada app la actualización más nueva
   de su canal y su runtime, **firmada**; la app la descarga en segundo plano al abrirse y la aplica la
   siguiente vez que se abre. Nunca reinicia sola (ni en un viaje ni con el motorizado conectado).
3. **Porcentaje**: elige una parte estable de los teléfonos (por el id de instalación que manda la app); los
   demás siguen con la anterior. Pausar = 0 %, luego ampliar a 100 %.
4. **Revertir**: retira la actualización y publica una copia más nueva de la anterior (las apps se quedan
   siempre con la más nueva que descargaron); si no había anterior, las apps vuelven al código del APK.
5. Solo reciben la OTA las apps con el mismo runtime. Las instaladas antes de la parte 2 (sin `expo-updates`)
   necesitan el APK nuevo.

### Clave de firma de las OTA
- Certificado (público) en `mobile/certs/updates-<entorno>.pem`; va dentro del APK. Sin certificado para el
  entorno la app compila con las OTA apagadas (así está producción hasta crear su clave).
- Clave privada en la variable `UPDATES_SIGNING_KEY` de la API (PEM; se aceptan los saltos de línea como
  `\n`) y copia en el gestor de contraseñas de Carlos. Sin ella el manifiesto responde 503 y las apps se
  quedan con lo que tienen.
- Crear la de un entorno: `npx expo-updates codesigning:generate --key-output-directory <fuera del repo>
  --certificate-output-directory certs --certificate-validity-duration-years 20 --certificate-common-name
  "Kuulis <entorno> updates"` y renombrar `certs/certificate.pem` a `certs/updates-<entorno>.pem`.
- Cambiar la clave obliga a un APK nuevo (el certificado viaja dentro): las apps viejas rechazan lo firmado
  con la clave nueva. Si se filtra, se cambia igual y se publica un APK obligatorio.

## Firma de producción (pendiente de Carlos)
El perfil `production` de `eas.json` genera un APK firmado con el keystore de producción que guarda EAS.
Antes de la primera compilación de producción: crearlo (`eas credentials -p android`, perfil production),
descargar una copia y guardarla con sus contraseñas en el gestor de contraseñas de Carlos. Si se pierde, los
teléfonos no aceptan actualizaciones y todos tendrían que desinstalar e instalar de nuevo.

## Build de desarrollo (Android)
Perfil `qa-dev` de `eas.json`: APK de desarrollo (`uk.top8.kuulis.qa`) que carga el JS desde
`https://kuulis-expo.top8.uk`. Los cambios solo de JS llegan al cerrar y abrir la app, sin APK nuevo. Hace
falta un build nuevo solo cuando cambia algo nativo (dependencias nativas, plugins, permisos).
