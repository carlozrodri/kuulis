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
3. Ve el **precio en dólares** (fijado por Kuulis, no negociable) y, debajo, su equivalente en bolívares a
   tasa **BCV** y a tasa **Binance**, además de la distancia y el tiempo estimado.
4. Confirma y pide el viaje.
5. Ve "buscando motorizado"; cuando uno acepta, ve su nombre, foto, moto, placa y ubicación en vivo.
6. El motorizado llega, empieza el viaje y el pasajero lo sigue en el mapa.
7. Llega al destino y **paga directamente al motorizado** el monto de la app, con el método que acordaron.
8. **Califica al motorizado (obligatorio)** antes de poder pedir otro viaje.

## Flujo del motorizado (decidido: esperar la solicitud; el detalle es supuesto)
1. Se registra y envía sus documentos (ver "Requisitos del motorizado"). El admin lo aprueba a mano.
2. Se pone **disponible**.
3. **Le llega la solicitud** con origen, destino y precio; la acepta o la rechaza en un tiempo límite.
4. Va a buscar al pasajero, inicia el viaje y lo termina.
5. Recibe el pago directo del pasajero y **califica al pasajero (obligatorio)**.
6. Ve sus ganancias del mes y la cuota que le toca según los tramos.
7. Recarga su **billetera** con USDT (mínimo 5) y la cuota se descuenta de ahí (detalles en `business-model.md`).
8. El día 1 se cobra la cuota del mes anterior. Si el saldo no alcanza, tiene 1 semana de gracia; después deja de recibir viajes hasta pagar.
9. Puede transferir saldo a otro motorizado, pero no retirarlo.

## Requisitos del motorizado (decidido)
Requisitos previos: **21 años o más** y moto **año 2013 o más nueva** (ambos configurables desde el admin).

Para ser aprobado sube, desde la app:
- Cédula de identidad.
- **RIF** (en Venezuela).
- Licencia de conducir.
- **Certificado médico** vigente.
- Carnet de circulación de la moto.
- Selfie (para comparar con la cédula).
- Fotos de la moto con la placa visible.

La aprobación es **manual desde el admin**. Supuesto: el admin puede rechazar con un motivo y el motorizado
corrige y reenvía; los documentos se guardan en el S3 privado con URLs firmadas. Si el lanzamiento es en otro
país, la lista de documentos debe ser configurable por país (el RIF solo aplica a Venezuela).

## Inicio de sesión (decidido)
- **Email y contraseña, y Google.** Sin login por teléfono, porque cada SMS cuesta.
- **Iniciar sesión con Apple solo en iOS**, porque Apple lo exige si la app ofrece Google (guía 4.8 de la
  App Store). Es gratis.

## Comunicación y confianza (decidido)
- **Chat dentro de la app** entre pasajero y motorizado, solo mientras el viaje está activo. Va por el WebSocket
  que ya existe en la plantilla, así que no tiene costo extra. Supuesto: mensajes rápidos predefinidos
  ("Ya llegué", "Voy en camino") para no escribir manejando, y el historial queda guardado para soporte.
- **Calificación obligatoria** de ambos lados (1 a 5 estrellas y comentario opcional). Supuesto: si alguien no
  califica, la app se lo pide al abrirla y no deja pedir ni aceptar otro viaje hasta hacerlo.
- **Llamadas: fuera del lanzamiento.** Las llamadas con número enmascarado necesitan un proveedor telefónico
  (Twilio y similares), que cobra por minuto y por número, y en Venezuela es caro y poco fiable. No van, para
  mantener el costo de operación muy bajo. Alternativa futura sin costo por minuto: llamada de voz dentro de la
  app (WebRTC) con un servidor TURN propio en la infraestructura de Carlos.

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
precio, emparejamiento pasajero-motorizado, estados del viaje, chat, calificaciones, tasas de cambio y suscripciones.
