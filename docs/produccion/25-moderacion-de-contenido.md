# 25 · Moderación de contenido

**Prioridad:** P2 · **Área:** API · Admin · **Depende de:** 13

## Objetivo
Mantener sanos los espacios donde los usuarios escriben o suben contenido (chat del viaje, comentarios de
calificación, fotos de perfil, descripciones de reportes) y desincentivar que el chat se use para sacar a los
clientes de la app.

## Estado actual
- Chat del viaje (1–500 caracteres) solo durante el viaje, guardado para soporte.
- Calificaciones con comentario opcional y etiquetas.
- Foto de perfil (`avatar_key`) sin revisión.
- Ningún filtro de contenido.

## Alcance
### Incluye
1. **Filtro de chat** (sin bloquear la seguridad): detectar insultos con lista de palabras en es/en (incluye
   jerga venezolana, editable desde el admin) y marcar el mensaje; detectar números de teléfono y enlaces de
   WhatsApp para registrar el intento de "viaje por fuera" (señal para 16, no bloqueo, porque puede ser
   legítimo para coordinar la recogida). Configurable: avisar, ocultar el número o permitir.
2. **Denunciar mensaje** desde el chat (mantener presionado) → crea reporte `harassment` con el mensaje citado.
3. **Comentarios de calificación**: mismos filtros; los comentarios ofensivos no cuentan para el perfil público y
   se marcan para revisión.
4. **Fotos de perfil**: cola de revisión ligera (aprobar/rechazar con motivo) para motorizados (su foto se
   muestra al pasajero); para pasajeros, solo cuando se denuncian. Opcional: modelo abierto de detección de
   desnudez autoalojado como prefiltro.
5. **Nombres**: validar nombres ofensivos o que imiten a "Kuulis Soporte".

### Fuera
- Moderación automática con modelos de pago.

## App móvil
### Pasajero y motorizado
- Mantener presionado un mensaje del chat → "Denunciar".
- Aviso suave si se intenta enviar un insulto ("Mantengamos el respeto").
### Motorizado
- Si su foto de perfil fue rechazada: aviso con motivo y botón para subir otra.

## Admin
- **Moderación**: cola de mensajes y comentarios marcados, fotos pendientes, con acciones (aprobar, ocultar,
  advertir al usuario, abrir reporte, suspender).
- Gestión de la lista de palabras y de las reglas de teléfonos y enlaces.

## API y datos
- `ride_messages.flags` (text[]) y `hidden_at`; `ratings.comment_hidden_at`.
- `moderation_items` (`kind` message|comment|avatar|name, `ref_id`, `reason`, `status`, `reviewed_by`).
- `users.avatar_status` (pending|approved|rejected) para motorizados.
- `POST /rides/{id}/messages/{msg_id}/report`.
- `AppConfig.moderation` (palabras, reglas de teléfono/enlace, modo).

## Criterios de aceptación
- Un insulto en el chat queda marcado y aparece en la cola de moderación.
- Un número de teléfono en el chat genera una señal en el usuario sin bloquear el mensaje (modo por defecto).
- La foto de un motorizado no se muestra al pasajero hasta ser aprobada (si se activa la regla).

## Dependencias
13 (reportes como destino de las denuncias). 16 consume las señales de "viaje por fuera".

## Preguntas para Carlos
1. ¿Ocultar números de teléfono en el chat o solo registrar el intento? Recomendado: solo registrar al inicio.
