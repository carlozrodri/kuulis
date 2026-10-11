# 16 · Antifraude

**Prioridad:** P1 · **Área:** API · Mobile · Admin · **Depende de:** 11, 15

## Objetivo
Detectar y frenar los abusos que cuestan dinero o confianza: viajes falsos para cobrar promociones, GPS falso,
cuentas múltiples, reventa de saldo y manipulación de calificaciones. Con reglas simples, revisables por
personas y sin servicios de pago.

## Estado actual
- Promociones con presupuesto, tope por pasajero y **alerta de pares pasajero–motorizado** con 3+ viajes con
  promoción en 30 días (página `promotions/alerts`).
- Transferencias entre motorizados con límite mensual de lo enviado.
- Unicidad de cédula y placa.
- No se detecta GPS simulado, ni cuentas en el mismo dispositivo, ni viajes imposibles (velocidad/distancia).
- El precio se calcula con la ruta estimada, no con la real.

## Alcance
### Incluye
1. **Huella de dispositivo**: id de instalación de la app (`expo-application` / Android ID), modelo, versión.
   Se registra por sesión. Reglas: más de N cuentas en un mismo dispositivo, pasajero y motorizado del mismo
   viaje con el mismo dispositivo (viaje consigo mismo).
2. **GPS simulado**: Android informa si la ubicación es simulada (`mocked`); la app lo envía con cada posición.
   Motorizado con ubicación simulada: no recibe ofertas y aparece en alertas. Además, saltos imposibles
   (velocidad > 150 km/h entre puntos).
3. **Viajes sospechosos** (con el recorrido de 11): viaje completado con muy poco movimiento real, duración
   mucho menor a la estimada, inicio y fin en el mismo punto, motorizado y pasajero siempre juntos (la regla de
   promociones existente se generaliza a todos los viajes).
4. **Puntuación de riesgo** por usuario (0–100) a partir de las señales; umbrales que congelan acciones
   sensibles (créditos de promoción pendientes de revisión, transferencias salientes bloqueadas) hasta que un
   humano revise.
5. **Créditos de promoción en revisión**: si el viaje es sospechoso, el crédito queda `held` en vez de
   acreditarse; el admin lo libera o lo anula.
6. **Transferencias**: alertas por cadenas (A→B→C en poco tiempo), receptores que reciben de muchos emisores,
   cuentas nuevas que reciben saldo, y retención opcional de 24 h para la primera transferencia de una cuenta.
7. **Cuentas vetadas**: lista de hashes de email, cédula, teléfono, Binance Pay ID y dispositivo de cuentas
   suspendidas definitivamente o eliminadas por fraude, para bloquear el registro de nuevo.
8. **Calificaciones**: ignorar calificaciones entre pares sospechosos y detectar patrones de 5 estrellas
   recíprocas repetidas.

### Fuera
- Servicios comerciales de detección de fraude.
- Aprendizaje automático (primero reglas; con datos, se evalúa).

## App móvil
### Motorizado
- Envía `mocked: true|false` con cada ubicación (Android) y el id de instalación al iniciar sesión.
- Si se detecta GPS simulado: aviso "Desactiva la ubicación simulada para recibir viajes".
### Pasajero
- Envía el id de instalación al iniciar sesión. Sin cambios visibles.

## Admin
- **Riesgo**: bandeja de alertas por tipo (dispositivo compartido, GPS simulado, viaje sospechoso,
  transferencias, pares frecuentes) con evidencia (mapa del recorrido, lista de cuentas relacionadas) y
  acciones: descartar, liberar o anular crédito, suspender (13/06), vetar.
- Ficha de usuario: puntuación de riesgo, cuentas relacionadas por dispositivo, Binance Pay ID o teléfono.
- Configuración de reglas y umbrales.

## API y datos
- `device_fingerprints` (`install_id` hash, `user_id`, `platform`, `model`, `first_seen`, `last_seen`).
- `risk_signals` (`user_id`, `ride_id`, `kind`, `score`, `evidence` JSONB, `status`, `reviewed_by`).
- `users.risk_score` (cache) y `blocked_identifiers` (`kind`, `hash`, `reason`, `created_by`).
- `promotion_redemptions.status` agrega `held`.
- `wallet_transfers.status` agrega `held` con `release_at`.
- Mensaje `location` del WebSocket y `POST /drivers/me/location` aceptan `mocked`.
- Tarea `risk.evaluate` al completar cada viaje (encolada) y `risk.sweep` diaria.
- Error `registration_blocked` (403) sin revelar el motivo.

## Criterios de aceptación
- Un viaje entre dos cuentas del mismo teléfono genera alerta y su crédito de promoción queda retenido.
- Un motorizado con GPS simulado deja de recibir ofertas en menos de 1 minuto.
- Registrar una cuenta nueva con una cédula vetada falla con `registration_blocked`.
- Las alertas se pueden revisar y cada decisión queda en la auditoría (06).

## Dependencias
11 (recorrido del viaje), 15 (tasas por persona). 06 para auditoría.

## Preguntas para Carlos
1. ¿Retener 24 h la primera transferencia de cada cuenta? Recomendado: sí.
