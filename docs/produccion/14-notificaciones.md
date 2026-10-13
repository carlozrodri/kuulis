# 14 · Notificaciones completas

**Prioridad:** P1 · **Área:** Mobile · API · Admin · **Depende de:** 10

## Objetivo
Que cada notificación lleve a la pantalla correcta, que el usuario elija qué recibe, que los emails se vean
profesionales y que el equipo pueda enviar campañas segmentadas y programadas sin molestar de más.

## Estado actual
- Push con Expo (tabla `devices`, lotes de 100, tokens inválidos desactivados), bandeja in-app y WebSocket.
- Al **tocar** una push, la app solo navega si es de un reporte; las de viaje, billetera, suscripción y cuenta
  refrescan datos pero no abren su pantalla (`usePushNotifications.ts`).
- Admin → Notificaciones: envío a todos, por rol o a un usuario, inmediato.
- Emails en HTML simple; plantillas con diseño pendientes (`docs/pending.md`).
- Sin preferencias por tipo, sin horario silencioso, sin limpieza de notificaciones viejas y dispositivos
  inactivos (pendiente).
- Un solo canal de Android (`default`): la oferta de viaje suena igual que una promoción.

## Alcance
### Incluye
1. **Navegación al tocar** para todos los tipos: viaje (pantalla del viaje o calificar), oferta (pantalla de
   conducir), billetera, recarga, cuota, cuenta, soporte (13), seguridad (11), anuncio (10).
2. **Canales de Android** con sonido e importancia propios: `ride_offer` (máxima, sonido largo propio, pantalla
   completa si el teléfono está bloqueado), `ride_updates` (alta), `safety` (máxima), `account` (normal),
   `marketing` (baja). Sonido de oferta distintivo y vibración fuerte para el motorizado.
3. **Preferencias**: el usuario puede apagar `marketing` y novedades; los transaccionales y de seguridad no se
   pueden apagar. Horario silencioso para marketing (por defecto 21:00–08:00 Caracas).
4. **Plantillas de email** con la marca (MJML o HTML probado en Gmail/Outlook), es/en: verificación, cambio de
   contraseña, bienvenida, motorizado aprobado/rechazado, recarga acreditada, cuota cobrada (recibo), aviso de
   cuota, documento por vencer, respuesta de soporte, eliminación de cuenta, resumen mensual del motorizado.
5. **Campañas** desde el admin: segmentos (rol, ciudad, actividad en los últimos N días, motorizados con
   cuota pendiente, nuevos sin primer viaje, versión de app), canal (push, bandeja, email), programación,
   vista previa del alcance, límite de frecuencia (máximo 1 de marketing por día por usuario), y resultados
   (enviados, entregados, abiertos).
6. **Mantenimiento**: borrar notificaciones de la bandeja de más de 90 días, desactivar dispositivos sin uso en
   60 días, reintentos con backoff de los envíos que fallan, lectura de *receipts* de Expo para detectar
   tokens muertos.
7. **Web Push** para la PWA de pasajeros (09) con claves VAPID propias.

### Fuera
- SMS (decisión de costo: sin SMS).

## App móvil
### Pasajero y motorizado
- Perfil → Notificaciones: interruptores por tipo y horario silencioso.
- Tocar cualquier push abre la pantalla que corresponde, incluso con la app cerrada.
- Bandeja: agrupación por día, marcar todo como leído (si no existe), íconos por tipo.
### Motorizado
- Oferta de viaje con sonido propio y aviso de pantalla completa en Android cuando la app está en segundo plano.

## Admin
- **Campañas**: crear, segmentar, programar, previsualizar en teléfono, enviar prueba a mí mismo, resultados.
- Reemplaza la página actual de Notificaciones (que queda como "envío rápido").
- **Plantillas de email**: vista previa de cada plantilla en es/en con datos de ejemplo.

## API y datos
- `notifications` agrega `category` (transactional|safety|support|marketing) y `deep_link`.
- `notification_preferences` (`user_id`, `category`, `enabled`, `quiet_start`, `quiet_end`).
- `campaigns` (`name`, `segment` JSONB, `channels`, `title`, `body` es/en, `deep_link`, `scheduled_at`,
  `status`, `stats` JSONB, `created_by`).
- `devices` agrega `last_seen_at`, `app_version`.
- Tareas: `campaigns.dispatch` (programadas, en lotes por keyset), `notifications.cleanup` (diaria),
  `push.receipts` (cada 15 min).
