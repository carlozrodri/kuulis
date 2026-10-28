# Caracas en movimiento (actividad pública)

Producto: [docs/product/wow/01-mapa-vivo.md](../product/wow/01-mapa-vivo.md), parte B. Solo viajes reales.

## `GET /api/v1/public/rides/activity`

Sin login. Caché de 30 s en Redis (y `Cache-Control: public, max-age=30`). Límite: 60/min por IP.

```json
{
  "live": true,
  "threshold": 3,
  "trips_last_hour": 7,
  "verified_drivers": 12,
  "in_progress": [{ "id": "3f9a0c1b2d4e", "lat": 10.4964, "lng": -66.8628, "distance_m": 3400, "fare": "1.80" }],
  "recent": [{ "minutes_ago": 10, "distance_m": 3400, "fare": "1.80" }],
  "updated_at": "2026-10-28T21:00:00Z"
}
```

- `live` es `false` cuando está apagado en el admin o cuando hubo menos de `threshold` viajes reales empezados
  en la última hora. Entonces `in_progress` y `recent` vienen vacíos y la app muestra el mensaje honesto con
  `verified_drivers` (motorizados aprobados, sin cuentas de prueba).
- Cuentan solo viajes entre cuentas reales (`is_test_account = false` en pasajero y motorizado) y de
  motorizados que no se ocultaron.
- `in_progress`: viajes `in_progress` empezados hace más de 3 min. La posición es donde la ruta planificada
  dice que iba **hace 3 minutos**, nunca en el primer ni en el último 15 % del viaje, redondeada a una
  cuadrícula de ~200 m. `id` es anónimo y cambia cada hora (sirve para que la moto se deslice en la app).
- `recent`: hasta 8 viajes terminados hace entre 5 min y 2 h, con `minutes_ago` en pasos de 5 minutos.
- Nunca hay nombres, fotos, placas, teléfonos, direcciones ni ids reales. `fare` es lo que paga el pasajero
  (tarifa menos descuento), todo para el motorizado.

## Ajustes (admin → Ajustes → Caracas en movimiento)

| Clave | Por defecto | Qué hace |
| --- | --- | --- |
| `public_activity_enabled` | `true` | Apagado, `live` siempre es `false` |
| `public_activity_min_trips_per_hour` | `3` | Umbral de viajes reales en la última hora (1‑500) |

## Motorizado: no aparecer

`PATCH /api/v1/drivers/me/preferences` con `{"hide_from_public_activity": true}` devuelve el perfil
(`DriverProfileRead.hide_from_public_activity`). En la app: Perfil → Ajustes → Privacidad → "Mostrar mis
viajes en el mapa público".
