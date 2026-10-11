# 22 · Referidos

**Prioridad:** P2 · **Área:** API · Mobile · Admin · **Depende de:** 16, 17

## Objetivo
Resolver el arranque en frío (riesgo listado: sin motorizados no hay pasajeros) con invitaciones baratas:
motorizados que traen motorizados y pasajeros que traen pasajeros, con premios que Kuulis controla y que no se
pueden abusar.

## Estado actual
- No existe ningún programa de referidos.
- Existen promociones con presupuesto (para premios de pasajeros) y billetera del motorizado (para premios de
  motorizados, como crédito no retirable).

## Alcance
### Incluye
1. **Código y enlace personal** por usuario (`kuulis.app/i/CARLOS7`), compartible por WhatsApp con vista previa.
2. **Motorizado invita motorizado**: cuando el invitado es aprobado y completa N viajes (configurable, por
   ejemplo 20) en sus primeros 30 días, el que invitó recibe crédito en su billetera (por ejemplo 5 USD, paga
   una cuota). Opcional: el invitado recibe un mes gratis extra.
3. **Pasajero invita pasajero**: el invitado recibe descuento en su primer viaje (una promoción automática
   ligada al referido) y el que invitó recibe descuento cuando el invitado completa su primer viaje.
4. **Topes**: máximo de referidos premiados por mes por persona, presupuesto total del programa, fechas.
5. **Antifraude** (16): sin premio si comparten dispositivo, Binance Pay ID o teléfono, o si el viaje es
   sospechoso; premios en `held` hasta revisión cuando el riesgo es alto.

### Fuera
- Premios en efectivo o retirables.

## App móvil
### Pasajero
- Perfil → "Invita y gana": código, botón compartir, estado de cada invitado (registrado, primer viaje hecho).
- En el registro: campo "¿Te invitó alguien?" (se llena solo si llegó por enlace).
### Motorizado
- Igual, con el progreso del invitado (viajes hechos de los N requeridos) y el crédito ganado.

## Admin
- **Referidos**: configuración del programa (premios, requisitos, topes, presupuesto, fechas), lista de
  referidos con estado, premios pagados/retenidos y costo total, ranking de quienes más invitan, alertas.

## API y datos
- `users.referral_code` (único, legible) y `referrals` (`referrer_id`, `referred_id`, `role`, `status` pending|
  qualified|rewarded|rejected, `qualified_at`, `reward_entry_id`, `reason`).
- `AppConfig.referral_program` (premios, requisitos, topes, presupuesto, activo).
- Al aprobar un motorizado y al completar viajes se evalúa la calificación del referido (tarea encolada).
- Crédito en billetera como movimiento nuevo `referral_bonus` (no suma a la ganancia del mes, igual que las
  promociones).
- `GET /referrals/me`, `POST /auth/register` acepta `referral_code`; página pública `/i/{code}` en la web (08).

## Criterios de aceptación
- Un motorizado invitado que completa 20 viajes en 30 días genera el crédito al que invitó, una sola vez.
- Un referido desde el mismo dispositivo no genera premio y aparece en alertas.
- El costo total del programa nunca supera el presupuesto configurado.

## Dependencias
16 (señales de fraude), 17 (movimientos de billetera nuevos y cierres).

## Preguntas para Carlos
1. ¿Premio por motorizado referido? Recomendado: 5 USD de crédito tras 20 viajes en 30 días.
2. ¿Programa de pasajeros desde el inicio o solo de motorizados? Recomendado: solo motorizados al lanzar.
