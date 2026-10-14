# 19 · Analítica de producto

**Prioridad:** P1 · **Área:** API · Mobile · Admin · **Depende de:** 07 (privacidad)

## Objetivo
Entender cómo se usa Kuulis para decidir con datos: dónde se cae la gente en el registro y en el pedido, cuántos
vuelven (retención), dónde falta oferta de motorizados y qué promociones funcionan. Sin vender datos ni usar
servicios caros.

## Estado actual
- Métricas operativas en el admin (viajes, cancelaciones, tiempos, GMV, horas pico, mejores motorizados, por
  ciudad) y portada operativa. Muy buenas para la operación del día.
- No hay eventos de producto (qué pantallas se ven, en qué paso se abandona), ni retención por cohortes, ni
  embudos, ni demanda no atendida por zona.

## Alcance
### Incluye
1. **Eventos de producto propios** (sin terceros): la app envía eventos en lote (cada 30 s o al ir a segundo
   plano) a la API, que los guarda en una tabla particionada. Lista cerrada y documentada de eventos, por
   ejemplo: `app_open`, `signup_started`, `signup_completed`, `driver_onboarding_step`, `search_opened`,
   `quote_shown`, `ride_requested`, `ride_matched`, `ride_completed`, `rating_submitted`, `topup_started`,
   `topup_completed`, `report_created`, `help_article_viewed`, `update_prompt_shown`.
   Propiedades mínimas, sin datos personales ni coordenadas exactas (zona/celda de 1 km).
   Alternativa evaluada: PostHog autoalojado (pesado para el servidor) o Umami solo para la web.
2. **Embudos** en el admin: registro → primer viaje (pasajero); registro → solicitud enviada → aprobado →
   primer viaje → primer mes con cuota (motorizado); cotización → pedido → emparejado → completado.
3. **Retención por cohortes** semanales: % de pasajeros y motorizados que vuelven a viajar en la semana 1, 2, 4,
   8 desde el primer viaje.
4. **Demanda no atendida**: mapa de calor de pedidos `no_drivers` y cotizaciones sin pedido por zona y hora,
   y de motorizados conectados por zona y hora (oferta vs demanda). Base para 21.
5. **Promociones**: costo por viaje incremental, pasajeros nuevos adquiridos, retención de esos pasajeros.
6. **Economía del motorizado**: distribución de ganancias mensuales y de tramos (valida los tramos con datos
   reales, supuesto pendiente en `business-model.md`), horas conectado vs horas en viaje (utilización).
7. **Consentimiento**: la política de privacidad (07) describe la analítica; opción de excluirse en Perfil.
8. **Exportación** de tablas agregadas a CSV para análisis fuera del admin.

### Fuera
- Herramientas de BI externas pagas. Se puede conectar Metabase autoalojado a una réplica más adelante.

## App móvil
### Pasajero y motorizado
- Módulo `analytics.track(event, props)` con cola local persistente, envío en lote y respeto de la exclusión.
- Perfil → Privacidad → "Compartir datos de uso anónimos" (activado por defecto, supuesto a validar).

## Admin
- **Analítica**: pestañas Embudos, Retención, Oferta y demanda (mapa de calor por hora), Promociones,
  Motorizados (distribución de ganancias y utilización). Filtros por ciudad y rango.

## API y datos
- `analytics_events` (`id`, `user_id` nullable, `anon_id`, `event`, `props` JSONB, `platform`, `app_version`,
  `area`, `cell`, `occurred_at`, `received_at`), particionada por mes, retención 13 meses.
- `POST /analytics/events` (lote de hasta 100, rate limit por usuario, sin bloquear la app si falla).
- `driver_online_sessions` (`driver_id`, `started_at`, `ended_at`, `area`) para utilización.
- Tareas que precalculan cohortes y embudos a diario en tablas resumen.
- Endpoints admin `GET /admin/analytics/funnels|retention|supply-demand|promotions|drivers`.

## Criterios de aceptación
- El embudo de registro del motorizado muestra en qué paso del onboarding se abandona.
- El mapa de oferta y demanda muestra zonas con pedidos sin motorizado por hora.
- Ningún evento contiene email, teléfono ni coordenadas exactas (test que valida el esquema de eventos).
- Excluirse detiene el envío de eventos de ese usuario.

## Dependencias
07 (texto de privacidad y exclusión). 18 (particionado y tablas resumen).

