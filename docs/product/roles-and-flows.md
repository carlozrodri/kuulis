# Roles y flujos

## Roles
| Rol | Decidido | Qué hace |
| --- | --- | --- |
| Cliente (pasajero) | Sí | Pide un viaje y ve su costo en dólares |
| Motorizado (conductor) | Sí | Espera que le llegue la solicitud de un viaje y la atiende |
| Admin / staff | Supuesto (el panel ya existe en la plantilla) | Aprueba motorizados, ve viajes, gestiona suscripciones y soporte |

Supuesto: una misma persona podría tener cuenta de pasajero y de motorizado (dos perfiles en una cuenta).

## Flujo del pasajero (decidido: pedir y ver costo en USD; el detalle es supuesto)
1. Abre la app y ve el mapa con su ubicación.
2. Elige destino (búsqueda o pin en el mapa).
3. Ve el **precio en dólares** (fijado por Kuulis, no negociable), la distancia y el tiempo estimado.
4. Confirma y pide el viaje.
5. Ve "buscando motorizado"; cuando uno acepta, ve su nombre, foto, moto, placa y ubicación en vivo.
6. El motorizado llega, empieza el viaje y el pasajero lo sigue en el mapa.
7. Llega al destino y **paga directamente al motorizado** el monto de la app, con el método que acordaron.
8. Califica al motorizado.

## Flujo del motorizado (decidido: esperar la solicitud; el detalle es supuesto)
1. Se registra y envía sus datos (cédula, licencia, moto, placa, foto). El admin lo aprueba.
2. Se pone **disponible**.
3. **Le llega la solicitud** con origen, destino y precio; la acepta o la rechaza en un tiempo límite.
4. Va a buscar al pasajero, inicia el viaje y lo termina.
5. Recibe el pago directo del pasajero.
6. Ve sus ganancias del mes y la cuota que le toca según los tramos.
7. Recarga su **billetera** con USDT (mínimo 5) y la cuota se descuenta de ahí (detalles en `business-model.md`).
8. El día 1 se cobra la cuota del mes anterior. Si el saldo no alcanza, tiene 1 semana de gracia; después deja de recibir viajes hasta pagar.
9. Puede transferir saldo a otro motorizado, pero no retirarlo.

## Flujo del admin (supuesto)
- Aprobar o rechazar motorizados.
- Ver viajes en curso y el historial.
- Ver ganancias y cuotas por motorizado; marcar pagos de suscripción.
- Atender reportes y suspender cuentas.

## Tipos de vehículo (decidido)
Al lanzamiento solo **motos**; **carros** después. Requisito: el modelo de datos admite varios tipos de
vehículo desde el inicio (tipo de vehículo en el motorizado, en la solicitud y en la tarifa), aunque la app
solo muestre motos. Así agregar carros es configuración y pantallas, no una migración grande.

## Qué reutiliza de la plantilla
Auth con roles, usuarios, notificaciones push y en tiempo real (WebSocket), subida de archivos (documentos
del motorizado), emails, panel admin y despliegue. Falta construir: mapas y geolocalización, cálculo de
precio, emparejamiento pasajero-motorizado, estados del viaje, calificaciones y suscripciones.
