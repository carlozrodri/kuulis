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
