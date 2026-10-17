# 23 · Mejoras para el pasajero

**Prioridad:** P2 · **Área:** Mobile · API · **Depende de:** nada

## Objetivo
Hacer que pedir sea todavía más rápido y útil en el día a día, con funciones que el pasajero espera de una app
de primer nivel y que no requieren costos de operación.

## Estado actual
- Buscar destino con Photon, fijar en el mapa, cotizar con equivalente en Bs (BCV y Binance), elegir método de
  pago y pago preferido, historial con recibos y **lugares frecuentes calculados** desde los viajes.
- ~~No hay lugares guardados con nombre (Casa, Trabajo), ni pedir para otra persona, ni programar, ni
  paradas.~~ Hecho en 2026-10-17 salvo programar (decidido: no) y paradas (fuera). Ver Implementación.

## Alcance
### Incluye
1. **Lugares guardados**: Casa, Trabajo y otros con nombre e ícono; aparecen primero en la búsqueda y en el
   inicio. Se pueden crear desde un viaje del historial o desde el mapa.
2. **Pedir para otra persona**: nombre y teléfono del pasajero real; el motorizado ve ese nombre; el enlace de
   viaje en vivo (11) se envía a esa persona por WhatsApp.
3. **Notas para el motorizado** al pedir ("estoy en la puerta del edificio azul"), máximo 140 caracteres.
4. **Repetir viaje** desde el historial con un toque (misma ruta, nueva cotización).
5. **Recibo compartible** del viaje (imagen o PDF con ruta, precio en USD y Bs, método de pago acordado), útil
   para empresas que reembolsan.
6. **Programar viaje** (supuesto, evaluar demanda primero): pedir para dentro de 30 min a 7 días; la búsqueda
   empieza 10 min antes. Riesgo: sin garantía de motorizado; se comunica como "intentaremos".
7. **Calificación con propina simbólica**: no aplica (pagos fuera de la app); en su lugar, "cumplidos" al
   motorizado (insignias como "Muy amable", "Casco limpio") visibles en su perfil.

### Fuera
- Paradas múltiples (más complejidad de precio; evaluar con datos).
- Viajes compartidos entre pasajeros (no aplica a moto).

## App móvil
### Pasajero
- Inicio: accesos rápidos a Casa y Trabajo; búsqueda con guardados arriba.
- Hoja de pedido: "¿Para quién es?" y "Nota para el motorizado".
- Historial: "Repetir" y "Compartir recibo".
### Motorizado
- La oferta y el viaje muestran la nota y el nombre de quien viaja si es para otra persona.
- Perfil: insignias recibidas.

## Admin
- Detalle del viaje: nota, pasajero real (si es para otra persona).

## API y datos
- `saved_places` (`user_id`, `label`, `kind` home|work|other, `lat`, `lng`, `address`, `position`).
- `rides.rider_name`, `rides.rider_phone`, `rides.note`.
- `ratings.tags` ya existe; se reutiliza para insignias y se agrega el conteo por etiqueta en el perfil.
- `GET/POST/PATCH/DELETE /places`, `GET /rides/{id}/receipt`.
- Programados: `rides.scheduled_for` y estado `scheduled`, con el despacho iniciando a la hora indicada (solo si
  se aprueba el punto 6).

## Criterios de aceptación
- Pedir a Casa desde el inicio toma 2 toques más la confirmación.
- El motorizado ve la nota y el nombre de quien viaja antes de aceptar.
- El recibo compartido muestra precio en USD y Bs con la tasa congelada del viaje.

## Dependencias
11 para enviar el enlace en vivo a la persona que viaja.

## Preguntas para Carlos
1. ~~¿Programar viajes entra?~~ **Decidido** (2026-10-11, Carlos aprobó las recomendaciones): no al lanzar;
   medir primero. El punto 6 queda fuera.

## Implementación (2026-10-17)
Contrato en [`docs/api/mejoras-pasajero.md`](../api/mejoras-pasajero.md).
- **Lugares guardados**: parte de lo que ya existía (`da5bb1e`: Casa, Trabajo y hasta 10 más, buscador con
  guardados arriba). Se suma el ícono de los "otros" (8 a elegir), accesos de un toque en el inicio (Casa →
  precio → Pedir; los que faltan invitan a agregarlos), guardar desde un viaje del historial y fijar el punto
  en el mapa. El orden queda fijo (Casa, Trabajo, luego por fecha), así que no hizo falta `position`.
- **Pedir para otra persona**: `rides.rider_name` y `rides.rider_phone`; los contactos de confianza se eligen
  con un toque. El motorizado ve "Viaja: María" en la oferta y en el viaje, nunca el teléfono. Con el motorizado
  asignado, el pasajero envía por WhatsApp un enlace en vivo para quien viaja (`for_rider`) que además muestra el
  PIN de inicio.
- **Nota para el motorizado** (`rides.note`, 140 caracteres) en la oferta, el viaje, el detalle y el admin.
- **Repetir** desde el historial y el detalle: misma ruta, precio nuevo. "Intentar de nuevo" conserva nota y
  persona.
- **Recibo compartible**: imagen PNG generada en la API (con la fuente de la app) detrás de un enlace firmado,
  con ruta, total en USD y en Bs a la tasa congelada, método de pago acordado y "no es factura fiscal". Se
  comparte con texto desde el historial (pasajero y motorizado). Sin módulos nativos nuevos: sale por OTA.
- **Cumplidos**: las etiquetas de la calificación (`ratings.tags`) se cuentan en `GET /drivers/me/stats`
  (sin las calificaciones ignoradas por el doc 16) y se muestran como insignias en el perfil del motorizado.
- Privacidad: quien viaja, su teléfono y la nota se borran a los 180 días (como la ruta) y al eliminar la
  cuenta del pasajero; salen en "Descargar mis datos".
