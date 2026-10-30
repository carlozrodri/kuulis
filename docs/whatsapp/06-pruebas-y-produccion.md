# 06 · Pruebas y salida a producción

Rigor «normal» como el resto de Kuulis: pruebas automáticas de lo importante, una pasada manual completa en QA
con teléfonos reales y una salida gradual con el flag.

## Pruebas automáticas (API, `apps/whatsapp/tests/`)
Contra Postgres y Redis reales como el resto de apps, con la Graph API simulada (respx o un cliente falso
inyectado). Comando de siempre: `cd api && uv run ruff check . && uv run ruff format --check . && uv run pytest`.

| Grupo | Casos |
| --- | --- |
| Verificación GET | token correcto devuelve el `challenge`; token malo o `hub.mode` distinto → 403 |
| Firma | buena → 200; mala, ausente, cuerpo alterado en un byte → 401; `phone_number_id` ajeno → 200 ignorado |
| Parser | fixtures reales (anonimizados) de texto, ubicación, `button_reply`, `list_reply`, imagen, audio, estados `sent/delivered/read/failed`, mensaje de sistema; JSON con campos nuevos desconocidos no rompe |
| Duplicados | el mismo `wamid` dos veces procesa una sola vez |
| Orden | ubicación vieja que llega después de una nueva no pisa el estado |
| Conversación (pura) | cada transición de la tabla de estados de 02, vencimientos, palabras clave en cualquier estado, mensajes no soportados |
| Cotizar y pedir | usa `create_quote` y `create_ride` reales: precio igual al de la app para la misma ruta, tasas BCV/Binance, recargo, promoción automática, fuera de zona, servicio cerrado, cotización vencida, doble toque en «Pedir» crea un solo viaje |
| Invitado | primer quote crea invitado; mismo número reutiliza; login rechazado; no se le envían emails; `customer_since` al primer viaje completado; `purge_guests` borra o anonimiza según tenga viajes |
| Avisos | cada evento de `rides.notify` sale por WhatsApp para invitados y por push para usuarios de la app; asignado incluye enlace en vivo y PIN cuando aplica |
| Cancelar | motivos válidos, aviso de que cuenta tras la gracia, `vehicle_mismatch` abre reporte |
| Calificar | obligatoria antes de pedir; 1-2 estrellas ofrece soporte |
| Chat | texto en `in_ride` llega al chat del viaje; mensaje del motorizado sale por WhatsApp; cerrado tras completar |
| Soporte | crea `Report` con `source = whatsapp`; mensajes y fotos se agregan; respuesta del equipo sale por texto en ventana y por plantilla fuera; cierre devuelve al bot |
| Envío | reintento en 5xx; `131047` cae a plantilla; `131026` no reintenta; límites `130429`/`131056` esperan |
| Abuso | límites por número; número bloqueado recibe un solo aviso; no +58 rechazado (si se decide así) |
| Flag | `whatsapp_rides` apagado responde el mensaje de descarga y soporte sigue funcionando |
| Seguridad | ningún log contiene el token (captura de logs en la prueba de envío) |

Migraciones: `alembic upgrade head` y `alembic check` en CI. App del motorizado: prueba de la etiqueta «Pedido
por WhatsApp» y claves `es`/`en`. Admin: vitest de la página de contactos.

## QA con el número de prueba
Entorno QA (`kuulis-qa.top8.uk`), número de prueba +1 (555) 209-1686.

### Preparación (Carlos, una vez)
1. En la app de Meta → WhatsApp → Configuración de la API: agregar y verificar hasta **5 números destinatarios**
   (el de Carlos y los de quienes vayan a probar). El número de prueba solo puede escribirles a ellos.
2. Crear el token del **usuario del sistema** para QA (05) y ponerlo en Coolify como `WHATSAPP_ACCESS_TOKEN` en la
   API y el worker de QA, junto con `WHATSAPP_APP_SECRET`, `WHATSAPP_VERIFY_TOKEN`, `WHATSAPP_PHONE_NUMBER_ID` y
   `WHATSAPP_BUSINESS_ACCOUNT_ID`. Claude no toca Coolify sin su permiso (memoria
   `kuulis-coolify-automation-limits`).
3. Configurar el webhook en la app de Meta: `https://kuulis-qa.top8.uk/api/v1/whatsapp/webhook` con el token de
   verificación y suscribir los campos de 04.
4. Encender `whatsapp_rides` en el control remoto de QA (o solo para los números de prueba con una regla).

### Pasada manual (con un motorizado de QA en la app)
- [ ] «Hola» → bienvenida con enlace legal y botones.
- [ ] Nombre → origen con ubicación actual → destino elegido en el mapa → cotización con el **mismo precio** que
      muestra la app para esa ruta y las dos tasas.
