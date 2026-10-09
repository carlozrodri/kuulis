# Roadmap

## Fase 0 · Fundaciones (hecha, 2026-10-09)
- [x] Monorepo privado `carlozrodri/kuulis` con ramas `main` y `qa`.
- [x] API FastAPI: auth JWT con roles, usuarios, notificaciones (push + bandeja + WebSocket), archivos S3,
      emails con Resend, tareas en background, migraciones, health checks, rate limiting, tests.
- [x] Admin Nuxt: login por rol, panel, usuarios, envío de notificaciones, perfil, es/en.
- [x] Mobile Expo: login, registro, recuperar contraseña, inicio, notificaciones, perfil, push, WebSocket, es/en.
- [x] Coolify: proyecto `kuulis` con QA y producción (API, worker, admin, Postgres, Redis, backups).
- [x] Documentación inicial.

## Fase 1 · Producto (siguiente)
Depende de la definición del producto. Al llegar ahí: modelar las apps de dominio en `api/apps/`,
pantallas en mobile y secciones del admin.

## Fase 2 · Lanzamiento móvil
- [ ] Cuentas Apple Developer y Google Play (bloqueo, ver `blockers.md`).
- [ ] Proyecto EAS, credenciales push (APNs/FCM), builds internas de QA.
- [ ] Iconos, splash, nombre final y bundle ids definitivos.
- [ ] Deep links para verificar email y resetear contraseña dentro de la app.

## Fase 3 · Operación
- [ ] Activar Sentry (API, admin, mobile).
- [ ] Prueba de carga y ajuste de workers/pool.
- [ ] Login social (Google, Apple).
- [ ] Auditoría de acciones del admin.
