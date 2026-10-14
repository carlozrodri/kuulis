# 15 · Reglas de cancelación y calidad del servicio

**Prioridad:** P1 · **Área:** API · Mobile · Admin · **Depende de:** nada

## Objetivo
Proteger el tiempo de ambas partes y la confiabilidad del servicio: tiempo de espera en el punto de recogida,
"no se presentó", límites a las cancelaciones abusivas y métricas de calidad por motorizado y por pasajero,
**sin cobrar dinero** (Kuulis no procesa pagos de viajes).

## Estado actual
- Cancelaciones del pasajero (desde `searching`, `driver_assigned`, `driver_arrived`) y del motorizado (desde
  `driver_assigned`, `driver_arrived`), con motivo libre en `cancel_reason`. Sin consecuencias.
- El motorizado puede rechazar ofertas o dejarlas vencer sin efecto.
- No existe tiempo de espera ni "no se presentó".
- Métricas del admin con tasas globales de cancelación; no por persona.

## Alcance
### Incluye
1. **Motivos de cancelación predefinidos** por lado (pasajero: "tardó mucho", "cambié de planes", "el
   motorizado me pidió cancelar", "la moto no coincide"...; motorizado: "no se presentó", "dirección incorrecta",
   "pasajero sin casco"...) más texto opcional. "La moto no coincide" abre un reporte `vehicle_mismatch`.
2. **Espera y no-show**: al marcar "llegué" empieza un contador visible para ambos. Tras N minutos
   (configurable, por ejemplo 5) el motorizado puede cancelar como **"no se presentó"** sin penalidad.
3. **Ventana de gracia del pasajero**: cancelar en los primeros 2 min tras la asignación no cuenta.
4. **Tasas por persona** (últimos 30 días o últimos 50 viajes): aceptación, cancelación del motorizado,
   cancelación del pasajero, no-shows. Visibles para el propio usuario (motorizado) y en el admin.
