# 24 · Admin: herramientas de operación (CRM)

**Prioridad:** P2 · **Área:** Admin · API · **Depende de:** 06, 13

## Objetivo
Que el equipo resuelva cualquier caso desde una sola ficha por persona, encuentre todo con una búsqueda y haga
el trabajo repetitivo en lote, para operar 5000+ usuarios con pocas personas.

## Estado actual
- Páginas separadas: usuarios, motorizados, viajes, viajes en vivo, reportes, recargas, transferencias,
  suscripciones, billeteras, promociones, tasas, finanzas, notificaciones, configuración.
- `PersonSummaryCard` en reportes resume a una persona (calificación, viajes, reportes, suspensión).
- Crear usuarios desde el panel: el endpoint existe pero no hay pantalla (`docs/pending.md`).
- Sin notas internas sobre un usuario fuera de los reportes, sin línea de tiempo unificada, sin búsqueda global.

## Alcance
### Incluye
1. **Ficha 360 de la persona**: datos, roles (pasajero/motorizado), estado, suspensión, riesgo (16), calidad
   (15), billetera, cuotas, viajes, reportes en ambos sentidos, verificaciones (12), sesiones y dispositivos (05),
   aceptaciones legales (07), auditoría (06) y **línea de tiempo unificada** de todos sus eventos.
2. **Notas internas y etiquetas** por persona ("motorizado embajador", "VIP", "vigilar"), visibles para el
   equipo, con autor y fecha.
3. **Búsqueda global** (atajo `/` o `Ctrl+K`): por nombre, email, teléfono, cédula, placa, id de viaje, id de
   transacción de Binance o código de referido.
4. **Acciones en lote**: enviar notificación, etiquetar, exportar, suspender (con doble aprobación si son
   muchos).
5. **Vistas guardadas** en las listas (filtros frecuentes) y exportación CSV de cualquier lista (auditada).
6. **Crear usuarios** desde el panel (pantalla para el endpoint existente) y forzar cambio de contraseña o
   reenviar verificación.
7. **Contactar al usuario** desde la ficha: notificación directa, email o abrir ticket de soporte (13).
8. **Gráficas de registros por día** (pendiente en `docs/pending.md`) en la portada.

### Fuera
- CRM externo.

## App móvil
Sin cambios.

## Admin
- Nueva ficha de persona que unifica `users/[id]`, `drivers/[id]` y `wallets/[userId]` en pestañas.
- Barra de búsqueda global en el layout.
- Panel lateral de notas y etiquetas en la ficha.

## API y datos
- `user_notes` (`user_id`, `author_id`, `body`, `pinned`, `created_at`), `user_tags` (`user_id`, `tag`).
- `GET /admin/users/{id}/timeline?cursor` que une eventos de viajes, billetera, reportes, verificaciones,
  suspensiones y auditoría ordenados por fecha.
- `GET /admin/search?q` con búsqueda en varias tablas (índices trigram `pg_trgm` en nombre y email).
- `POST /admin/bulk` con acción y lista de ids (encolado, resultado por id).

## Criterios de aceptación
- Desde una sola ficha se ve todo lo que pasó con una persona en orden cronológico.
- Buscar una placa, una cédula o el id de una transacción de Binance lleva a la persona correcta en < 1 s.
- Las notas internas nunca aparecen en la app del usuario ni en sus exportaciones de datos.

## Dependencias
06 (permisos y auditoría), 13 (tickets). Suma datos de 12, 15, 16 cuando existan.

## Preguntas para Carlos
Ninguna bloqueante.
