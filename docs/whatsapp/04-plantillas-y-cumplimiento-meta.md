# 04 · Plantillas y cumplimiento de Meta

Reglas de WhatsApp Business Platform que afectan el diseño y lo que hay que preparar en Meta. Las reglas y
precios de Meta cambian con frecuencia: **antes de la salida a producción se revisan en la documentación oficial**
(developers.facebook.com/docs/whatsapp) y se actualiza este documento.

## Cuentas y números
| Qué | Valor | Nota |
| --- | --- | --- |
| Número de prueba (QA) | +1 (555) 209-1686 | Dado por Meta. Solo puede escribir a hasta **5 números destinatarios** registrados y verificados en el panel de la app. No sirve para producción. |
| Phone Number ID (prueba) | `1401863553012660` | No es secreto. Va en `WHATSAPP_PHONE_NUMBER_ID` de QA. |
| WhatsApp Business Account ID (prueba) | `1672828641129416` | No es secreto. Va en `WHATSAPP_BUSINESS_ACCOUNT_ID` de QA. |
| Número de producción | Por definir (pregunta 7) | No puede estar activo en la app de WhatsApp ni en WhatsApp Business del teléfono. Se registra con un **PIN de verificación en dos pasos** que se guarda en el gestor de contraseñas de Carlos, no en el repo. |

## La ventana de 24 horas
- Cada mensaje del pasajero abre (o renueva) una **ventana de atención de 24 h**. Dentro de ella Kuulis puede
  enviar cualquier mensaje: texto, botones, listas, imágenes, ubicaciones.
- Fuera de la ventana **solo se pueden enviar plantillas aprobadas**. Un mensaje libre falla con el error
  `131047`.
- Un viaje dura minutos, y el pasajero acaba de escribir para pedirlo, así que **todo el flujo normal del viaje
  ocurre dentro de la ventana**: confirmación, avisos, PIN, calificación y chat. Las plantillas son el respaldo
  para casos raros y para el soporte tardío.
- `whatsapp_contacts.last_inbound_at` dice si la ventana está abierta; `whatsapp.send` elige texto libre o
  plantilla con eso, y si Meta igual responde `131047`, cae a la plantilla.

## Precios (revisar antes de producción)
Desde julio de 2025 Meta cobra **por mensaje de plantilla entregado**, según la categoría y el país del
destinatario (Venezuela entra en la tarifa de «Resto de Latinoamérica»):
- **Mensajes de servicio** (no plantilla, dentro de la ventana): **gratis**. Es casi todo el canal.
- **Plantillas de utilidad dentro de la ventana abierta**: gratis.
- **Plantillas de utilidad fuera de la ventana**: se pagan (centavos de dólar cada una).
- **Marketing**: se paga y requiere consentimiento específico. **No se usa** (fuera de alcance).
- **Autenticación** (códigos): solo si más adelante se une el invitado con la app (pregunta 9).

Estimación: con 1000 viajes diarios, el costo de Meta es prácticamente cero; solo cuentan las respuestas de
soporte enviadas después de 24 h. Se registra en la métrica del admin para verlo.

## Plantillas
Idioma `es`, categoría **utilidad**, sin lenguaje promocional (si Meta las recategoriza como marketing, cuestan
más: se revisa el webhook `template_category_update`). Se crean en el WhatsApp Manager o por la API de gestión y se
referencian por nombre en `texts.py`.

| Nombre | Cuándo | Texto propuesto | Botón |
| --- | --- | --- | --- |
| `soporte_respuesta` | El equipo responde un ticket y la ventana está cerrada | «Hola {{1}}, el equipo de Kuulis respondió tu consulta. Toca el botón para leer la respuesta.» | Respuesta rápida «Ver respuesta» |
| `objeto_perdido_novedad` | Hay novedades del objeto perdido (doc 13) fuera de la ventana | «Hay novedades sobre el objeto que dejaste en tu viaje del {{1}}. Toca el botón para verlas.» | «Ver novedades» |
| `viaje_actualizacion` | Respaldo: un aviso del viaje cae fuera de la ventana (no debería pasar) | «Tu viaje de Kuulis cambió de estado: {{1}}. Toca el botón para ver los detalles.» | «Ver mi viaje» |
| `calificacion_pendiente` | Opcional, apagado por defecto: recordar calificar 24 h después | «Tu viaje con {{1}} ya terminó. Califícalo para poder pedir el siguiente.» | «Calificar» |