5. **Consecuencias sin dinero**, configurables:
   - Motorizado que cancela X veces en una hora o rechaza Y ofertas seguidas: pausa automática de 15 min ("Te
     desconectamos un momento para no hacer esperar a los pasajeros").
   - Motorizado con tasa de cancelación > umbral: aviso, luego menor prioridad en el despacho, luego revisión.
   - Pasajero con muchos no-shows: aviso, luego pausa temporal para pedir.
   - Calificación promedio bajo umbral (por ejemplo < 4,3 con ≥ 20 viajes): revisión en el admin.
6. **Prioridad en el despacho**: además de la cercanía, desempatar por calificación y tasa de aceptación
   (configurable, empezar con peso bajo para no castigar a los nuevos).
7. **Reasignación automática**: si el motorizado cancela tras aceptar, el viaje vuelve a `searching` (con
   prioridad) en vez de terminar, si el pasajero no lo cancela.

### Fuera
- Tarifas de cancelación en dinero (no hay cobro dentro de la app).

## App móvil
### Pasajero
- Hoja de cancelación con motivos; aviso si ya pasó la gracia ("Cancelar muchas veces puede pausar tu cuenta").
- Contador "Tu motorizado te espera: 3:12" al llegar.
- Si el motorizado cancela: "Buscando otro motorizado" automáticamente.
### Motorizado
- Contador de espera con botón "No se presentó" habilitado al cumplirse el tiempo.
- Panel "Mi calidad": tasa de aceptación, de cancelación y calificación, con explicación de umbrales.
- Pantalla de pausa temporal con cuenta regresiva.

## Admin
- Ficha de usuario y de motorizado: tasas y su evolución, historial de pausas.
- Lista "Calidad" con motorizados y pasajeros por debajo de umbrales, para revisar.
- Configuración: minutos de espera, gracia, umbrales y duración de pausas, peso de calidad en el despacho.
- Métricas: cancelaciones por motivo.

## API y datos
- `rides.cancel_reason_code` (enum) además del texto; nuevo estado final `no_show` (o `cancelled_by_driver` con
  código `no_show`, a decidir para no romper clientes).
- `rides.reassigned_from_driver_id` y conteo de reasignaciones.
- `user_quality_stats` (materializada o calculada por tarea cada 10 min): tasas por usuario y rol.
- `driver_pauses` / `passenger_pauses` (`user_id`, `reason`, `until`).
- `POST /drivers/me/online` y `POST /rides` responden 403 `temporarily_paused` con `details.until`.
- `AppConfig`: `pickup_wait_minutes`, `passenger_cancel_grace_s`, `quality_rules`, `dispatch_quality_weight`.
- `GET /drivers/me/quality`.

## Criterios de aceptación
- Tras 5 min de espera el motorizado puede marcar "no se presentó" y no cuenta como cancelación suya.
- Un motorizado que rechaza 5 ofertas seguidas queda pausado 15 min y lo ve claramente.
- Si el motorizado cancela un viaje aceptado, el pasajero vuelve a `searching` sin hacer nada.
- Las tasas del admin coinciden con un cálculo manual sobre los viajes del periodo.

## Dependencias
Ninguna obligatoria. 16 usa estas tasas para detectar fraude.

## Preguntas para Carlos
1. ¿Minutos de espera antes del no-show? Recomendado: 5.
   **Decidido** (recomendado): 5 minutos, configurable en Ajustes → Calidad del servicio.
2. ¿Pausas automáticas para motorizados que rechazan mucho? Recomendado: sí, suaves (15 min).
   **Decidido** (recomendado): 5 ofertas seguidas rechazadas o ignoradas, o 3 cancelaciones en una hora,
   pausan 15 minutos. Todo configurable y se puede apagar.

## Cómo quedó (2026-10-13)
### API (`api/apps/rides`, `api/apps/quality`)
- **Motivos:** `POST /rides/{id}/cancel` acepta `reason_code` (opcional, las apps viejas siguen funcionando).
  Cada cancelación queda en `ride_cancellations` con el lado, el motivo, la etapa del viaje y si cuenta.
- **No cuentan:** la cancelación del pasajero en los 2 primeros minutos tras la asignación o por "la moto no
  coincide" (que además abre el reporte `vehicle_mismatch` de 12), el no-show válido y "no me siento seguro"
  del motorizado.
- **No-show:** se decidió no crear un estado nuevo: es `cancelled_by_driver` con `cancel_reason_code=no_show`,
  así ninguna app se rompe. Solo se puede desde `driver_arrived` cuando pasa `no_show_at` (llegada + 5 min);
  antes responde 409 `no_show_too_early`. Cuenta contra el pasajero, no contra el motorizado.
- **Reasignación:** si el motorizado cancela con cualquier otro motivo, el viaje vuelve a `searching` con un
  plazo de búsqueda nuevo y se ofrece a otros (nunca al mismo). El pasajero recibe "Buscando otro motorizado";
  para el motorizado el viaje aparece cancelado. El chat del motorizado anterior no lo ve el nuevo.
- **Tasas** (últimos 30 días): aceptación, cancelación del motorizado (sobre viajes aceptados), cancelación
  del pasajero (sobre viajes que tuvieron motorizado) y no-shows. Un bucle del worker (latido `quality`) las
  recalcula cada 10 min en `quality_stats`; la pantalla del motorizado y la ficha del admin las calculan en vivo.
- **Consecuencias sin dinero:** motorizado con 15% de cancelación recibe un aviso, con 25% menor prioridad en
  el despacho y con 35% aparece para revisar (con al menos 10 viajes aceptados). Calificación menor a 4,3
  con 20 o más calificaciones: revisar. Pasajero con 2 no-shows en 30 días: aviso; con 3: pausa de 24 h para
  pedir. Cada aviso llega una sola vez (bandeja y push).
- **Pausas:** `quality_pauses`. `POST /drivers/me/online`, `POST /rides/quote` y `POST /rides` responden 403
  `temporarily_paused` con `until` y `reason`; el evento `quality.paused` avisa al momento y el motorizado
  queda desconectado. El admin puede levantarlas.
- **Despacho:** dentro de cada radio, la distancia se multiplica por la calidad (peso 0,2 de aceptación y
  calificación; +50% para quien está en menor prioridad). Un motorizado nuevo sin datos no se castiga.
- `GET /drivers/me/quality`; en el admin `/admin/quality/users`, `/admin/quality/users/{id}`,
  `/admin/quality/cancellations` y `/admin/quality/pauses/{id}/lift`. Permisos `quality.view` y
  `quality.manage`.
- Al borrar una cuenta se borra el texto libre de sus cancelaciones; el código del motivo queda.
### Admin
- Página **Calidad** (en Operación): motorizados y pasajeros bajo los umbrales o en pausa, y cancelaciones por
  motivo. Fichas de usuario y motorizado con tasas, tendencia de 8 semanas y pausas (con "Levantar pausa").
  El detalle del viaje muestra sus cancelaciones y reasignaciones. Bloque **Calidad del servicio** en Ajustes.
### App
- Pasajero: hoja de cancelación con motivos y aviso fuera de la gracia, contador "Tu motorizado te espera",
  "Buscando otro motorizado" cuando el motorizado cancela y aviso claro si la cuenta está en pausa.
- Motorizado: hoja de cancelación con motivos, contador de espera con "No se presentó" al cumplirse el tiempo,
  pantalla **Mi calidad** y pantalla de pausa con cuenta regresiva.
### Pendiente
- Las tasas empiezan desde cero: las cancelaciones de antes de este cambio no tienen motivo ni etapa.
- Revisar los umbrales con datos reales tras las primeras semanas.
