# 11 · Seguridad en el viaje

**Prioridad:** P0 · **Área:** Mobile · API · Admin · **Depende de:** 08 (página de viaje compartido)

## Objetivo
Que pasajero y motorizado se sientan seguros en una moto con un desconocido: confirmar que es la persona
correcta, que alguien de confianza pueda seguir el viaje en vivo, que un SOS llegue al equipo de Kuulis con la
ubicación, y detectar situaciones anómalas. Es el principal riesgo listado en `open-questions.md`.

## Estado actual
- Hoja de seguridad en el viaje con: llamar al 911, reportar un problema y **compartir el viaje como texto**
  (conductor, moto, placa, origen, destino y enlace de Google Maps al destino). No hay seguimiento en vivo.
- Se ven nombre, foto, moto y placa del motorizado; el pasajero solo muestra nombre y calificación.
- Reportes con categoría `safety` y `harassment` marcados como urgentes, atendidos por la bandeja del admin.
- **No se guarda el recorrido del viaje**: solo la última posición del motorizado en Redis.

## Alcance
### Incluye
1. **PIN de inicio del viaje**: el pasajero ve un código de 4 dígitos; el motorizado debe escribirlo para
   iniciar el viaje (`/rides/{id}/start` lo exige). Evita subirse a la moto equivocada. Activable por ciudad.
2. **Compartir viaje en vivo**: enlace `https://<dominio>/v/{token}` (08) que muestra posición, estado, datos del
   motorizado y hora estimada; caduca al terminar o cancelar el viaje. Lo puede compartir el pasajero y también
   el motorizado.
3. **Contactos de confianza** (hasta 5, con nombre y teléfono): compartir automáticamente cada viaje (opcional,
   por horario, por ejemplo de noche) por WhatsApp/SMS usando la app de mensajería del teléfono (sin costo
   para Kuulis).
4. **Botón SOS** (pasajero y motorizado), visible en todo el viaje:
   - Mantener presionado 2 s → llama al 911 (como hoy) **y** crea una alerta SOS con ubicación en vivo.
   - La alerta llega al admin en tiempo real con sonido, por push al equipo de guardia y por Telegram (03).
   - Envía el enlace en vivo a los contactos de confianza.
   - Mientras está activa, la app envía la ubicación cada 5 s aunque el viaje termine.
5. **Recorrido del viaje**: guardar los puntos del motorizado durante el viaje (cada 5–10 s, reducidos) para
   revisar reportes, disputas de cobro y detectar desvíos. Retención en 07.
6. **Detección de anomalías** (reglas simples, configurables):
   - Parada de más de N minutos durante `in_progress` fuera del destino.
   - Desvío de la ruta prevista mayor a X metros durante Y minutos.
   - Viaje que dura más del doble del estimado.
   - Ante una anomalía: notificación a ambos "¿Todo bien?" con botones "Estoy bien" / "Necesito ayuda"; sin
     respuesta en 2 min, alerta al admin.
7. **Verificación de la foto del pasajero** (opcional por ciudad, de noche): el motorizado puede ver la foto
   del pasajero al aceptar, si el pasajero tiene foto. Supuesto: no obligatoria.
8. **Consejos de seguridad** antes del primer viaje (pasajero: verificar placa y PIN; motorizado: casco para
   el pasajero).

### Fuera
- Grabación de audio del viaje (costo, privacidad y almacenamiento).
- Integración con servicios de emergencia oficiales (no hay API pública).

## App móvil
### Pasajero
- En "motorizado asignado": PIN grande con instrucción "Dale este código al motorizado".
- Hoja de seguridad: SOS, compartir en vivo, contactos de confianza, reportar, consejos.
- Perfil → Seguridad → Contactos de confianza y "Compartir automáticamente mis viajes".
- Respuesta a "¿Todo bien?" desde la notificación sin abrir la app.
### Motorizado
- Al llegar: teclado numérico enorme para el PIN (uso con guantes) antes de "Iniciar viaje"; mensaje claro si
  es incorrecto (3 intentos, luego llamar a soporte o cancelar sin penalidad).
- Botón SOS y compartir viaje en vivo.

## Admin
- **Centro de seguridad** (`/safety`): alertas SOS y anomalías en tiempo real sobre el mapa (Leaflet ya existe),
  con sonido, posición en vivo, datos de ambas partes, teléfono del motorizado, botón "Atendiendo", notas y
  cierre con resultado. Contador en el menú.
- En el detalle del viaje: recorrido real dibujado sobre la ruta prevista, eventos de PIN y anomalías.
- Configuración: PIN por ciudad, umbrales de anomalías, horario del equipo de guardia.

## API y datos
- `rides.start_pin` (4 dígitos, generado al asignar); `POST /rides/{id}/start` con `{pin}` → 400 `pin_invalid`,
  429 tras 3 intentos.
- `ride_share_links` (`ride_id`, `token` aleatorio de 128 bits, `created_by`, `revoked_at`);
  `POST /rides/{id}/share` → `{url}`; `GET /public/rides/shared/{token}`.
- `trusted_contacts` (`user_id`, `name`, `phone`, `auto_share`, `auto_share_hours`).
- `ride_track_points` (`ride_id`, `lat`, `lng`, `recorded_at`) con escritura en lote desde Redis al terminar el
  viaje (no una fila por mensaje en caliente), o columna `track` (LineString/JSONB) en `rides`.
- `safety_alerts` (`id`, `ride_id`, `user_id`, `kind` sos|stop|deviation|overtime, `status` open|acknowledged|
  resolved, `lat`, `lng`, `handled_by`, `notes`, `created_at`, `resolved_at`).
- `POST /rides/{id}/sos`, `POST /safety/alerts/{id}/ok`, `POST /safety/location` (durante SOS).
- Tarea `safety.check` (cada 30 s, con lock) que evalúa anomalías de los viajes `in_progress`.
- Eventos WebSocket `safety.alert` (admin) y `safety.check_in` (participantes).

## Criterios de aceptación
- Un viaje no puede iniciarse sin el PIN correcto cuando la ciudad lo exige.
- El enlace compartido muestra la posición en vivo y responde 410 tras completar el viaje.
- Un SOS aparece en el admin en menos de 5 s con sonido y posición, y llega a Telegram.
- Una parada simulada de 10 min dispara el "¿Todo bien?" y, sin respuesta, una alerta en el admin.
- El detalle del viaje en el admin muestra el recorrido real.

## Dependencias
08 (página `/v/{token}`). 03 para alertas por Telegram. 07 para la retención del recorrido.

## Preguntas para Carlos
1. ¿PIN obligatorio en todos los viajes o solo de noche? Recomendado: siempre en Caracas.
2. ¿Habrá alguien de guardia para atender SOS? Si no, el SOS solo llama al 911 y avisa a contactos.
