# 05 · Seguridad y variables de entorno

## Variables de entorno
Solo nombres. Los valores viven en Coolify (API y worker) y en el gestor de contraseñas de Carlos; **nunca** en
el repo, el chat, los logs, los tickets ni la memoria de los agentes.

| Variable | Secreta | QA | Producción | Para qué |
| --- | --- | --- | --- | --- |
| `WHATSAPP_ENABLED` | No | `true` cuando esté listo | `false` hasta la salida | Interruptor técnico: sin él el router responde 404 y no se envía nada. El encendido para usuarios es el flag `whatsapp_rides`. |
| `WHATSAPP_GRAPH_URL` | No | `https://graph.facebook.com` | igual | Base de la Graph API |
| `WHATSAPP_GRAPH_VERSION` | No | versión vigente al implementar (por ejemplo `v23.0`) | igual | Fija la versión; se sube a propósito |
| `WHATSAPP_PHONE_NUMBER_ID` | No | `1401863553012660` (número de prueba) | el del número real | Desde qué número se envía y qué webhooks se aceptan |
| `WHATSAPP_BUSINESS_ACCOUNT_ID` | No | `1672828641129416` | el de la cuenta real | Gestión de plantillas y métricas |
| `WHATSAPP_ACCESS_TOKEN` | **Sí** | token del usuario del sistema de QA | token del usuario del sistema de prod | Autoriza los envíos (`Authorization: Bearer …`) |
| `WHATSAPP_APP_SECRET` | **Sí** | secreto de la app de Meta | ídem (si es otra app, el suyo) | Verifica `X-Hub-Signature-256` |
| `WHATSAPP_VERIFY_TOKEN` | **Sí** | aleatorio de 32+ caracteres | otro distinto | Solo para el GET de verificación del webhook |
| `WHATSAPP_SUPPORT_HOURS` | No | `08:00-20:00` | igual | Texto de horario de soporte (también puede ir en la config del admin) |

En `kuulis/settings/base.py` van con valor vacío por defecto (como `BINANCE_API_KEY`), y la app arranca sin ellas.
`WHATSAPP_ENABLED=true` sin token, secreto o phone number id hace fallar el arranque con un mensaje claro.
Se agregan a `api/.env.example` (sin valores), a la tabla de secretos de `docs/deployment.md` y a
`docs/infra/servicios-externos.md`.

## El token de acceso
- **Usar un token permanente de un usuario del sistema** (Business Manager → Usuarios del sistema), con solo los
  permisos `whatsapp_business_messaging` y `whatsapp_business_management` y solo sobre la cuenta de WhatsApp de
  Kuulis. Nunca el token personal de Carlos ni el temporal del panel de desarrolladores (dura 24 h).
- **Un token por entorno** (QA y producción), como el resto de secretos: QA nunca puede escribir desde el número
  de producción.
- **Rotación**: cada 90 días y siempre que alguien salga del equipo o el token aparezca en un lugar donde no
  debía (chat, log, captura). Pasos: generar el nuevo en el usuario del sistema → cambiarlo en Coolify (API y
  worker) → redesplegar → comprobar un envío en QA → **revocar el viejo**. Se anota la fecha en la tabla de
  secretos de `docs/deployment.md`.
- **Pendiente ya:** un token de acceso se pegó en el chat del proyecto el 2026-10-30. Aunque los temporales
  vencen solos en 24 h, conviene revocarlo en el panel de Meta y no reutilizarlo. Ese valor no se copió a ningún
  archivo.
- El token **no se registra nunca**: el cliente httpx no loguea cabeceras, Sentry filtra `Authorization` y los
  errores de la Graph API se guardan sin la petición original.
- Gitleaks (CI) ya detecta tokens de Facebook con su regla genérica; se agrega una prueba con un valor falso para
  confirmarlo.

## Firma del webhook (`X-Hub-Signature-256`)
Cada POST de Meta lleva `X-Hub-Signature-256: sha256=<hex>`, el HMAC-SHA256 del **cuerpo crudo** con el secreto de
la app.

```python
expected = "sha256=" + hmac.new(APP_SECRET, raw_body, hashlib.sha256).hexdigest()
if not hmac.compare_digest(expected, header or ""):
    raise SignatureInvalidError()   # 401, se registra con la IP y sin el cuerpo
```

