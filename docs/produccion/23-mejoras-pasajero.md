# 23 · Mejoras para el pasajero

**Prioridad:** P2 · **Área:** Mobile · API · **Depende de:** nada

## Objetivo
Hacer que pedir sea todavía más rápido y útil en el día a día, con funciones que el pasajero espera de una app
de primer nivel y que no requieren costos de operación.

## Estado actual
- Buscar destino con Photon, fijar en el mapa, cotizar con equivalente en Bs (BCV y Binance), elegir método de
  pago y pago preferido, historial con recibos y **lugares frecuentes calculados** desde los viajes.
- No hay lugares guardados con nombre (Casa, Trabajo), ni pedir para otra persona, ni programar, ni paradas.

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
1. ¿Programar viajes entra? Recomendado: no al lanzar; medir primero.
