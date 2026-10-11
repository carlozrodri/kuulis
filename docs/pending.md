# Pendiente

Ordenado por prioridad. Lo que depende de terceros o de Carlos está en `blockers.md`.

## Infra
- [ ] Una clave de S3 por entorno, limitada a su prefijo (hoy QA y producción comparten la misma; hallazgo M3
      de `produccion/revision-seguridad.md`). Carlos lo deja para más adelante (2026-10-11).
- [ ] Rotar el token de Expo que se pegó en un chat (Carlos lo deja para más adelante, 2026-10-11).
- [ ] Protección de ramas `qa` y `main` en GitHub (Carlos, cuando quiera; ver `deployment.md`). Hasta
      entonces, no fusionar con el check `ci` en rojo.
- [ ] Preparar el VPS de contingencia (apagado) y el dominio de marca antes de lanzar (ver
      `produccion/02-infraestructura-produccion.md`).
- [ ] Verificar QA y producción de punta a punta cuando estén los dominios en NPM (login admin, registro
      desde la app, email de verificación, push, WebSocket).
- [ ] Activar los backups en QA y producción con el bucket de R2 y hacer el simulacro de restauración
      medido (ver `deployment.md` → Backups).
- [ ] Prueba de carga (k6/Locust) contra QA: objetivo 50 req/s y 500 WebSockets sin errores.

## Legal
- [ ] Revisión de los textos legales por un abogado venezolano antes del lanzamiento, y completar los datos
  entre corchetes (responsable, RIF, domicilio, correo de contacto, tribunales, seguro). Se publican como versión
  nueva desde el admin → Legal (doc 07).
- [ ] Qué hacer cuando alguien con una cuenta suspendida y eliminada se registra de nuevo con el mismo email: la
  tabla `erased_emails` ya guarda el hash (doc 16 decide si se bloquea o se avisa a soporte).
- [ ] Plazos de conservación de la auditoría y el libro contable (supuesto: 5 años) a validar con el abogado.

## API
- [x] Páginas web para `verify-email` y `reset-password`: las sirve la web pública (`web/`, doc 08).
      Alternativa: deep links a la app móvil.
- [ ] Plantillas HTML de email con diseño.
- [ ] Scheduler de Taskiq desplegado cuando haya tareas periódicas (hoy no hay ninguna).
- [ ] Limpieza periódica de dispositivos inactivos (las notificaciones de más de 90 días ya se borran, doc 07).
- [ ] Mostrar en el admin las invitaciones entre motorizados y los meses gratis ganados.
- [ ] Revisar en el admin las cuentas en proceso de borrado (`deletion_requested_at`); el worker
      borra los datos personales a los 30 días (`ACCOUNT_DELETION_GRACE_DAYS`).

## Admin
- [x] Crear usuarios desde el panel: Equipo → Invitar (doc 06).
- [ ] Gráficas de registros por día.

## Mobile
- [ ] Manejo de toque en notificación push (navegar a la pantalla correspondiente).
- [ ] Tests de componentes.
- [ ] Enlace de invitación con el código ya puesto cuando la app esté en las tiendas (hoy el mensaje
      de WhatsApp lleva solo el código).