Patrón: la plantilla **no lleva el contenido**, solo invita a tocar el botón. Al tocarlo el pasajero abre la
ventana y el bot le envía el detalle como mensaje de servicio (gratis). Así las plantillas son cortas, se aprueban
rápido y no exponen datos en la vista previa de la notificación.

El webhook `message_template_status_update` avisa si Meta aprueba, rechaza o pausa una plantilla; se alerta por
Telegram (doc 03 de producción).

## Políticas que hay que cumplir
1. **Consentimiento (opt-in).** El pasajero escribe primero; el primer mensaje del bot enlaza Términos y Privacidad
   y se registra `consent_at`. Kuulis nunca inicia conversaciones con números que no escribieron.
2. **Salida (opt-out).** Escribir `baja`, `stop` o `no quiero mensajes` detiene todo mensaje no pedido (plantillas y
   recordatorios). Si hay un viaje activo se le avisa que dejará de recibir los avisos de ese viaje y se le
   pregunta si quiere cancelarlo.
3. **Paso a una persona.** La política de mensajería de WhatsApp exige un camino claro hacia un humano en
   experiencias automatizadas. Lo cubre «soporte» (decidido 11), siempre visible en el menú y en los errores.
4. **Política de comercio.** Transporte de personas es una actividad permitida. No se venden productos regulados
   ni se piden datos de pago (el pago es directo al motorizado).
5. **Datos sensibles.** El bot no pide cédula, datos bancarios ni contraseñas. Si el pasajero los escribe en
   soporte, el equipo no los repite.
6. **Sin spam ni marketing** por este canal (fuera de alcance). Los mensajes de difusión y el canal de WhatsApp
   del plan de marketing son otra cosa y no usan este número.
7. **Menores.** Igual que en la app: los términos exigen mayoría de edad.

## Preparación en Meta (lista para Carlos)
1. **Business Manager (Meta Business Suite)** de Kuulis con datos legales reales.
2. **Verificación del negocio** (documentos de la empresa). Sin verificación el número queda en el nivel más bajo
   de envíos y con límites.
3. **App de Meta** tipo Business con el producto WhatsApp agregado (ya existe para el número de prueba).
4. **Usuario del sistema** con rol de administrador y un **token permanente** con los permisos
   `whatsapp_business_messaging` y `whatsapp_business_management` (ver 05). El token temporal del panel dura
   24 h y no sirve para producción.
5. **Número de producción** registrado, con **nombre visible «Kuulis»** aprobado por Meta.
6. **Perfil del negocio**: foto (logo), descripción corta («Motos en Caracas con precio justo, sin regateo»),
   horario de soporte, web, email de soporte.
7. **Webhook**: URL `https://<dominio de la API>/api/v1/whatsapp/webhook`, token de verificación, suscripción a
   los campos `messages`, `message_template_status_update`, `template_category_update`,
   `phone_number_quality_update` y `account_update`.
8. **Plantillas** de la tabla, enviadas a revisión antes de la salida.
9. **App en modo Live** (publicada) con política de privacidad pública.

## Calidad del número y límites
- Meta califica el número (verde, amarillo, rojo) según bloqueos y reportes de los usuarios. Con calidad baja
  baja el límite de envíos y puede suspender el número.
- El **límite de mensajes iniciados por la empresa** (plantillas a personas distintas en 24 h) empieza bajo y sube
  con la verificación y la buena calidad. Este canal casi no inicia conversaciones, así que no debería tocarlo.
- El throughput por número (mensajes por segundo) sobra para el volumen esperado (03, Capacidad).
- Se escucha `phone_number_quality_update` y `account_update`: un cambio a amarillo o rojo alerta por Telegram y
  aparece en la página de métricas del admin.
- Buenas prácticas para mantener verde: respuestas útiles y cortas, nada de mensajes no pedidos, salida fácil,
  soporte humano a mano.
