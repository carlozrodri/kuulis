# Convenciones

## Git
- Ramas: `main` (prod), `qa` (QA), `feature/<tema>`, `fix/<tema>`.
- Commits en imperativo y en inglés, pequeños y con un solo propósito.
- Nunca subir secretos: `.env*` está ignorado; las variables viven en Coolify.

## API
- Una carpeta por dominio en `api/apps/`. Routers finos, lógica en `services.py`.
- Errores: lanzar subclases de `AppError` con un `code` estable en snake_case; los clientes lo traducen.
- Todo lo lento (emails, push, integraciones) va a `tasks.py` y se encola con `.kiq()`.
- Endpoints versionados bajo `/api/v1`. Cambios incompatibles → `/api/v2`.
- Tests junto a cada app (`apps/<app>/tests/`), contra Postgres y Redis reales.
- Lint y formato: `uv run ruff check . && uv run ruff format .`

## Admin
- Páginas en `admin/app/pages`, peticiones con `useApi()`, errores con `useApiError()`.
- Roles por página: `definePageMeta({ roles: ['admin'] })`.
- Textos siempre en `i18n/locales/{es,en}.json`.

## Mobile
- Instalar dependencias con `npx expo install` (versiones compatibles con el SDK).
- Rutas en `src/app`, el resto fuera. Textos en `src/i18n/locales`.
- No crear ni editar `ios/` ni `android/` a mano (Continuous Native Generation).

## i18n
Español es el idioma por defecto y de respaldo. Toda clave nueva se añade en `es` y `en` (hay tests que
comprueban que ambos archivos tienen las mismas claves en mobile).
