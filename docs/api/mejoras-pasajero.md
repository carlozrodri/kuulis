# Contrato de API · Mejoras para el pasajero (doc 23)

Base `/api/v1`, mismo sobre de errores (`{"error": {"code", "message", "details"}}`). Montos como texto con dos
decimales (`"3.00"`). Programar viajes no entra (decidido: medir primero).

## Pedir para otra persona y nota para el motorizado

`POST /rides` acepta dos campos opcionales (las apps viejas siguen funcionando sin ellos):

```
RideCreate = {
  quote_id, payment_method,
  note?: string | null,                      // ≤ 140; espacios y saltos de línea se compactan; "" → null
  rider?: { name: string, phone: string }    // name 1–60; phone E.164 ("+584141112233")
}
```

`RideRead` (y `ride.updated`) suma:

| Campo | Quién lo recibe |
| --- | --- |
| `note` | pasajero, motorizado y admin |
| `rider_name` | pasajero, motorizado y admin |
| `rider_phone` | solo el pasajero que pidió y el admin (`null` para el motorizado) |

La oferta (`ride.offer`, `GET /drivers/me/state`) suma `note` y `rider_name`, así el motorizado los ve antes de
aceptar. "Intentar de nuevo" en la app repite nota y persona.

### Enlace en vivo para quien viaja

`POST /rides/{id}/share` acepta el cuerpo opcional `{"for_rider": true}` (solo el pasajero de un viaje pedido para
otra persona; si no, `409 ride_not_for_rider`). La página `/v/{token}` de ese enlace (`GET
/public/rides/shared/{token}`) devuelve además:

```
for_rider: true,
start_pin: "4821" | null,     // hasta que empieza el viaje; nunca en los enlaces normales
passenger.first_name          // el nombre de quien viaja
```

## Recibo compartible

`GET /rides/{id}/receipt` (participantes; `409 receipt_unavailable` si el viaje no terminó):

```
RideReceipt = {
  ride_id, number: "3F9A1C2B",           // inicio del id, para citarlo en soporte
  completed_at, pickup_address, dropoff_address, distance_m, duration_s,
  fare, discount, total,                 // USD
  rates: { bcv, binance },               // tasas congeladas del viaje
  total_ves: { bcv, binance },
  payment_method,                        // el acordado con el motorizado
  passenger_name,                        // quien viajó (rider_name si fue para otra persona)
  driver_name, plate,
  image_url                              // PNG firmado, en el idioma del usuario
}
```

`GET /public/rides/receipts/{token}.png` (sin login): la imagen 1080 px de ancho. El token es el id del viaje, el
idioma (`es`/`en`) y un HMAC con `SECRET_KEY`; uno alterado o de un viaje no terminado responde `404
receipt_not_found`. La imagen dice que Kuulis no cobra el viaje y que no es una factura fiscal.

## Lugares guardados

`/users/me/places` suma `icon` para los lugares `other`: `star` (por defecto), `heart`, `dumbbell`, `school`,
`store`, `users`, `utensils`, `hospital`. En Casa y Trabajo se ignora (siempre `null`). Otro valor: 422.

## Cumplidos

`GET /drivers/me/stats` suma `compliments: [{tag, count}]`: cuántas veces los pasajeros dieron cada etiqueta
(`safe_driving`, `on_time`, `friendly`, `clean_helmet`), de mayor a menor. No cuentan las calificaciones
ignoradas por antifraude (doc 16).

## Privacidad

`rider_name`, `rider_phone` y `note` se borran a los 180 días (salvo que el viaje tenga un reporte) y al eliminar
la cuenta del pasajero, y salen en "Descargar mis datos" del pasajero.