- [ ] Cotizar sin pedir; dejar vencer la cotización (5 min) y ver el aviso.
- [ ] Pedir con cada método de pago; nota para el motorizado.
- [ ] El motorizado ve «Pedido por WhatsApp», el nombre y la nota; no ve el teléfono.
- [ ] Avisos: asignado (enlace en vivo abre y muestra la moto), PIN, llegó, en curso, terminado con monto y método.
- [ ] Calificar con estrellas y comentario; intentar pedir sin calificar.
- [ ] Cancelar antes y después de la gracia; «la moto no coincide».
- [ ] Motorizado cancela → «buscando otro»; sin motorizados → aviso.
- [ ] Chat ida y vuelta durante el viaje.
- [ ] Soporte: abrir, enviar foto, responder desde el admin, cerrar. Respuesta fuera de la ventana con la
      plantilla (probar cambiando `last_inbound_at` en QA).
- [ ] Nota de voz, sticker, dirección escrita, ubicación fuera de Caracas.
- [ ] Primer viaje completado → el número aparece como cliente en el admin.
- [ ] Bloquear el número desde el admin y escribir de nuevo.
- [ ] Apagar el flag y escribir.
- [ ] Revisar logs y Sentry de QA: sin tokens, sin errores.

### Carga
Con el endpoint de pruebas de carga existente (`apps.loadtest`) o un script k6: 50 webhooks firmados por segundo
durante 5 minutos (unas diez veces el pico esperado). Objetivo: respuesta del webhook p95 < 100 ms, cola sin
atraso, ningún duplicado procesado. Los envíos a Meta se simulan (no se gasta el número de prueba).

## Salida a producción
### Requisitos (bloqueantes)
- [ ] Pasada manual de QA completa sin fallos abiertos.
- [ ] Negocio verificado en Meta, número de producción registrado, nombre visible «Kuulis» aprobado, perfil
      completo (04).
- [ ] Plantillas aprobadas.
- [ ] App de Meta en modo Live, webhook de producción verificado con el dominio de la API de producción.
- [ ] Token permanente de producción en Coolify (API y worker) y fecha anotada en `docs/deployment.md`.
- [ ] Política de privacidad y términos actualizados (05).
- [ ] Alertas por Telegram configuradas (abajo).
- [ ] Equipo de soporte sabe responder tickets de WhatsApp y conoce el horario.

### Encendido gradual (flag `whatsapp_rides`)
1. **Día 0**: solo números del equipo (regla por lista en el control remoto).
2. **Semana 1**: 10 % de los números nuevos (el resto recibe el mensaje con el enlace de descarga). Revisar a
   diario las métricas y los tickets.
3. **Semana 2**: 50 %.
4. **Semana 3**: 100 %, y se anuncia el número en la web, la app y las redes.

Avanzar solo si: errores de envío < 1 %, calidad del número en verde, no-shows de WhatsApp no mayores que los de
la app, sin incidentes de seguridad.

### Monitoreo y alertas (doc 03 de producción)
| Señal | Umbral | Acción |
| --- | --- | --- |
| Firmas inválidas | > 20 en 5 min | Telegram; revisar si cambió el secreto o hay un ataque |
| Errores de envío | > 5 % en 15 min | Telegram; ver códigos de error |
| Cola `whatsapp` atrasada | > 30 s | Telegram; revisar worker |
| Calidad del número | baja a amarillo o rojo | Telegram; revisar mensajes y bloqueos |
| Token inválido (error 190) | cualquiera | Telegram urgente: rotar el token |
| Plantilla rechazada o pausada | cualquiera | Telegram |

Métricas Prometheus (endpoint existente): mensajes in/out por tipo, latencia webhook → respuesta, cotizaciones,
viajes pedidos y completados por canal, errores por código.

### Vuelta atrás
- **Apagar el flag `whatsapp_rides`**: efecto inmediato, sin desplegar. El bot responde con el enlace de descarga y
  el soporte sigue. Los viajes activos de WhatsApp siguen recibiendo avisos hasta terminar.
- Problema grave en el webhook: `WHATSAPP_ENABLED=false` y redesplegar; Meta reintenta los webhooks pendientes
  durante días, así que al volver se procesan (los duplicados se descartan por `wamid`).
- Las migraciones son aditivas; no hace falta revertirlas.

## Después de la salida
- Revisión a las 2 semanas: conversión, cancelaciones, tickets más comunes, textos que confunden. Ajustar
  `texts.py`.
- Evaluar las preguntas que quedaron para después: unir invitados con la app, promociones por código, pedir para
  otra persona, lugares guardados.
