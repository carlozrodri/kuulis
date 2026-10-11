# 06 · Auditoría y permisos del admin

**Prioridad:** P0 · **Área:** API · Admin · **Depende de:** 05

## Objetivo
Saber siempre **quién hizo qué y cuándo** en el admin, y dar a cada persona del equipo solo los permisos que
necesita (por ejemplo, un agente de soporte no ajusta saldos ni cambia tarifas).

## Estado actual
- Dos roles en el admin: `staff` y `admin`; las páginas se restringen con `definePageMeta({ roles })`.
- Algunas acciones guardan quién las hizo en su propia tabla (aprobación de motorizados `reviewed_by_id`,
  suspensiones `created_by_id`, notas de reportes), pero no hay un registro único.
- Cambios de configuración (`app_settings`), tarifas, tramos, promociones, ajustes de saldo, cambios de rol y
  cancelaciones de viajes desde el admin no tienen historial consultable.
- El roadmap (fase 3) ya lista "Auditoría de acciones del admin".

## Alcance
### Incluye
1. **Registro de auditoría** (append-only) de toda acción de escritura del admin y de la lectura de datos
   sensibles: ver documentos de un motorizado, exportar CSV, ver datos personales completos.
   Campos: actor, acción, entidad y id, antes/después (diff en JSON, sin secretos), motivo opcional, IP,
   user agent, `request_id`, fecha.
2. **Permisos por capacidad** en lugar de solo dos roles. Roles predefinidos (editables por un admin):
   - `soporte`: reportes, ver usuarios y viajes, suspender hasta 7 días.
   - `verificador`: cola de motorizados y documentos.
   - `finanzas`: recargas, transferencias, suscripciones, finanzas, ajustes de saldo hasta un límite.
   - `operaciones`: viajes en vivo, cancelar viajes, promociones, tasas, notificaciones masivas.
   - `admin`: todo, incluidos configuración, tarifas, tramos, roles y equipo.
3. **Doble aprobación** (cuatro ojos) para acciones de alto impacto, configurable: ajustes de saldo mayores a
   X USD, cambios de tramos o tarifas, notificaciones masivas a todos. Una persona propone y otra aprueba.
4. **Motivo obligatorio** en acciones que afectan a un usuario (suspender, ajustar saldo, rechazar recarga,
   cancelar viaje) — algunas ya lo piden; unificar.
5. **Gestión del equipo**: invitar staff por email (enlace de un solo uso), asignar rol, desactivar, ver
   último acceso. Reutiliza `POST /users` (hoy sin pantalla, ver `docs/pending.md`).
6. **Retención**: la auditoría se guarda al menos 2 años y no se puede editar ni borrar desde la app.

### Fuera
- SSO corporativo.

## App móvil
Sin cambios.

## Admin
- **Equipo**: lista de staff con rol, 2FA activo, último acceso; invitar, cambiar rol, desactivar.
- **Roles**: matriz de permisos por rol (solo admin).
- **Auditoría**: tabla filtrable por actor, acción, entidad, fecha; detalle con el diff antes/después; enlace a
  la entidad. Exportación CSV (también auditada).
- En la ficha de cada usuario, motorizado, viaje y promoción: pestaña "Historial" con su auditoría.
- **Aprobaciones pendientes**: bandeja de acciones que esperan segunda firma, con contador en el menú.
- El menú y los botones se ocultan según permisos (además del bloqueo en la API).

## API y datos
- Tabla `audit_log` (`id`, `actor_id`, `action` string estable p. ej. `wallet.adjust`, `entity_type`,
  `entity_id`, `before` JSONB, `after` JSONB, `reason`, `ip`, `user_agent`, `request_id`, `created_at`).
  Índices por `(entity_type, entity_id)`, `actor_id`, `created_at`. Particionado por mes cuando crezca.
- Helper `audit(session, actor, action, entity, before, after, reason)` llamado desde los services del admin
  dentro de la misma transacción.
- Tablas `staff_roles` (`name`, `permissions` text[]) y `users.staff_role_id`. Dependencia
  `require_permission("wallet.adjust")` que reemplaza a `StaffUser`/`AdminUser` en cada endpoint admin.