Reglas:
- Se calcula sobre los bytes recibidos, **antes** de parsear JSON (parsear y volver a serializar cambia la firma).
- Comparación de tiempo constante (`hmac.compare_digest`), como ya se hace en `apps/updates` y `apps/wallet`.
- Sin cabecera o con firma mala: `401`, contador en métricas y alerta si pasan de 20 en 5 minutos.
- Además se comprueba `metadata.phone_number_id` contra la variable: un webhook firmado de otro número de la
  misma app se ignora.
- El `hub.verify_token` del GET no sirve para los POST; sin el secreto de la app nadie puede inyectar mensajes.

## Abuso y fraude (doc 16 de producción)
Pedir sin registrarse (decidido 5) abre la puerta a viajes falsos que hacen que un motorizado vaya a buscar a
nadie. Controles:

| Riesgo | Control |
| --- | --- |
| Viajes falsos en serie | Una sola solicitud activa por número (índice único de `rides`), calificación obligatoria, no-shows y cancelaciones cuentan para pausas de calidad (doc 15) igual que en la app |
| Número nuevo que abusa | Límites por número: 10 cotizaciones/hora, 5 solicitudes/día, 60 mensajes/hora. Al pasarlos: mensaje amable y espera |
| Muchos números del mismo actor | Señales de riesgo (`apps.risk`) por zona de recogida repetida con números distintos, no-shows seguidos; el admin ve los contactos agrupados |
| Números no venezolanos o virtuales | Pregunta 1: solo +58 para pedir |
| Bloqueo | El admin puede bloquear un número (motivo obligatorio, auditado); automático tras 3 no-shows en 7 días (Supuesto, configurable) |
| Mensajes enormes o binarios | Texto recortado a 1000 caracteres; medios solo en modo soporte, imágenes de hasta 5 MB |
| Inyección en textos | Nombre y notas pasan por la misma limpieza que en la app (sin enlaces, sin teléfonos en el nombre) antes de mostrarse al motorizado |
| Suplantación del bot | El número de producción con nombre verificado «Kuulis»; la web y la app enlazan solo a ese número |

Al motorizado: no ve el teléfono del pasajero (pregunta 3) ni el pasajero ve el del motorizado. El enlace en vivo
usa los tokens aleatorios de `ride_share_links` y expira al terminar el viaje.

## Privacidad (doc 07 de producción)
- **Datos que se guardan**: número, nombre de perfil y el que dio, consentimiento, mensajes (90 días), viajes
  (como cualquier pasajero).
- **Minimización**: invitados que no completan un viaje se borran o anonimizan a los 30 días (pregunta 6);
  coordenadas en el registro de mensajes redondeadas; el texto de los mensajes no va a la analítica.
- **Política de privacidad**: se agrega una sección «Si pides por WhatsApp» que nombra a Meta como encargado del
  transporte de los mensajes y explica que Meta conserva los mensajes en la Cloud API hasta 30 días.
- **Derechos**: «borrar mis datos» en soporte inicia el borrado de cuenta existente (`deletion_requested_at`) y
  también borra el contacto y sus mensajes.
- **Acceso del equipo**: leer la conversación de un contacto es una lectura sensible auditada (doc 06); solo
  roles Soporte y Admin.
- **Copias de seguridad**: las tablas nuevas entran en los backups cifrados normales (doc 04).

## Infraestructura
- El webhook entra por la misma cadena que la API (NPM → Traefik → API). No hace falta abrir puertos nuevos.
- Meta exige HTTPS con certificado válido; el dominio de la API ya lo tiene.
- No se filtra por IP de Meta (cambian sin aviso); la firma es el control.
- Salida hacia `graph.facebook.com` y `lookaside.fbsbx.com` (descarga de medios) desde la API y el worker;
  comprobar que el firewall de las VPS de producción (`docs/infra/produccion-2-vps.md`) lo permite.

## Lista de revisión de seguridad antes de salir
- [ ] Ningún token en el repo, los logs ni Sentry (búsqueda en los logs de QA tras una prueba completa).
- [ ] Firma verificada con pruebas de firma buena, mala, ausente y cuerpo modificado.
- [ ] Token permanente del usuario del sistema, uno por entorno, fecha anotada en `docs/deployment.md`.
- [ ] Token pegado en el chat (2026-10-30) revocado.
- [ ] Límites por número probados.
- [ ] Bloqueo desde el admin auditado.
- [ ] Política de privacidad actualizada y enlazada en el primer mensaje.
