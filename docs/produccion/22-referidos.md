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
1. ~~¿Premio por motorizado referido?~~ **Decidido** (2026-10-11, Carlos aprobó las recomendaciones): 5 USD de
   crédito tras 20 viajes en 30 días. Reemplaza el mes gratis por el primer viaje de la primera versión.
2. ~~¿Programa de pasajeros desde el inicio o solo de motorizados?~~ **Decidido** (2026-10-11): solo motorizados
   al lanzar. Pasajero invita pasajero queda para cuando haya datos.

## Implementación (2026-10-17)
Contrato en [`docs/api/referidos.md`](../api/referidos.md).
- Parte de lo que ya existía (`da5bb1e`): código por motorizado aprobado, `POST /referrals/redeem` antes del
  primer viaje y la pantalla Invita y gana. El premio cambia a crédito `referral_bonus` en la billetera; los meses
  gratis ya ganados se siguen usando en la cuota.
- `AppConfig.referral_program`: premio, viajes, días desde la aprobación, mes gratis opcional para el invitado,
  tope por persona al mes, presupuesto total y fechas. Se edita en la página Referidos.
- `referrals` gana estado (`pending`, `qualified`, `held`, `rewarded`, `rejected`), viajes que cuentan, plazo,
  premio y revisión. Se evalúa tras cada viaje (tarea encolada), al aprobar al invitado y en un barrido cada hora
  (vence plazos y paga los que esperaban tope o presupuesto).
- Antifraude: sin premio si comparten teléfono, dispositivo, Binance Pay ID, cédula, RIF o placa (marcas del
  doc 12), con alerta `referral` en Riesgo; no cuentan los viajes con quien invita de pasajero ni los marcados
  como sospechosos; riesgo alto retiene el premio hasta revisión. El presupuesto se bloquea al pagar, así que
  pagado + retenido nunca lo supera.
- Admin: página Referidos (dinero → Referidos) con invitaciones, alertas, pagar/rechazar/reabrir, ranking y el
  programa. Permisos `referrals.view` (Operaciones, Finanzas) y `referrals.manage` (Operaciones).
- App: Invita y gana explica el premio, comparte el enlace `/i/CODIGO` por WhatsApp y muestra cada invitado con
  su progreso; el movimiento y el estado de cuenta muestran el premio.
- Web: página `/i/{código}` con vista previa para WhatsApp, el código, cómo usarlo, descargar la app y abrirla con
  el código ya escrito (`kuulis://profile/invite?code=…`).
- Fuera por ahora: referidos de pasajeros (decidido) y el código ya puesto al instalar desde cero (necesita las
  tiendas; ver `docs/pending.md`).
