# 01 · CI y calidad del código

**Prioridad:** P0 · **Área:** Infra · **Depende de:** nada

## Objetivo
Que ningún cambio llegue a QA o a producción si rompe los tests, el lint o el tipado, y que exista una prueba
de punta a punta automática del flujo principal (registrarse, aprobar motorizado, pedir y completar un viaje).

## Estado actual
- No existe `.github/`: Coolify despliega en cada push a `qa` o `main` aunque los tests fallen.
- La API tiene ~20 archivos de tests (Postgres y Redis reales), ruff y formato.
- Admin tiene `lint`, `typecheck` y `test` (vitest) en `package.json`; mobile tiene `lint`, `typecheck`, `test`
  (jest, 9 archivos, sobre todo lógica e i18n).
- Hay un patrón de smoke E2E manual (registrar dos usuarios, aprobar al motorizado con el superusuario, viaje
  completo), pero no está en el repo como script.

## Alcance
### Incluye
- GitHub Actions (gratis en repos privados hasta 2000 min/mes) con un job por app, filtrado por ruta:
  - `api`: `uv sync`, `ruff check`, `ruff format --check`, `pytest` con servicios Postgres 17 y Redis 7.
  - `admin`: `pnpm install --frozen-lockfile`, `lint`, `typecheck`, `test`, `build`.
  - `mobile`: `npm ci`, `lint`, `typecheck`, `test`, `npx expo-doctor`.
  - Chequeo de migraciones: `alembic upgrade head` sobre una base vacía y `alembic check` (sin cambios de
    modelo sin migración).
- Protección de ramas `qa` y `main`: solo por PR, checks obligatorios en verde.
- Coolify sigue desplegando en push; como solo entra por PR con checks en verde, el despliegue queda protegido.
- Script `scripts/smoke_e2e.py` (en el repo, sin secretos) que corre el flujo completo contra una URL dada y
  con credenciales por variables de entorno. Se ejecuta a mano tras cada despliegue a QA y como job manual
  (`workflow_dispatch`).
- Escaneo de dependencias: Dependabot (alertas y PRs semanales agrupadas) y `pip-audit`/`npm audit` en CI
  como aviso, no bloqueante.
- Escaneo de secretos (GitHub secret scanning o `gitleaks` en CI).

### Fuera
- Despliegue desde GitHub Actions (Coolify lo sigue haciendo).
- Tests E2E de la app móvil en dispositivo (ver 20).

## App móvil
Sin cambios visibles. Los tests de i18n (mismas claves en `es` y `en`) pasan a ser obligatorios en CI.

## Admin
Sin cambios visibles.

## API y datos
- `scripts/smoke_e2e.py`: crea pasajero y motorizado de prueba con emails `smoke+<timestamp>@...`, sube
  documentos de ejemplo, aprueba con un usuario staff, conecta al motorizado, cotiza, pide, acepta, llega,
  inicia, completa, califica ambos lados y limpia (desactiva las cuentas).
- Para no ensuciar métricas: los usuarios de smoke llevan un marcador (`is_test_account`, columna nueva
  booleana) y las métricas del admin los excluyen.

## Criterios de aceptación
- Un PR a `qa` con un test roto no se puede fusionar.
- El tiempo total de CI en un PR que toca solo `admin/` es menor de 5 minutos (filtro por rutas).
- `smoke_e2e.py` termina en verde contra QA y deja las cuentas de prueba desactivadas.
- Las cuentas de prueba no aparecen en `/admin/metrics` ni en `/admin/overview`.
- `docs/deployment.md` y `docs/conventions.md` describen el flujo nuevo.

## Dependencias
Ninguna. Carlos activa la protección de ramas en GitHub (requiere permisos de dueño del repo).

## Preguntas para Carlos
1. ¿Se protege `main` para que solo entre por PR desde `qa`? Recomendado: sí.
2. ¿Los PRs de Dependabot se fusionan solos si CI pasa (solo parches)? Recomendado: no, se revisan en lote.
