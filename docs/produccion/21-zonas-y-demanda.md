# 21 · Zonas y demanda

**Prioridad:** P2 · **Área:** API · Mobile · Admin · **Depende de:** 18, 19

## Objetivo
Llevar a los motorizados adonde está la demanda y fijar reglas por zona (recargos, puntos de recogida,
zonas restringidas), con geografía más precisa que una caja por ciudad.

## Estado actual
- Ciudades como **cajas** (`service_areas`: min/max lat/lng), de 1 a 20; origen y destino en la misma ciudad.
- Recargo por horario (`surge_rules`) y manual global (`surge_manual_multiplier`), no por zona.
- Las maquetas (`mobile-design.md`) proponen que **el motorizado vea en el mapa las zonas con más pedidos**;
  no está construido.

## Alcance
### Incluye
1. **Polígonos** para ciudades y zonas (dibujados en el mapa del admin o importados en GeoJSON), reemplazando las
   cajas sin romper la configuración actual (una caja se convierte en polígono).
2. **Tipos de zona**: ciudad (servicio), recargo, restringida (no se recoge ni se deja, por ejemplo zonas
   peligrosas o aeropuerto si aplica), punto de recogida sugerido (centros comerciales, estaciones de metro).
3. **Mapa de demanda para motorizados**: celdas hexagonales (H3, resolución ~1 km) coloreadas por pedidos de los
   últimos 15 min y pedidos sin motorizado, actualizadas cada minuto. Sin mostrar posiciones de pasajeros.
4. **Recargo por zona y dinámico** (opcional, configurable): multiplicador por zona según relación demanda/oferta
   en tiempo real, con tope y siempre visible para el pasajero antes de pedir. Cuenta para el tramo de cuota
   (decidido para recargos por demanda).
5. **Puntos de recogida**: al pedir dentro de una zona con puntos definidos, la app sugiere el más cercano.
6. **Viajes entre ciudades**: hoy prohibidos; dejar la regla configurable por par de ciudades.

### Fuera
- Rutas con tráfico en tiempo real (OSRM no lo tiene; se evalúa con datos propios de velocidades).

## App móvil
### Motorizado
- Capa "Demanda" en la pantalla de conducir (activable), con leyenda y aviso "Mucha demanda en Chacao".
- Notificación opcional cuando una zona cercana sube de demanda (límite: 1 cada 30 min).
### Pasajero
- Sugerencia de punto de recogida y aviso si el origen está en zona restringida.
- Texto claro cuando hay recargo por zona ("Alta demanda en esta zona: +20 %").

## Admin
- **Zonas**: editor de polígonos sobre Leaflet (dibujar, editar, importar/exportar GeoJSON), tipo, reglas y
  vigencia.
- Mapa de oferta y demanda en vivo (celdas) en la página de viajes en vivo.

## API y datos
- PostGIS (supuesto técnico ya listado en `open-questions.md`) o polígonos en JSONB con comprobación en Python
  (shapely) si se quiere evitar la extensión. Recomendado: PostGIS.
- `zones` (`id`, `kind`, `name`, `area` polígono, `rules` JSONB, `active`, `city_id`).
- Contadores por celda H3 en Redis (pedidos, sin motorizado, motorizados conectados) con ventana deslizante.
- `GET /drivers/me/demand?lat&lng` → celdas cercanas con intensidad; evento WebSocket `demand.updated`.
- La cotización aplica reglas de zona y muestra el motivo del recargo.

## Criterios de aceptación
- Una ciudad definida como polígono rechaza orígenes fuera de él aunque estén dentro de la antigua caja.
- El mapa de demanda refleja un pico simulado de pedidos en menos de 2 minutos.
- Un pedido con origen en zona restringida responde `pickup_restricted` con sugerencia de punto cercano.

## Dependencias
18 (carga del cálculo en tiempo real), 19 (datos históricos de demanda).

## Preguntas para Carlos
1. ~~¿Recargo dinámico automático o solo manual por zona?~~ **Decidido** (2026-10-11, Carlos aprobó las
   recomendaciones): manual por zona al principio. El automático por demanda queda para cuando haya datos.

## Implementación (2026-10-17)
Contrato en [`docs/api/zonas.md`](../api/zonas.md).
- **Polígonos sin PostGIS** (decisión técnica): ciudades y zonas guardan `[[lat, lng], ...]` y se comprueban en
  Python (ray casting), sin instalar la extensión ni shapely. Las ciudades siguen en `service_areas` con un
  `polygon` opcional; una ciudad sin polígono sigue usando su caja.
- App `api/apps/zones`: tabla `zones` (recargo, restringida, punto de recogida) con vigencia, caché en Redis,
  importar/exportar GeoJSON y permisos `zones.view`/`zones.manage` (rol Operaciones).
- Cotización y pedido: `pickup_restricted` (con sugerencia), `dropoff_restricted`, recargo por zona con su motivo
  (`surge_reason`, `surge_zone`) y viajes entre ciudades según `intercity_pairs`.
- Demanda: celdas H3 de resolución 8 contadas en Redis (pedidos y sin motorizado, ventana de 15 min), mapa
  recalculado cada minuto por el worker, evento `demand.updated` y aviso push "Mucha demanda en …" (máximo 1
  cada 30 min, se apaga en preferencias). Nombre de la zona o del barrio vía Photon.
- Admin: página Zonas (editor de polígonos, reglas, vigencia, GeoJSON, simulador de picos fuera de producción)
  y capa de demanda en Viajes en vivo.
- App: capa Demanda en conducir con leyenda y aviso; aviso de zona restringida, punto sugerido y texto del
  recargo por zona para el pasajero.
