# 18 · Escalabilidad y pruebas de carga

**Prioridad:** P1 (la prueba de carga es P0 antes de abrir al público) · **Área:** Infra · API ·
**Depende de:** 02, 03

## Objetivo
Demostrar con mediciones que Kuulis aguanta **5000 usuarios activos al día** con margen (objetivo de diseño:
3 veces el pico estimado) y dejar escrito cuándo y cómo crecer.

## Estado actual
- `docs/scaling.md` estima ~500 usuarios simultáneos en pico, 25–50 req/s y ~500 WebSockets; 4 workers de
  gunicorn, pool de 10+5, 2 procesos de worker.
- **Nunca se hizo una prueba de carga** (pendiente en `docs/pending.md`: 50 req/s y 500 WebSockets).
- Puntos de presión no medidos:
  - Mensajes de ubicación: cada motorizado conectado envía posición cada 3–5 s (500 motorizados ≈ 100–170
    mensajes/s) y cada uno se reenvía por pub/sub al pasajero.
  - Loops dentro de cada proceso de worker (despacho, tasas, Binance, suscripciones) compitiendo con emails y
    push masivos en la misma cola.
  - Consultas de métricas del admin sobre `rides` sin réplica.
  - Un solo servidor (homelab).

## Alcance
### Incluye
1. **Escenarios de carga con k6** (scripts en `loadtest/`), contra QA con datos sintéticos:
   - 600 motorizados conectados enviando ubicación cada 4 s por WebSocket.
   - 1500 pasajeros abriendo la app, cotizando y pidiendo (perfil de hora pico de `by_hour`).
   - 150 viajes simultáneos de punta a punta con chat.
   - Admin: 5 personas con viajes en vivo y métricas abiertas.
   - Campaña de push a 5000 usuarios durante el pico.
   Objetivos: p95 de API < 300 ms, despacho de oferta < 2 s desde el pedido, 0 errores 5xx, WebSockets
   estables 30 min, CPU < 70 %.
2. **Datos sintéticos**: script que crea 5000 usuarios, 600 motorizados aprobados y 100 000 viajes históricos
   para probar consultas reales (métricas, historial, finanzas).
3. **Ajustes según resultados** (en orden de `scaling.md`): workers, pool, **PgBouncer** en modo transacción,
   índices que falten (con `pg_stat_statements` de 02), cache de cotización y de `AppConfig`, reducción de
   frecuencia de ubicación cuando el motorizado está quieto (ahorra datos y servidor).
4. **Colas separadas** en Taskiq: `realtime` (despacho, ofertas), `default` (emails, push transaccional) y
   `bulk` (campañas, exportaciones), con procesos dedicados para que una campaña no retrase una oferta.
5. **Loops con un solo dueño**: confirmar que todos los loops periódicos usan lock en Redis (despacho ya usa Lua
   y `reconcile` uno a la vez; suscripciones usa lock) y documentarlo; latidos en 03.
6. **Retención y tamaño**: particionar o archivar `ride_offers`, `ride_messages`, puntos de recorrido (11) y
   `audit_log` (06) por mes; estimar crecimiento en GB por mes.
7. **Plan de crecimiento** actualizado en `docs/scaling.md` con los números medidos: a partir de cuántos
   usuarios hace falta segundo servidor, réplica de lectura para métricas o Redis dedicado.
8. **Pruebas de caos ligeras**: reiniciar API, worker y Redis durante la carga y verificar que los viajes en
   curso siguen y las ofertas se reprograman.

### Fuera
- Autoescalado (Coolify no lo tiene; se escala a mano con el plan).

## App móvil
- Frecuencia adaptativa de ubicación del motorizado: cada 4 s en movimiento, cada 15 s quieto y sin viaje.
- Reintentos con backoff y jitter en todas las peticiones (evita avalanchas tras una caída).

## Admin
- Métricas con rangos grandes calculadas desde tablas resumen diarias (no sobre `rides` crudo).

## API y datos
- Tabla `daily_metrics` (o vista materializada) por día y ciudad, actualizada cada 10 min y al cerrar el día.
- Configuración de colas en `kuulis/tasks.py` y variables `WORKER_QUEUES` por contenedor.
- Servicio `kuulis-pgbouncer` en Coolify si las pruebas lo justifican.

## Criterios de aceptación
- Informe en `docs/produccion/informe-carga.md` con los escenarios, resultados, cuellos de botella encontrados
  y cambios aplicados.
- Se cumplen los objetivos de p95, despacho y errores con 3 veces el pico estimado.
- Reiniciar el worker durante la prueba no deja viajes en `searching` sin ofertas más de 30 s.
- Una campaña de 5000 push no aumenta el tiempo de despacho.

## Dependencias
02 (infraestructura final), 03 (métricas para medir).

## Preguntas para Carlos
1. **Decidido (12-10-2026):** sí, QA en su servidor real; "pc grande" solo genera la carga. Resultados en
   `docs/produccion/informe-carga.md`.
