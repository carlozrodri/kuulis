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
2. ¿Pausas automáticas para motorizados que rechazan mucho? Recomendado: sí, suaves (15 min).