- Tabla `pending_approvals` (`action`, `payload`, `requested_by`, `approved_by`, `status`, `expires_at`).
- Endpoints: `GET /admin/audit`, `GET /admin/staff`, `POST /admin/staff/invite`, `PATCH /admin/staff/{id}`,
  `GET/PUT /admin/roles`, `GET /admin/approvals`, `POST /admin/approvals/{id}/approve|reject`.
- Error `permission_denied` (403) con `details.permission`.

## Criterios de aceptación
- Cada endpoint `/admin/*` de escritura deja una fila en `audit_log` (test que recorre el router y lo exige).
- Un usuario con rol `soporte` recibe 403 al intentar ajustar un saldo, aunque llame a la API directamente.
- Un ajuste de saldo por encima del límite queda pendiente hasta que otra persona lo aprueba; quien lo pidió no
  puede aprobarlo.
- Ver los documentos de un motorizado queda auditado con actor y hora.

## Dependencias
05 (2FA y re-autenticación para acciones sensibles).

## Preguntas para Carlos
1. ¿Cuántas personas tendrá el equipo al lanzar y qué hará cada una? Ayuda a fijar los roles iniciales.
2. ¿Límite para doble aprobación de ajustes de saldo? Recomendado: 20 USD.

## Decidido (2026-10-11)
1. Roles iniciales: los cinco del alcance (`soporte`, `verificador`, `finanzas`, `operaciones`, `admin`); un
   admin los edita cuando se sepa quién hace qué.
2. Doble aprobación de ajustes de saldo por encima de **20 USD**.
3. Se entrega en tres partes: (1) registro de auditoría y su pantalla; (2) permisos por capacidad y gestión del
   equipo; (3) doble aprobación.

## Cómo quedó
### Parte 1 (2026-10-11)
- Tabla `audit_log` con actor (id y correo), acción estable (`wallet.adjust`), entidad e id, antes/después en
  JSONB, motivo, IP, user agent, `request_id` y fecha. Índices por entidad, actor, fecha y acción.
- Cada endpoint de escritura del admin declara su acción con `dependencies=[audit("wallet.adjust", "wallet",
  "user_id")]`. La fila se escribe con el primer commit de la sesión de la petición (evento `before_commit`),
  así que la acción y su auditoría van en la misma transacción y una petición fallida no deja fila. El cuerpo
  de la petición se guarda sin secretos (contraseñas, tokens, códigos 2FA) y el `reason` del cuerpo pasa a la
  columna de motivo.
- Antes/después reales en configuración (solo las claves cambiadas), cambios de usuario (rol, activo, etc.),
  ajustes de saldo (saldo antes y después), confirmación de recargas y suspensiones.
- Lecturas sensibles auditadas: ficha de un motorizado con sus documentos (`driver.view`), datos personales
  completos de un usuario (`user.view`), exportaciones CSV de finanzas, abrir el archivo de otra persona
  (`file.view`) y la exportación de la propia auditoría.
- `test_coverage.py` recorre todas las rutas y falla si un endpoint de escritura protegido por rol de staff no
  declara su acción de auditoría.
- Motivo obligatorio: suspender, ajustar saldo, rechazar recarga y cancelar viaje ya lo exigían.
- Admin: página **Auditoría** (solo admin) con filtros por acción, tipo e id de registro, persona y fechas;
  detalle con el diff antes/después y exportación CSV. Tarjeta **Historial** en la ficha de usuario,
  motorizado, viaje, promoción y saldo (una tarjeta y no una pestaña, porque esas fichas no tienen pestañas).
- Retención: la app no tiene forma de editar ni borrar la auditoría. Si un usuario se borra, su id queda en
  blanco pero el correo del actor se conserva.
- De paso: los correos a dominios reservados (`@example.com`, `.test`, etc.) ya no se envían. Resend los
  rechazaba con 422 y la tarea reintentaba sin sentido (cuentas de prueba y la cuenta del smoke test).

