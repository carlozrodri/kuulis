# Pendiente

Ordenado por prioridad. Lo que depende de terceros o de Carlos está en `blockers.md`.

## Infra
- [ ] Verificar QA y producción de punta a punta cuando estén los dominios en NPM (login admin, registro
      desde la app, email de verificación, push, WebSocket).
- [ ] Probar una restauración de backup en QA.
- [ ] Prueba de carga (k6/Locust) contra QA: objetivo 50 req/s y 500 WebSockets sin errores.

## API
- [ ] Páginas web para `verify-email` y `reset-password` (los enlaces de los emails apuntan a
      `FRONTEND_URL/verify-email?token=` y `/reset-password?token=`; hoy esas rutas no existen en el admin).
      Alternativa: deep links a la app móvil.
- [ ] Plantillas HTML de email con diseño.
- [ ] Scheduler de Taskiq desplegado cuando haya tareas periódicas (hoy no hay ninguna).
- [ ] Endpoint de avatar (subida con presign ya existe; falta guardar `avatar_key` y mostrarlo).
- [ ] Limpieza periódica de notificaciones antiguas y dispositivos inactivos.

## Admin
- [ ] Crear usuarios desde el panel (el endpoint `POST /users` ya existe).
- [ ] Gráficas de registros por día.

## Mobile
- [ ] Pantallas de cambio de contraseña y edición de perfil.
- [ ] Manejo de toque en notificación push (navegar a la pantalla correspondiente).
- [ ] Tests de componentes.
