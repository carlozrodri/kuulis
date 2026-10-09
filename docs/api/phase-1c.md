# Contrato de API · Fase 1C (tasas y promociones)

Base `/api/v1`, mismo sobre de errores. Montos en USD como string con 2 decimales. Montos en bolívares
también como string con 2 decimales (`"2101.56"`); las tasas, en Bs por 1 USD con 2 decimales.

## Tasas de cambio

Dos fuentes: `bcv` (oficial) y `binance` (P2P USDT/VES). El worker las consulta solo:

| Fuente | Origen por defecto (variable de entorno) | Frecuencia |
| --- | --- | --- |
| `bcv` | `RATES_BCV_URL` = `https://ve.dolarapi.com/v1/dolares/oficial` (promedio publicado por el BCV) | cada 60 min |
| `binance` | `RATES_BINANCE_URL` = búsqueda pública de anuncios P2P de Binance; mediana de los 10 primeros anuncios de compra de USDT con VES | cada 15 min |

Cada consulta correcta se guarda en Redis (tasa vigente) y en el historial de Postgres. Si una fuente falla se
mantiene la última tasa válida. `RATES_ENABLED=false` apaga las consultas (pruebas y desarrollo).

`ExchangeRate = {source, rate: "875.65", origin: "auto" | "manual", as_of, fetched_at, stale: bool}`
- `as_of`: fecha de la tasa según la fuente; `fetched_at`: cuándo la guardó Kuulis.
- `stale`: la tasa es más vieja que `rates_stale_minutes[source]` (configuración).

`VesAmount = {bcv: "2101.56" | null, binance: "2520.00" | null}` (null si no hay tasa).

| Método | Ruta | Quién | Respuesta |
| --- | --- | --- | --- |
| GET | `/rates` | cualquiera | `{bcv: ExchangeRate \| null, binance: ExchangeRate \| null}` |
| GET | `/admin/rates/history` | staff | `?source&limit&offset` → paginado de `{id, source, rate, origin, as_of, fetched_at, created_by: {id, name} \| null, note}` |
| POST | `/admin/rates` | admin | `{source, rate, note?}` → `ExchangeRate` (corrección manual) |
| POST | `/admin/rates/refresh` | admin | `{source?}` → `{bcv, binance}`; consulta las fuentes ya |

Una tasa manual queda vigente `rates_manual_hold_hours` horas: mientras tanto el worker sigue consultando pero no
la reemplaza. Pasado ese plazo, la siguiente consulta automática correcta la reemplaza.

## Configuración nueva (`AppConfig`)

| Clave | Defecto | Descripción |
| --- | --- | --- |
| `rates_stale_minutes` | `{"bcv": 2160, "binance": 120}` | Edad a partir de la cual el admin avisa que la tasa está vieja (36 h y 2 h) |
| `rates_manual_hold_hours` | `6` | Horas que una tasa manual no se reemplaza (1–168) |
| `promo_pair_alert_threshold` | `3` | Viajes con promoción entre el mismo pasajero y motorizado que disparan una alerta |
| `promo_pair_alert_days` | `30` | Ventana de días para esa alerta |

## Promociones

Kuulis asume el descuento: el pasajero paga `total = fare − discount` al motorizado y, cuando el viaje se
completa, Kuulis acredita `discount` en la billetera del motorizado.

