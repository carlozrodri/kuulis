# Roadmap

## Fase 0 · Fundaciones (hecha, 2026-10-09)
- [x] Monorepo privado `carlozrodri/kuulis` con ramas `main` y `qa`.
- [x] API FastAPI: auth JWT con roles, usuarios, notificaciones (push + bandeja + WebSocket), archivos S3,
      emails con Resend, tareas en background, migraciones, health checks, rate limiting, tests.
- [x] Admin Nuxt: login por rol, panel, usuarios, envío de notificaciones, perfil, es/en.
- [x] Mobile Expo: login, registro, recuperar contraseña, inicio, notificaciones, perfil, push, WebSocket, es/en.
- [x] Coolify: proyecto `kuulis` con QA y producción (API, worker, admin, Postgres, Redis, backups).
- [x] Documentación inicial.

## Fase 1 · Producto (en curso desde 2026-10-09)
Plan en `docs/product/`; diseño en `docs/product/mobile-design.md`. Cada sub-fase deja API, admin y mobile
funcionando en QA antes de pasar a la siguiente.

### 1A · Cuentas, motorizados y configuración (hecha 2026-10-09, en QA; contrato en `docs/api/phase-1a.md`)
- [x] Mobile: sistema de diseño Verde Ávila (tokens, fuente, componentes) y modo claro/oscuro.
- [x] Login con Google (Android/iOS) y Apple (solo iOS).
- [x] Modo pasajero / motorizado en la misma cuenta.
- [x] Perfil de motorizado: vehículo (tipo, marca, modelo, año, placa, color), documentos en S3 privado,
      estados (borrador, en revisión, aprobado, rechazado con motivo, suspendido).
- [x] Admin: cola de aprobación con visor de documentos; configuración editable (edad mínima, año mínimo,
      documentos requeridos).

### 1B · Viajes (hecha 2026-10-09, en QA; contrato en `docs/api/phase-1b.md`)
- [x] Ubicación en vivo del motorizado por WebSocket, guardada en Redis (GEO).
- [x] Cotización: tarifa base, km, minutos, mínimo y recargo, todo configurable en el admin.
- [x] Solicitud, emparejamiento por cercanía con oferta de 15 s, estados del viaje y cancelaciones.
- [x] Chat del viaje y calificación obligatoria de ambos lados.
- [x] Mapas: `react-native-maps` (gratis). Rutas con OSRM y búsqueda con Photon. En QA usan los
      servidores públicos de demostración.
- [ ] Antes del lanzamiento: alojar OSRM y Photon en Coolify (los públicos no son para producción).
- [ ] Ubicación en segundo plano del motorizado (requiere build instalada, no funciona en Expo Go).

### 1C · Tasas y promociones
- [x] Tasas BCV y Binance P2P (worker), historial y corrección manual en el admin.
- [x] Promociones con presupuesto, fechas y tope por pasajero; crédito al motorizado en su billetera.
- [x] Billetera del motorizado (solo lectura: saldo y movimientos). Contrato en `docs/api/phase-1c.md`.

### 1D · Billetera y suscripción
- [ ] Libro contable de la billetera (recargas, cuotas, promociones, transferencias).
- [ ] Recarga con Binance Pay (validar API de conciliación) y TRC-20 como respaldo; confirmación manual en el admin.
- [ ] Cuota el día 1 por tramos, 3 meses gratis desde el primer viaje, 1 semana de gracia y bloqueo.
- [ ] Transferencias entre motorizados con límite mensual de lo enviado.

### 1E · Operación en el admin
- [ ] Viajes en vivo e historial, reportes y suspensiones, conciliación de pagos, métricas.

## Fase 2 · Lanzamiento móvil
- [ ] Cuentas Apple Developer y Google Play (bloqueo, ver `blockers.md`).
- [ ] Proyecto EAS, credenciales push (APNs/FCM), builds internas de QA.
- [ ] Iconos, splash, nombre final y bundle ids definitivos.
- [ ] Deep links para verificar email y resetear contraseña dentro de la app.

## Fase 3 · Operación
- [ ] Activar Sentry (API, admin, mobile).
- [ ] Prueba de carga y ajuste de workers/pool.
- [ ] Auditoría de acciones del admin.
