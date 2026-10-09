# Contrato de API · Fase 1B (viajes)

Base `/api/v1`, mismo sobre de errores que la 1A. Coordenadas en grados decimales (`lat`, `lng`).
Montos en USD con 2 decimales, como string decimal (`"2.40"`). Distancias en metros, duraciones en segundos.
Los textos de error no se traducen en la API: los clientes traducen por `code`.

## Configuración nueva (`AppConfig`, editable en el admin)

| Clave | Defecto | Descripción |
| --- | --- | --- |
| `fares` | `{"moto": {"base": "0.80", "per_km": "0.35", "per_minute": "0.05", "minimum": "1.50"}, "car": {"base": "1.50", "per_km": "0.60", "per_minute": "0.08", "minimum": "2.50"}}` | Tarifa por tipo (valores de ejemplo, Carlos los ajusta) |
| `surge_rules` | `[]` | Lista `{days: [0-6], start: "HH:MM", end: "HH:MM", multiplier: "1.20"}` en hora de Caracas (0 = lunes) |
| `surge_manual_multiplier` | `"1.00"` | Recargo manual global (demanda alta), 1.00–3.00 |
| `fare_rounding` | `"0.10"` | Redondeo hacia arriba del precio final |
| `payment_methods` | `["cash_usd", "pago_movil", "binance", "zelle", "cash_ves"]` | Métodos que el pasajero puede elegir |
| `service_areas` | `[{"name": "Caracas", "min_lat": 10.35, "max_lat": 10.56, "min_lng": -67.10, "max_lng": -66.70}]` | Una caja por ciudad (1 a 20). Fuera de ellas no hay viajes y el origen y el destino deben caer en la misma ciudad. Reemplaza al antiguo `service_area` (si quedó guardado, se lee como Caracas) |
| `offer_timeout_seconds` | `15` | Tiempo que tiene el motorizado para aceptar |
| `search_radius_m` | `[2000, 4000, 7000]` | Radios de búsqueda sucesivos |
| `search_timeout_seconds` | `180` | Tiempo máximo buscando antes de `no_drivers` |
| `quote_ttl_seconds` | `300` | Vigencia de una cotización |

Precio = max(`minimum`, `base` + `per_km` × km + `per_minute` × min) × recargo (el mayor entre la regla horaria
vigente y el manual), redondeado hacia arriba a `fare_rounding`.

## Geografía

Proveedores configurables por variables de entorno: `OSRM_URL` (rutas) y `PHOTON_URL` (búsqueda de
direcciones). En QA se usan los servidores públicos de demostración; antes del lanzamiento se alojan en Coolify.
Si no hay `OSRM_URL`, la ruta se estima con distancia en línea recta × 1,3 a 22 km/h y sin `polyline`.

| Método | Ruta | Parámetros | Respuesta |
| --- | --- | --- | --- |
| GET | `/geo/search` | `q`, `lat?`, `lng?` | `[{name, address, lat, lng}]` limitado a la ciudad que contiene `lat/lng` (la primera si no hay) |
| GET | `/geo/reverse` | `lat`, `lng` | `{name, address, lat, lng}` |

## Cotizar y pedir (pasajero)

`Place = {lat, lng, address}`

| Método | Ruta | Cuerpo | Respuesta |
| --- | --- | --- | --- |
| POST | `/rides/quote` | `{pickup: Place, dropoff: Place, vehicle_type}` | `Quote` |
| POST | `/rides` | `{quote_id, payment_method}` | `Ride` (201, estado `searching`) |
| GET | `/rides/active` | | `Ride` o `null` (para pasajero o motorizado) |
| GET | `/rides/pending-rating` | | `Ride` o `null` (el viaje que falta calificar) |
| GET | `/rides` | `?role=passenger\|driver&limit&offset` | Paginado `{items, total, limit, offset}` |
| GET | `/rides/{id}` | | `Ride` (solo participantes) |
| POST | `/rides/{id}/cancel` | `{reason?}` | `Ride` |

`Quote = {quote_id, vehicle_type, pickup, dropoff, distance_m, duration_s, fare: "2.40", surge_multiplier: "1.00", polyline: str|null, expires_at}`

Errores al pedir: `quote_expired` (400), `outside_service_area` (400), `payment_method_invalid` (400),
`ride_already_active` (409), `rating_required` (409, con `details.ride_id`).

## Motorizado