- Plantillas de email en `api/kuulis/templates/email/` con renderizado en el worker.
- Endpoints: `GET/PUT /notifications/preferences`, admin: CRUD de campañas, `POST /admin/campaigns/{id}/test`,
  `GET /admin/campaigns/{id}/audience-count`.

## Criterios de aceptación
- Tocar cada tipo de push con la app cerrada abre la pantalla correcta (probado en Android físico).
- Un usuario que apagó marketing no recibe campañas, pero sí las de su viaje.
- La oferta de viaje suena con el sonido propio aunque el teléfono esté en modo "No molestar" permitido para el
  canal (si el usuario lo concede).
- Una campaña programada a 3000 usuarios se envía sin afectar la latencia de la API (cola separada, ver 18).
- Los emails se ven correctamente en Gmail Android y Outlook web.

## Dependencias
10 (deep links y anuncios). 13 y 11 aportan los tipos `support` y `safety`.

## Preguntas para Carlos
1. ¿Límite de campañas de marketing: 1 al día por usuario? Recomendado: sí, y ninguna en horario silencioso.
   **Decidido** (recomendado): 1 al día, configurable en Ajustes → Notificaciones; en horario silencioso esperan.

## Cómo quedó (2026-10-13)
### API (`api/apps/notifications`)
- **Categorías:** cada notificación de la bandeja tiene `category` (transactional, safety, support, marketing)
  y un `deep_link` opcional. La migración clasifica las existentes por su `data.type`.
- **Canales de Android:** la app crea `ride_offer`, `ride_updates`, `safety`, `account`, `marketing` y
  `default`, y al registrar el teléfono dice cuáles tiene. El servidor elige el canal de cada push entre los
  que ese teléfono reportó; a una app vieja le llega por `default` (un canal que no existe ocultaría el aviso).
- **Preferencias:** `GET/PUT /notifications/preferences`. Solo se apaga el marketing (push y email por
  separado). Horario silencioso por usuario, por defecto 21:00–08:00 Caracas.
- **Campañas:** segmentos (pasajeros/motorizados, ciudad, activos o inactivos en N días, cuota pendiente,
  nuevos sin viaje, versión de app, idioma), canales push, bandeja y email, programación, aprobación de dos
  personas si está activa para envíos masivos, prueba a mí mismo y resultados (enviados, omitidos por motivo,
  push entregados según los *receipts* de Expo, emails y abiertos). Al empezar se congela la lista de
  destinatarios; quien está en horario silencioso espera, quien ya recibió marketing ese día se omite.
- **Emails con la marca:** un diseño único (tabla con estilos en línea, probado para Gmail y Outlook) para todos
  los correos, en es/en: confirmar correo, bienvenida, contraseña restablecida y cambiada, invitación, intentos
  fallidos, motorizado aprobado/rechazado, documento por vencer, recarga acreditada, recibo y aviso de cuota,
  resumen mensual del motorizado (el día 1), soporte, descarga de datos y eliminación de cuenta.
- **Mantenimiento** (bucle del worker, latido `notifications`): campañas cada 30 s, *receipts* de Expo cada
  15 min (tokens muertos se desactivan), y una vez al día se borran notificaciones de más de 90 días y se
  desactivan teléfonos sin uso en 60 días. Todo configurable en `notifications` de los ajustes.
### Admin
- **Campañas** (lista, editor con alcance en vivo y vista de teléfono, prueba, programar, resultados en vivo),
  **Plantillas de email** (vista previa es/en, diseño o texto, ancho de teléfono o escritorio) y el bloque
  Notificaciones en Ajustes. La página de Notificaciones queda como **Envío rápido**.
### App
- Tocar cualquier push abre su pantalla, también con la app cerrada (tabla en `src/lib/notificationRoutes.ts`).
- Perfil → Ajustes → Notificaciones: promociones por push y por email, lo que siempre llega, horario silencioso.
- Bandeja agrupada por día, con ícono por tipo y "Marcar todo como leído".
### Pendiente
- **Sonido propio de la oferta y aviso a pantalla completa** para el motorizado: necesitan un APK nuevo (el
  sonido va dentro de la app). Cuando se haga, ese APK crea el canal `ride_offer_sound` y el servidor ya lo
  prefiere para las ofertas.
- **Web Push para la PWA:** espera a la PWA de iPhone, que se pospuso en 09.
- Probar en un Android físico que cada tipo de push abre su pantalla con la app cerrada.

