# 03 · Observabilidad y alertas

**Prioridad:** P0 · **Área:** Infra · Admin · **Depende de:** 02

## Objetivo
Enterarnos de un problema antes que los usuarios: errores con contexto, métricas de salud, alertas a Carlos
por un canal que mire (Telegram o email) y una página de estado del sistema en el admin. A costo cero o casi.

## Estado actual
- Sentry instalado y **apagado** (`SENTRY_ENABLED=false`, decisión de Carlos para esta etapa).
- Los crashes de la app llegan a los logs de la API (`/health/client-errors`); solo se ven entrando a Coolify.
- Los loops del worker (tasas, conciliación Binance, cuotas del día 1, despacho) registran errores en logs y
  `/admin/overview` muestra `stale_rates`, pero nadie recibe un aviso si se detienen.
- No hay monitor externo de disponibilidad ni métricas de latencia.

## Alcance
### Incluye
1. **Errores**: GlitchTip autoalojado en Coolify (compatible con el SDK de Sentry ya instalado, sin costo por
   evento) o Sentry gratuito. Se activa en API, worker, admin y mobile (`@sentry/react-native`), con
   `environment` qa/production, `release` = commit, y sin datos personales (sin emails ni coordenadas en los
   eventos). Muestreo de trazas 5 %. El endpoint `/health/client-errors` se mantiene como respaldo.
2. **Monitor externo**: Uptime Kuma (autoalojado, idealmente fuera del homelab, por ejemplo en el VPS de
   contingencia) o un servicio gratuito (UptimeRobot/Better Stack) sobre `/api/health/ready`, el admin y el
   WebSocket. Página de estado pública opcional.
3. **Latidos de los loops** (heartbeats): cada loop escribe en Redis `heartbeat:<loop>` con la hora. Un chequeo
   alerta si un latido tiene más de N minutos: despacho > 2 min, Binance > 5 min, tasas > 2 h (BCV 26 h),
   cuotas del día 1 sin ejecutar a las 06:00 Caracas.
4. **Métricas**: endpoint `/api/metrics` (Prometheus, protegido por red interna o token) con latencia por ruta,
   errores 5xx, WebSockets abiertos, motorizados conectados, viajes buscando, tamaño de colas Taskiq y del set
   de despacho. Grafana es opcional; para empezar basta con las alertas y la página del admin.
5. **Alertas** a Telegram (bot gratuito) y email (Resend): API caída, 5xx > 2 % en 5 min, loop sin latido,
   tasa vencida, cola atascada, disco > 85 %, backup fallido (04), viajes `no_drivers` > 30 % en una hora,
   reporte urgente nuevo (13) y SOS (11).
6. **Logs**: formato JSON ya existe; añadir `request_id`, `user_id` y `ride_id` cuando existan, y retención
   de 14 días. Opcional: Loki + Grafana si se necesita buscar entre contenedores.

### Fuera
- APM de pago, trazas distribuidas completas.

## App móvil
- SDK de Sentry/GlitchTip con source maps subidos en cada build y OTA (09). El reporte actual a los logs queda
  como respaldo si el DSN no está configurado.
- Los errores muestran al usuario el mensaje amable que ya existe; nada nuevo visible.

## Admin
- Página **Estado del sistema** (staff): salud de Postgres, Redis, OSRM, Photon, worker; latido de cada loop
  con hora y estado (verde/amarillo/rojo); tamaño de colas; versión desplegada; últimos errores agrupados
  (enlace a GlitchTip).
- La portada (`/admin/overview`) muestra un aviso si algún loop está en rojo.
- SDK de errores en el admin.

## API y datos
- `GET /admin/system/health` (staff) → `{services: [{name, status, latency_ms}], loops: [{name, last_beat_at,
  status}], queues: {taskiq_pending, dispatch_due}, version, commit}`.
- Tarea `monitoring.check` (cada minuto, con lock en Redis) que evalúa reglas y envía alertas, con
  deduplicación (no repetir la misma alerta más de una vez cada 30 min) y aviso de recuperación.
- Configuración (`AppConfig` o variables): `ALERT_TELEGRAM_BOT_TOKEN`, `ALERT_TELEGRAM_CHAT_ID`,
  `ALERT_EMAILS`.

## Criterios de aceptación
- Detener el worker en QA genera una alerta en Telegram en menos de 3 minutos y otra al recuperarse.
- Un error 500 provocado aparece en GlitchTip con release, ruta y `request_id`, sin email del usuario.
- Un crash provocado en la app aparece con la traza legible (source maps).
- La página Estado del sistema refleja la caída de OSRM en menos de un minuto.

## Dependencias
02 (servicios y versión expuesta). Las alertas de SOS y reportes urgentes se conectan cuando existan 11 y 13.

## Preguntas para Carlos
1. ¿Se puede encender ya el reporte de errores? Antes pediste Sentry apagado "en esta etapa". Recomendado:
   GlitchTip autoalojado encendido antes de lanzar.
2. ¿Canal de alertas: Telegram, email o ambos? Recomendado: Telegram para urgentes y email para el resumen.