| Método | Ruta | Cuerpo | Notas |
| --- | --- | --- | --- |
| POST | `/drivers/me/online` | `{lat, lng}` | Solo `approved`; si no, 403 `driver_not_approved` |
| POST | `/drivers/me/offline` | | No permitido con viaje activo (409 `ride_active`) |
| GET | `/drivers/me/state` | | `{online: bool, active_ride_id, current_offer: Offer\|null}` |
| POST | `/rides/{id}/accept` | | 409 `offer_expired` o `ride_taken` si ya no aplica |
| POST | `/rides/{id}/decline` | | Pasa al siguiente motorizado |
| POST | `/rides/{id}/arrive` | | `driver_assigned` → `driver_arrived` |
| POST | `/rides/{id}/start` | | `driver_arrived` → `in_progress` |
| POST | `/rides/{id}/complete` | | `in_progress` → `completed`; fija `first_trip_completed_at` si es el primero |

Ubicación en vivo por WebSocket (`/ws`, ya autenticado): el motorizado envía
`{"type": "location", "lat", "lng", "heading"?, "speed"?}` cada 3–5 s mientras está conectado. Si no llega
ubicación en 60 s deja de recibir ofertas. Durante un viaje la ubicación se reenvía al pasajero.

`Offer = {ride_id, pickup, dropoff, distance_m, duration_s, pickup_distance_m, pickup_eta_s, fare, payment_method, passenger: {first_name, rating}, expires_at}`

## Estados del viaje

`searching` → `driver_assigned` → `driver_arrived` → `in_progress` → `completed`.
Salidas: `cancelled_by_passenger` (desde `searching`, `driver_assigned`, `driver_arrived`),
`cancelled_by_driver` (desde `driver_assigned`, `driver_arrived`) y `no_drivers` (búsqueda agotada).

`Ride = {id, status, vehicle_type, pickup, dropoff, distance_m, duration_s, fare, surge_multiplier, payment_method,
polyline, passenger: {id, first_name, rating}, driver: {id, first_name, rating, photo_url, vehicle: {brand, model,
color, plate}} | null, driver_location: {lat, lng, heading} | null, requested_at, assigned_at, arrived_at,
started_at, completed_at, cancelled_at, cancel_reason, my_rating: Rating | null}`

## Chat del viaje

| Método | Ruta | Cuerpo | Notas |
| --- | --- | --- | --- |
| GET | `/rides/{id}/messages` | | Lista ordenada |
| POST | `/rides/{id}/messages` | `{text}` (1–500) | Solo participantes y solo con el viaje en `driver_assigned`, `driver_arrived` o `in_progress` (409 `chat_closed`) |

`Message = {id, ride_id, sender_id, text, created_at}`

## Calificaciones

| Método | Ruta | Cuerpo |
| --- | --- | --- |
| POST | `/rides/{id}/rating` | `{stars: 1-5, tags: [str], comment?: str}` |

Solo tras `completed`, una vez por participante. Mientras un pasajero tenga un viaje completado sin calificar no
puede pedir otro; mientras un motorizado lo tenga no recibe ofertas. Promedios en `rating_avg` y
`rating_count` (por usuario y por rol). Etiquetas sugeridas para el pasajero: `safe_driving`, `on_time`,
`friendly`, `clean_helmet`; para el motorizado: `on_time`, `respectful`, `ready_at_pickup`.

## Eventos WebSocket (servidor → cliente)

| Evento | Para | `data` |
| --- | --- | --- |
| `ride.offer` | motorizado | `Offer` |
| `ride.offer_cancelled` | motorizado | `{ride_id}` |
| `ride.updated` | ambos | `Ride` |
| `ride.driver_location` | pasajero | `{ride_id, lat, lng, heading}` |
| `ride.message` | ambos | `Message` |

Las ofertas y los cambios de estado también envían push (por si la app está en segundo plano).

## Admin (staff)

| Método | Ruta | Notas |
| --- | --- | --- |
| GET | `/admin/rides` | `?status&q&date_from&date_to&limit&offset` |
| GET | `/admin/rides/{id}` | `Ride` + mensajes + calificaciones + historial de ofertas |
| GET | `/admin/rides/live` | Viajes activos con posición del motorizado |
| GET | `/admin/drivers/online` | `[{driver_id, name, lat, lng, last_seen_at, active_ride_id}]` |
| POST | `/admin/rides/{id}/cancel` | `{reason}` |