## Preguntas para Carlos
1. ¿Datos de uso activados por defecto con opción de excluirse? Recomendado: sí.
   **Decidido** (recomendado): activados por defecto; se desactivan en Perfil → Ajustes → Privacidad.

## Cómo quedó (2026-10-14)
### API
- **Eventos** (`apps/analytics/events.py`): catálogo cerrado de 16 eventos con el tipo de cada propiedad
  (`EVENTS`). Lo que no está en el catálogo se descarta; los textos que parecen un correo o un teléfono se
  descartan, los UUID pasan a `:id` y los números largos a `:n`. La ubicación solo viaja como celda de ~1 km
  (`"floor(lat*100):floor(lng*100)"`, igual en la app, en Python y en SQL) y la API deduce la ciudad de la celda.
  Un test recorre el catálogo y prueba que ningún evento guarda correo, teléfono ni coordenadas.
- `POST /analytics/events`: lote de hasta 100, 30 por minuto, con o sin sesión (`anon_id` del dispositivo),
  responde 202. Eventos de más de 7 días se descartan y las fechas futuras se recortan a la hora del servidor.
- **Exclusión**: nuevo permiso `usage_data` en `/users/me/consents`, activado por defecto
  (`CONSENT_DEFAULTS`). Si el usuario lo apaga, la API descarta sus eventos aunque una app vieja los envíe
  (respuesta cacheada 1 día en Redis y olvidada al cambiar). La exportación de datos incluye sus eventos y el
  borrado de cuenta los elimina.
- **Tablas**: `analytics_events` particionada por mes (`occurred_at`) con partición `default` de respaldo;
  `driver_online_sessions` (conexión y desconexión de cada motorizado); `supply_hours` (minutos de motorizado
  por celda y hora); `analytics_cohorts` (resumen diario de embudos y retención).
- **Worker** (`apps/analytics/tasks.py`, latido `product_analytics` en Monitoreo): cada minuto compara los
  motorizados conectados en Redis con las sesiones abiertas y suma un minuto de oferta a su celda; cada día
  crea las particiones del mes y los dos siguientes, borra lo de más de 13 meses y recalcula 26 semanas de
  cohortes. También se puede recalcular desde el admin.
- **Reportes** `GET /admin/analytics/funnels|retention|supply-demand|promotions|drivers` y
  `GET /admin/analytics/{reporte}.csv`. Permisos `analytics.view` y `analytics.export` (auditado).

### Admin
- **Operación → Analítica**, con filtro de rango (o mes) y ciudad, botones Exportar CSV y Recalcular:
  - **Embudos**: pasajero (registro → primer pedido → primer viaje), motorizado (solicitud → moto →
    documentos → enviada → aprobado → primer viaje → primera cuota) con el paso donde más se abandona
    resaltado, pantallas del onboarding y cotización → pedido → emparejado → completado.
  - **Retención**: cohortes semanales de pasajeros y motorizados en las semanas 1, 2, 4 y 8 desde el primer
    viaje. Una celda solo se muestra cuando esa semana ya terminó para toda la cohorte.
  - **Oferta y demanda**: mapa de calor por celda de pedidos sin motorizado, cotizaciones sin pedido, pedidos y
    horas de motorizado conectado, filtrable por hora del día; gráficos por hora y tabla de las zonas peores.
  - **Promociones**: viajes, costo, costo por viaje, pasajeros nuevos y su retención a 30 días.
  - **Motorizados**: distribución de ganancias del mes, cuántos caen en cada tramo de cuota y utilización
    (horas en viaje sobre horas conectado).

### App (OTA)
- `src/lib/analytics.ts`: `track()` con cola local en archivo (máx. 500), envío cada 30 s y al pasar a segundo
  plano, `anon_id` propio del dispositivo. Si falla, reintenta luego sin molestar al usuario.
- Eventos conectados en registro, búsqueda, cotización, pedido, emparejado, viaje completado (pasajero y
  motorizado), calificación, recarga, reporte, ayuda, avisos de actualización, pantallas vistas y cada paso del
  onboarding del motorizado.
- Perfil → Ajustes → Privacidad → "Compartir datos de uso anónimos". Al apagarlo se vacía la cola y se deja de
  enviar.

### Privacidad
- `privacy.es.md` y `privacy.en.md` describen los datos de uso, la retención de 13 meses y cómo excluirse. En
  QA y producción el texto vigente es el publicado en la base: hay que publicar la nueva versión desde
  Admin → Legal (no requiere volver a aceptar).
