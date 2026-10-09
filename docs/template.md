# Plantilla base (semilla de otros productos)

El tag **`template-v1.0.0`** marca el estado del monorepo que sirve como plantilla para crear otras
aplicaciones. Es la infraestructura completa sin lógica de producto: auth con roles, usuarios,
notificaciones (push, bandeja y WebSocket), archivos en S3, emails, tareas en background, admin, app móvil y
despliegue en Coolify con QA y producción. Todo lo que se haga en Kuulis después de este tag ya es producto.

Para ver la plantilla: `git checkout template-v1.0.0`.

## Qué es genérico (se reutiliza tal cual)

- `api/kuulis/core/`: base de datos, Redis, seguridad JWT, caché, rate limit, storage S3, email, logging, errores.
- `api/apps/`: `auth`, `users`, `notifications`, `realtime`, `files` y `health`.
- `api/docker/`, `api/Dockerfile` y `manage.py`.
- `admin/`: layout, login por rol, usuarios, notificaciones y perfil.
- `mobile/src/lib`, `providers`, `hooks` y `components`: cliente API con refresh, sesión segura, push, WebSocket e i18n.
- `mobile/Dockerfile.expo`: servidor Expo para Expo Go.
- `docs/`: arquitectura, decisiones, escalabilidad, convenciones y runbook de despliegue.

## Qué hay que cambiar en cada producto nuevo

| Dónde | Qué |
| --- | --- |
| Nombre del paquete `api/kuulis/` | Renombrar (o dejarlo; es solo el nombre interno del "proyecto") |
| `api/kuulis/settings/*.py` | `APP_NAME`, dominios de QA y producción, `EMAIL_FROM` |
| `admin/nuxt.config.ts`, `admin/app/layouts/*` | Título, colores (`app.config.ts`) y nombre visible |
| `mobile/app.config.ts` | `name`, `slug`, `scheme`, `bundleIdentifier`/`package`, URLs de API, `eas.projectId` (nuevo proyecto en expo.dev), iconos en `mobile/assets` |
| `mobile/Dockerfile.expo` | `EXPO_PACKAGER_PROXY_URL` (dominio del servidor Expo) |
| Traducciones (`i18n/locales`) | Textos de bienvenida y del producto |
| Coolify | Proyecto nuevo con sus propios Postgres, Redis, apps y variables (ver `deployment.md`) |
| `docs/roadmap.md`, `pending.md`, `blockers.md` | Empezar de cero para el producto nuevo |

## Cómo empezar un producto nuevo

1. Crear en GitHub un repo privado vacío, por ejemplo `carlozrodri/<producto>`.
2. Copiar la plantilla sin historial:
   ```bash
   git clone --branch template-v1.0.0 --depth 1 https://github.com/carlozrodri/kuulis <producto>
   cd <producto> && rm -rf .git && git init -b main
   git remote add origin https://github.com/carlozrodri/<producto>
   ```
3. Aplicar los cambios de la tabla de arriba, generar una nueva migración inicial si cambian los modelos
   (`uv run python manage.py makemigrations "initial"`) y hacer commit y push a `main` y `qa`.
4. En Coolify, crear el proyecto con sus entornos, bases de datos y apps siguiendo `docs/deployment.md`.
5. Crear los dominios en Nginx Proxy Manager con Websockets activado.

Las mejoras de infraestructura que se hagan en Kuulis y sirvan para todos se pueden portar a la plantilla
con un nuevo tag (`template-v1.1.0`, etc.).