### Parte 2 (2026-10-11)
- Tabla `staff_roles` (`name`, `label`, `permissions`) y `users.staff_role_id`. La migración crea Soporte,
  Verificador, Finanzas y Operaciones; un admin los cambia o crea otros en **Roles** (matriz de permisos).
- Catálogo de permisos en `apps/staff/permissions.py`. Cada endpoint del admin declara el suyo con
  `Can("wallet.adjust")`; un test recorre las rutas y falla si un endpoint abierto a staff no lo declara. Sin
  el permiso responde 403 `permission_denied` con `details.permission`.
- Solo admin, no asignables a un rol: configuración, tramos de suscripción, equipo, roles, auditoría y la
  edición de usuarios. Leer la configuración queda abierto a todo el staff porque las páginas toman de ahí sus
  valores por defecto; `config.view` solo muestra la página de Configuración.
- Soporte suspende hasta 7 días (`users.suspend`); más tiempo o sin fecha pide `users.suspend_long`.
- Ver recargas (`top_ups.view`) y confirmarlas (`top_ups.manage`) son permisos separados, igual que ver y
  fijar tasas.
- **Equipo**: lista con rol, 2FA, último acceso e invitación pendiente; invitar por correo (enlace de un
  solo uso, 3 días), cambiar rol, reenviar la invitación y desactivar. Cambiar el rol o desactivar cierra sus
  sesiones. Todo queda en la auditoría (`staff.invite`, `staff.update`, `role.update`).
- El menú y los botones se ocultan según los permisos (`/users/me` trae `permissions`), y una página sin
  permiso lleva a la primera que sí puede ver.
- Los staff que ya existían quedan sin rol hasta que un admin les asigne uno en Equipo.

### Parte 3 (2026-10-11)
- Tabla `pending_approvals` (acción, resumen, datos de la acción en JSONB, motivo, estado, quién pidió, quién
  decidió, nota, resultado y vencimiento). Las solicitudes vencen a las 48 horas.
- Qué espera una segunda firma (se cambia en **Configuración → Doble aprobación**):
  - Ajustes de saldo de más de **20 USD**, a favor o en contra (`approval_adjust_limit`, 0 la desactiva).
  - Cambios de tarifas o del redondeo y tramos de suscripción nuevos (`approval_fares`). Solo otro admin los
    aprueba. Si el panel manda la configuración entera, solo cuentan los valores que de verdad cambian, y al
    aprobar se aplican solo esas claves, así que no deshace otros cambios hechos mientras tanto.
  - Notificaciones a todos o a un rol completo (`approval_broadcasts`). Las de un solo usuario salen al momento.
- El endpoint responde **202** con `{"status": "pending_approval", "approval": {...}}` en lugar de actuar. Lo
  inválido (mes pasado, motorizado inexistente) se rechaza antes de crear la solicitud.
- `GET /admin/approvals`, `GET /admin/approvals/count`, `POST /admin/approvals/{id}/approve` (pide código 2FA
  reciente) y `POST /admin/approvals/{id}/reject` (nota obligatoria). Quien pidió no puede aprobar
  (`approval_own_request`); aprobar exige el permiso de la acción (`wallet.adjust`, `notifications.send`) o ser
  admin si la acción es solo de admin. Cada quien ve sus propias solicitudes y las que puede decidir.
- Al aprobar, la acción corre en la misma transacción y queda a nombre de quien la pidió. Si falla (por ejemplo,
  saldo insuficiente) la solicitud sigue pendiente.
- Auditoría: `approval.request` (con los datos de la acción), `approval.approve` y `approval.reject`.
- Admin: página **Aprobaciones** con contador en el menú, filtro por estado, datos de cada solicitud y botones de
  aprobar o rechazar. Ajustar saldo, crear tramos, guardar tarifas y enviar notificaciones avisan cuando el
  cambio quedó esperando aprobación.
- Mientras Carlos sea el único admin, las tarifas y los tramos no tienen quién los apruebe; se puede apagar
  `approval_fares` en Configuración hasta que haya un segundo admin.
