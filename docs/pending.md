# Pendiente

Ordenado por prioridad. Lo que depende de terceros o de Carlos está en `blockers.md`.

## Infra
- [ ] Protección de ramas `qa` y `main` en GitHub (Carlos, cuando quiera; ver `deployment.md`). Hasta
      entonces, no fusionar con el check `ci` en rojo.
- [ ] Preparar el VPS de contingencia (apagado) y el dominio de marca antes de lanzar (ver
      `produccion/02-infraestructura-produccion.md`).
- [ ] Verificar QA y producción de punta a punta cuando estén los dominios en NPM (login admin, registro
      desde la app, email de verificación, push, WebSocket).
- [ ] Activar los backups en QA y producción con el bucket de R2 y hacer el simulacro de restauración
      medido (ver `deployment.md` → Backups).
- [ ] Prueba de carga (k6/Locust) contra QA: objetivo 50 req/s y 500 WebSockets sin errores.

## API
- [ ] Páginas web para `verify-email` y `reset-password` (los enlaces de los emails apuntan a
      `FRONTEND_URL/verify-email?token=` y `/reset-password?token=`; hoy esas rutas no existen en el admin).
      Alternativa: deep links a la app móvil.
- [ ] Plantillas HTML de email con diseño.
- [ ] Scheduler de Taskiq desplegado cuando haya tareas periódicas (hoy no hay ninguna).
- [ ] Limpieza periódica de notificaciones antiguas y dispositivos inactivos.
- [ ] Mostrar en el admin las invitaciones entre motorizados y los meses gratis ganados.
- [ ] Revisar en el admin las cuentas en proceso de borrado (`deletion_requested_at`); el worker
      borra los datos personales a los 30 días (`ACCOUNT_DELETION_GRACE_DAYS`).

## Admin
- [ ] Crear usuarios desde el panel (el endpoint `POST /users` ya existe).
- [ ] Gráficas de registros por día.

## Mobile
- [ ] Manejo de toque en notificación push (navegar a la pantalla correspondiente).
- [ ] Tests de componentes.
- [ ] Enlace de invitación con el código ya puesto cuando la app esté en las tiendas (hoy el mensaje
      de WhatsApp lleva solo el código).
