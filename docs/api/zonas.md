# Contrato de API · Zonas y demanda (doc 21)

Base `/api/v1`, mismo sobre de errores (`{"error": {"code", "message", "details"}}`). Coordenadas siempre como
`[lat, lng]` (el orden de Leaflet); el GeoJSON de importar/exportar usa `[lng, lat]` como manda el estándar.

## Ciudades con polígono

`service_areas` (config) sigue siendo la lista de ciudades. Cada ciudad gana `polygon: [[lat, lng], ...] | null`.
Con polígono, una ciudad contiene un punto solo si cae dentro del polígono; la caja (`min_lat`...) se recalcula
sola como el rectángulo que lo encierra (búsquedas y centro siguen funcionando). Sin polígono, se usa la caja
como antes.

`intercity_pairs: [{a, b}]` (config): pares de ciudades entre las que se permiten viajes, en ambos sentidos. Vacío
(por defecto): origen y destino en la misma ciudad, como antes.

`demand` (config): `{enabled: true, window_minutes: 15, hot_requests: 3, notify: true, notify_radius_m: 3000,
notify_every_minutes: 30}`.

## Zonas

`kind`: `surge` (recargo), `restricted` (no se recoge ni se deja), `pickup` (puntos de recogida sugeridos).

```
Zone = {
  id, kind, name, city, polygon: [[lat, lng], ...] (3–300 vértices), active: bool,
  starts_at: datetime | null, ends_at: datetime | null,   // vigencia; null = sin límite
  rules: ZoneRules, created_at, updated_at
}
ZoneRules (según kind, se ignora lo que no aplica):
  surge:      {multiplier: "1.20" (1.00–3.00), days: [0..6] | [] (0 = lunes; vacío = todos),
               start: "HH:MM" | null, end: "HH:MM" | null}     // sin horas = todo el día
  restricted: {pickup: true, dropoff: true, message: {es, en}, points: [Point]}  // points = salidas sugeridas
  pickup:     {points: [Point] (1–20)}
Point = {name, lat, lng}
```

Una zona está vigente si `active` y `starts_at <= ahora < ends_at` (los null no limitan). Solo cuentan las
vigentes. El recargo final es el mayor entre el global (horario o manual) y el de las zonas `surge` vigentes que
contienen el **origen**. Decidido (Carlos, pregunta 1): recargo manual por zona; el automático por demanda queda
para cuando haya datos.

| Método | Ruta | Permiso | Notas |
| --- | --- | --- | --- |
| GET | `/admin/zones` | `zones.view` | `?city&kind` → `Zone[]` (todas, vigentes o no) |
| POST | `/admin/zones` | `zones.manage` | `ZoneWrite` (todo menos id y fechas de registro) → 201 `Zone` |
| GET | `/admin/zones/{id}` | `zones.view` | `Zone` (404 `zone_not_found`) |
| PATCH | `/admin/zones/{id}` | `zones.manage` | Parcial → `Zone` |
| DELETE | `/admin/zones/{id}` | `zones.manage` | 204 |
| GET | `/admin/zones/cities` | `zones.view` | `[{name, polygon, min_lat, max_lat, min_lng, max_lng, center: [lat, lng]}]` |
| PUT | `/admin/zones/cities/{name}` | `zones.manage` | `{polygon: [[lat, lng]...] \| null}` → la ciudad. null vuelve a la caja |
| GET | `/admin/zones/export` | `zones.view` | GeoJSON `FeatureCollection`: ciudades (`properties.kind = "city"`) y zonas |
| POST | `/admin/zones/import` | `zones.manage` | `{geojson: FeatureCollection, replace: bool}` → `{cities, created, updated, skipped: [{index, reason}]}`. Una zona con `properties.id` existente se actualiza; sin id se crea. `replace` borra antes las zonas de las ciudades importadas |
| GET | `/admin/zones/demand` | `live.view` | `DemandSnapshot` con todas las celdas (incluye `drivers`) |
| POST | `/admin/zones/demand/simulate` | `zones.manage` | Solo fuera de producción (404 allí). `{lat, lng, requests (1–200), unmatched (0–200)}` → `DemandSnapshot`. Para probar el mapa en QA |

Errores: `zone_not_found` (404), `city_not_found` (404), `zone_invalid` (422, polígono que se cruza o
`city` desconocida, con `details`), `geojson_invalid` (422).

## Pasajero

`GET /zones/check?lat&lng` (usuario) → antes de cotizar, para el punto de recogida elegido:

```
{
  city: string | null,                       // null: fuera de servicio
  restricted: {zone, message: {es, en}} | null,   // el origen cae en zona restringida para recoger
  suggestion: {name, lat, lng, distance_m, zone} | null,   // punto de recogida más cercano (≤ 1,5 km)
  surge: {multiplier: "1.20", zone} | null   // recargo de zona vigente en ese punto
}
```

`suggestion` aparece si el punto cae en una zona `pickup` (su punto más cercano) o en una `restricted` (el más
cercano entre sus `points` y los de zonas `pickup` a ≤ 1,5 km fuera de zonas restringidas). No aparece si ya se
está a menos de 30 m del punto.

Cotización (`POST /rides/quote`) y pedido (`POST /rides`):

- Origen en zona restringida para recoger: 422 `pickup_restricted`, `details = {zone, suggestion}`.
- Destino en zona restringida para dejar: 422 `dropoff_restricted`, `details = {zone}`.
- Origen y destino en ciudades distintas sin par permitido: 400 `outside_service_area` (como antes).
- `Quote` gana `surge_reason: "zone" | "time" | "manual" | null` (null sin recargo) y `surge_zone: string | null`.
  El recargo cuenta para el tramo de cuota (está dentro de la tarifa).

## Motorizado

Celdas H3 de resolución 8 (~1 km de lado a lado). Por celda se cuentan, en una ventana deslizante de
`window_minutes`: pedidos (`requests`) y pedidos que terminaron sin motorizado (`unmatched`); al calcular se
suman los motorizados conectados (`drivers`). Nunca se envían posiciones de pasajeros. Se recalcula cada minuto.

`level`: 3 = mucha demanda (`requests >= hot_requests` y además pedidos sin motorizado o más del doble de pedidos
que motorizados), 2 = demanda (`requests >= hot_requests`), 1 = algo de demanda (al menos un pedido).

```
DemandCell = {cell, boundary: [[lat, lng] x6], center: [lat, lng], level: 1|2|3, requests, unmatched, name?}
DemandSnapshot = {enabled, updated_at, window_minutes, cells: DemandCell[], hot: {name, level, distance_m, center} | null}
```

`GET /drivers/me/demand?lat&lng` (motorizado aprobado) → `DemandSnapshot` con las celdas a ≤ ~5 km y la
celda caliente más cercana en `hot` (`name` = nombre de la zona que la contiene o el barrio según Photon, p. ej.
"Chacao"). Con `demand.enabled = false` responde `{enabled: false, cells: []}`.

WebSocket: `demand.updated` `{updated_at}` a los motorizados conectados cuando cambia el mapa. La app vuelve a
pedir `/drivers/me/demand` si la capa está activa.

Push (opcional): cuando una celda pasa a nivel 3, los motorizados conectados y libres a ≤ `notify_radius_m`
reciben "Mucha demanda en Chacao" (máximo 1 cada `notify_every_minutes`). `data = {type: "demand", name, lat,
lng}`; abre la pantalla de conducir. Se apaga en preferencias: `demand_alerts` en
`GET/PUT /notifications/preferences` (PUT parcial) (por defecto true).