`Promotion`:
```json
{
  "id": "uuid", "name": "Bienvenida", "description": null,
  "code": "HOLA" | null,
  "discount_type": "percent" | "fixed", "discount_value": "20.00", "max_discount": "2.00" | null,
  "min_fare": "0.00",
  "starts_at": "...", "ends_at": "...",
  "budget": "100.00", "max_uses_per_passenger": 1, "max_total_uses": null,
  "first_ride_only": false, "service_areas": ["Caracas"], "vehicle_types": ["moto"],
  "is_active": true, "status": "active" | "scheduled" | "ended" | "exhausted" | "inactive",
  "stats": {"uses": 12, "completed": 10, "credited": "8.40", "reserved": "1.20", "remaining": "90.40"},
  "created_at": "...", "updated_at": "..."
}
```
- `code` vacío = promoción automática (se aplica sin código). Los códigos se guardan en mayúsculas y son únicos.
- `percent`: `discount_value` de 1 a 100, con tope opcional `max_discount`. `fixed`: monto fijo.
- El descuento nunca supera la tarifa; se redondea al centavo.
- `service_areas` y `vehicle_types` vacíos = todas.
- Presupuesto: `reserved` (viajes en curso con la promoción) + `credited` (completados) no puede pasar de
  `budget`. Un viaje cancelado o sin motorizado libera lo reservado.
- `uses` cuenta viajes en curso y completados; con eso se aplican `max_uses_per_passenger` y `max_total_uses`.
- `first_ride_only`: solo si el pasajero no tiene viajes completados.

| Método | Ruta | Quién | Notas |
| --- | --- | --- | --- |
| GET | `/admin/promotions` | staff | `?status&q&limit&offset`, paginado |
| POST | `/admin/promotions` | admin | Cuerpo = `Promotion` sin `id`, `status`, `stats` ni fechas de auditoría |
| GET | `/admin/promotions/{id}` | staff | `Promotion` |
| PATCH | `/admin/promotions/{id}` | admin | Parcial. El presupuesto no puede bajar de lo ya comprometido (`budget_below_committed`) |
| GET | `/admin/promotions/{id}/rides` | staff | Paginado de `{ride_id, status, passenger_name, driver_name, fare, discount, total, requested_at, completed_at}` |
| GET | `/admin/promotions/alerts` | staff | Pares con `promo_pair_alert_threshold` o más viajes con promoción en `promo_pair_alert_days` días: `[{passenger: {id, name, email}, driver: {id, name, email, profile_id}, rides, discount_total, last_ride_at}]` |

Errores: `promotion_code_taken` (409), `validation_error` (422).

## Cambios en la cotización y el viaje

`QuoteRequest` acepta `promo_code?` (se ignoran mayúsculas y espacios).

`Quote` agrega:
- `discount: "0.60"`, `total: "1.80"` (lo que paga el pasajero), `promotion: {id, name, code} | null`
- `total_ves: VesAmount`

Sin `promo_code`, se aplica la promoción automática con mayor descuento para la que el pasajero califique.
Con un código que no sirve la cotización responde 400 `promotion_invalid` con
`details.reason` = `not_found` | `not_started` | `ended` | `exhausted` | `max_uses` | `first_ride_only` |
`not_eligible` (zona, vehículo o tarifa mínima).

Al pedir el viaje (`POST /rides`) se vuelve a validar con la promoción bloqueada: si se agotó entre la
cotización y el pedido responde 409 `promotion_unavailable` y la app debe cotizar de nuevo.

`Ride` (y la vista admin) agrega `discount`, `total`, `promotion: {id, name, code} | null`,
`rates: {bcv: "875.65" | null, binance: "1004.00" | null}` (congeladas al pedir) y `total_ves: VesAmount`.

`Offer` agrega `discount`, `total` y `total_ves`. El motorizado cobra `total`; `discount` es lo que Kuulis le
acredita al completar.

## Billetera (solo lectura en la 1C)

| Método | Ruta | Respuesta |
| --- | --- | --- |
| GET | `/wallet/me` | `{balance: "0.60", currency: "USDT"}` |
| GET | `/wallet/me/entries` | Paginado de `{id, kind, amount, balance_after, ride_id, description, details, created_at}`, más nuevos primero |

`kind` en la 1C: `promo_credit` (positivo). Para `promo_credit`, `description` es el nombre de la promoción y
`details = {passenger_name: "Ana M."}`; la app arma el texto en su idioma. Al acreditar se envía push y queda en la bandeja del motorizado.
La 1D agrega recargas, transferencias y cuotas.
