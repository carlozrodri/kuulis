# 26 · Llamadas dentro de la app

**Prioridad:** P3 · **Área:** Mobile · API · Infra · **Depende de:** 02

## Objetivo
Permitir que pasajero y motorizado hablen por voz durante el viaje **sin compartir sus números** y sin costo por
minuto, como alternativa a las llamadas enmascaradas (descartadas por costo, decidido en
`roles-and-flows.md`).

## Estado actual
- Sin llamadas. Comunicación solo por chat del viaje con mensajes rápidos.
- La alternativa futura ya está nombrada en los documentos de producto: WebRTC con un servidor TURN propio.

## Alcance
### Incluye
1. **Llamada de voz WebRTC** (solo audio) entre los dos participantes de un viaje activo, con señalización por
   el WebSocket existente.
2. **Servidor TURN/STUN propio** (`coturn`) en Coolify con credenciales temporales por llamada; puerto UDP
   expuesto en el servidor (requiere abrir puertos en el router del homelab o usar el VPS de contingencia).
3. **Llamada entrante con la app en segundo plano** en Android: notificación de pantalla completa (canal de
   14); en la PWA, solo con la app abierta.
4. **Límites**: solo entre `driver_assigned` y 10 min después de completar; duración máxima 5 min; registro de
   llamadas (sin grabar audio) para soporte.

### Fuera
- Grabación de llamadas. Videollamadas. Llamadas con soporte.

## App móvil
### Pasajero y motorizado
- Botón "Llamar" junto al chat durante el viaje; pantalla de llamada (silenciar, altavoz, colgar).
- Notificación de llamada entrante con aceptar/rechazar.
### Motorizado
- Respuesta con un toque grande (uso con casco y guantes).

## Admin
- Detalle del viaje: llamadas realizadas (hora, duración, quién llamó, si se respondió).
- Configuración: activar por ciudad (flag de 10), duración máxima.

## API y datos
- `ride_calls` (`ride_id`, `caller_id`, `started_at`, `answered_at`, `ended_at`, `end_reason`).
- `POST /rides/{id}/calls` → credenciales TURN temporales (HMAC con secreto de coturn) y id de llamada.
- Eventos WebSocket `call.offer`, `call.answer`, `call.ice`, `call.end`.
- Dependencia nativa `react-native-webrtc` (requiere build nueva, no llega por OTA).

## Criterios de aceptación
- Una llamada entre dos teléfonos Android en redes móviles distintas conecta en < 5 s y se oye con claridad.
- Ningún participante ve el número del otro.
- Fuera del viaje activo no se puede llamar (`call_not_allowed`).

## Dependencias
02 (servidor y puertos UDP). 14 (canal de llamada entrante). Requiere APK nuevo (09).

## Preguntas para Carlos
1. ¿Vale la pena el esfuerzo? Recomendado: medir primero cuántos reportes o cancelaciones se deben a "no logré
   comunicarme" (19) y decidir con ese dato.
