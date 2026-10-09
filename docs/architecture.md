# Arquitectura

```
                 Internet
                    │
         Cloudflare DNS (top8.uk)
                    │
        Nginx Proxy Manager (homelab)   ← TLS público, Carlos crea los hosts
                    │
           Traefik de Coolify  ─────────────────────────────┐
     ┌──────────────┴──────────────┐                          │
     │ https://<host>/             │ https://<host>/api/*     │
     ▼                             ▼                          │
 kuulis-admin (Nuxt, :3000)   kuulis-api (FastAPI, :8000)    │
                               │   gunicorn × N UvicornWorker │
                               │   REST /api/v1 + WS /api/v1/ws
                               ▼                              │
                     ┌──────── Redis ────────┐                │
                     │ cache · rate limit    │                │
                     │ refresh tokens        │                │
                     │ pub/sub WebSockets    │                │
                     │ cola de tareas        │◄── kuulis-worker (Taskiq)
                     └───────────────────────┘        │
                               │                      │
                          PostgreSQL 17  ◄────────────┘
                               │
                     Backups → S3 (s3.top8.uk)

 App móvil (Expo) ──► https://<host>/api/v1  (REST + WebSocket)
                 └──► Expo Push Service ──► APNs / FCM   (enviado por el worker)
 Archivos: la app pide URL prefirmada a la API y sube directo a S3.
```

`<host>` es `kuulis-qa.top8.uk` (rama `qa`) o `kuulis-prod.top8.uk` (rama `main`).

## Componentes

### API (`api/`)
- FastAPI organizado como un proyecto Django: `kuulis/` es el "proyecto" (settings por entorno, `asgi.py`,
  `urls.py`, `models.py`, `tasks.py`) y `apps/<app>/` contiene `models.py`, `schemas.py`, `services.py`,
  `router.py`, `dependencies.py`, `tasks.py` y `tests/`.
- `manage.py` replica los comandos de Django: `runserver`, `migrate`, `makemigrations`, `createsuperuser`,
  `worker`, `scheduler`, `shell`.
- SQLAlchemy 2 async + asyncpg con pool de conexiones; Alembic para migraciones (se aplican al arrancar el
  contenedor de la API, con un advisory lock para que dos contenedores no migren a la vez).
- Auth: JWT de acceso (15 min) + refresh token rotativo (30 días) guardado en Redis, con detección de
  reutilización (si alguien reusa un refresh ya rotado se revocan todas las sesiones del usuario).
  Roles: `user`, `staff`, `admin`. Login social preparado (tabla `social_accounts`, endpoint 501).
- Errores con formato estable `{"error": {"code", "message", "details"}}`; los clientes traducen `code`.
- Rate limiting en Redis (compartido entre workers y contenedores).
- WebSockets: cada worker guarda sus sockets y Redis pub/sub reparte los eventos, así funciona con varios
  procesos y varios contenedores.
- Push: tabla `devices` con tokens de Expo; el worker envía en lotes de 100 y desactiva tokens inválidos.
- Archivos: URLs prefirmadas de S3 (la API nunca recibe los bytes). Prefijo por entorno (`qa/`, `production/`).
- Email: Resend, siempre desde el worker (registro, verificación, reset de contraseña) en es/en.
- Sentry instalado y apagado (`SENTRY_ENABLED=false`).

### Worker (`api/`, `PROCESS_TYPE=worker`)
Misma imagen Docker que la API. Taskiq sobre Redis Streams (con ack, así no se pierden tareas si un worker
muere). Hoy procesa: emails y push/broadcast de notificaciones.

### Admin (`admin/`)
Nuxt 4 + Nuxt UI, SPA servida por Nitro. Login solo para `staff`/`admin`
(`/auth/admin/login`). Mismo dominio que la API, sin CORS. Tokens en cookies `SameSite=Strict; Secure`.
Pantallas: panel (métricas de usuarios), usuarios (búsqueda, filtros, edición de rol/estado solo admin),
envío de notificaciones (a todos, por rol o a un usuario), perfil.

### Mobile (`mobile/`)
Expo SDK 57 + Expo Router + TypeScript. Tokens en Keychain/Keystore (`expo-secure-store`), refresh
transparente, i18n con detección del idioma del teléfono, push con `expo-notifications`, WebSocket con
reconexión exponencial que se pausa en background. `APP_ENV` elige API y bundle id (QA y prod conviven).

## Modelo de datos actual

| Tabla | Para qué |
| --- | --- |
| `users` | email único, contraseña Argon2, rol, idioma, activo/verificado, último login |
| `social_accounts` | futuro login con Google/Apple |
| `devices` | tokens push por usuario y plataforma |
| `notifications` | bandeja in-app (leído/no leído) |
