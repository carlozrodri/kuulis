# Contrato de API · Referidos (doc 22)

Base `/api/v1`, mismo sobre de errores (`{"error": {"code", "message", "details"}}`). Montos como texto con dos
decimales (`"5.00"`), en USDT (= USD).

Decidido (Carlos aprobó las recomendaciones del doc 22): **solo motorizados invitan motorizados** al lanzar, y el
premio es **5 USD de crédito tras 20 viajes en 30 días**. Los referidos de pasajeros quedan para después.

## Programa

`referral_program` (config, se edita desde la página Referidos del admin):

```
ReferralProgram = {
  enabled: true,               // apagado: no se aceptan códigos nuevos ni se pagan premios (quedan en espera)
  reward_usd: "5.00",          // 0–1000. Crédito en la billetera de quien invita
  required_trips: 20,          // 1–500. Viajes del invitado que cuentan
  window_days: 30,             // 1–365. Desde la aprobación del invitado
  referred_free_month: false,  // el invitado también gana un mes gratis al cumplir
  monthly_cap: 10,             // 0–1000. Premios por persona al mes (0 = sin tope)
  budget_usd: "500.00",        // 0–1.000.000. Pagado + retenido nunca lo supera
  starts_at: null, ends_at: null  // ventana para aceptar códigos nuevos (null = sin límite)
}
```

## Cómo se gana

1. Un motorizado **aprobado** tiene su código (6 caracteres sin 0/O/1/I/L) y enlace `https://<web>/i/CODIGO`.
2. Un motorizado nuevo escribe el código **antes de su primer viaje** (`POST /referrals/redeem`).
3. Al aprobar al invitado empieza su ventana: `deadline_at = aprobación + window_days`.
4. Tras cada viaje completado del invitado (tarea encolada), al aprobarlo y cada hora (barrido) se evalúa:
   - Quien invita cerró o borró su cuenta: `rejected`, `reason = inviter_inactive`.
   - **Datos compartidos** entre los dos (teléfono, dispositivo, Binance Pay ID, cédula, RIF o placa, por las
     marcas de identidad del doc 12): `rejected` con `reason = shared_identity`, sin premio, y alerta de riesgo
     `referral` (doc 16).
   - **Viajes que cuentan**: completados hasta `deadline_at`, sin quien invita como pasajero y sin los marcados
     como viaje sospechoso (alerta abierta o confirmada).
   - Pasado el plazo sin llegar: `rejected`, `reason = expired`.
   - Al llegar: `qualified` (y el mes gratis del invitado si `referred_free_month`). Luego se paga salvo que:
     programa apagado (`program_off`), tope del mes de quien invita (`monthly_cap`) o sin presupuesto (`budget`):
     queda `qualified` con ese motivo y el barrido lo paga cuando se pueda.
   - Si quien invita o el invitado tienen riesgo ≥ `risk.freeze_score`: `held` (`risk_score`), el monto se
     reserva del presupuesto y espera a una persona.
5. Pago: movimiento de billetera `referral_bonus` (no retirable a efectivo, no suma a la ganancia del mes para
   el tramo de la cuota), notificación push y en la bandeja, una sola vez por invitado.

Estados: `pending` → `qualified` | `held` | `rewarded` | `rejected`. Las invitaciones de la primera versión (un mes
gratis por el primer viaje) quedan `rewarded` con `reward_kind = free_month`.

## App

| Método | Ruta | Notas |
| --- | --- | --- |
| GET | `/referrals/me` | `ReferralSummary` |
| POST | `/referrals/redeem` | `{code}` → `ReferralSummary`. Errores abajo |
| GET | `/referrals/codes/{code}` | Sin sesión (30/min por IP). `{code, name, program: ProgramInfo}`; 404 `referral_code_invalid` |

```
ReferralSummary = {
  code: "AB3K7Q" | null,       // null hasta ser motorizado aprobado
  share_url: "https://kuulis…/i/AB3K7Q" | null,
  invited, rewarded,           // invitados y premiados
  earned_usd: "10.00",         // crédito ganado
  free_months,                 // meses gratis sin usar
  referred_by: "Luis G." | null,
  can_redeem: bool,            // motorizado sin primer viaje, sin código y con el programa abierto
  program: ProgramInfo,
  invitees: [Invitee]          // los 50 más recientes
}
ProgramInfo = {active, reward_usd, required_trips, window_days, referred_free_month, ends_at}
Invitee = {
  name: "Nuevo R.", joined_at, approved: bool,
  status: "pending" | "reviewing" | "rewarded" | "expired" | "not_eligible",  // nunca el motivo de fraude
  trips, required_trips, deadline_at | null, reward_usd | null, reward_kind: "wallet_credit" | "free_month" | null
}
```

Errores de `redeem`: `referral_code_invalid` (400), `referral_own_code` (400), `referral_driver_only` (403),
`referral_closed` (409, ya hizo su primer viaje), `referral_already_used` (409), `referral_program_closed` (409).

La web abre la app con el código ya escrito: `kuulis://profile/invite?code=AB3K7Q`.

Estado de cuenta (`GET /wallet/me/statements`): `movements.referral_bonuses`.

## Admin

Permisos `referrals.view` (Operaciones y Finanzas) y `referrals.manage` (Operaciones). Todo cambio queda en la
auditoría.

| Método | Ruta | Permiso | Notas |
| --- | --- | --- | --- |
| GET | `/admin/referrals/overview` | `referrals.view` | `{program, counts: [{status, count}], paid_usd, held_usd, month_paid_usd, budget_left_usd, free_months, alerts, waiting: {reason: n}}` |
| GET | `/admin/referrals` | `referrals.view` | `?status&alerts&q&user_id&limit&offset` → `Page[ReferralAdmin]`. `alerts`: retenidas y rechazos por datos compartidos sin revisar. `q`: nombre, correo o código |
| GET | `/admin/referrals/ranking` | `referrals.view` | `?limit` (1–50) → `[{user, invited, rewarded, earned_usd}]` |
| GET | `/admin/referrals/{id}` | `referrals.view` | `ReferralAdmin` |
| PUT | `/admin/referrals/program` | `referrals.manage` | `ReferralProgram` completo → el guardado (`referrals.program_update`) |
| POST | `/admin/referrals/{id}/release` | `referrals.manage` | `{note?}`. Paga una `held` o una `qualified` en espera (ignora el tope del mes, no el presupuesto: 409 `referral_budget_exhausted`) |
| POST | `/admin/referrals/{id}/reject` | `referrals.manage` | `{note?}`. Sin premio (`reason = staff`); una retenida avisa a quien invita. Sobre un rechazo por datos compartidos lo marca revisado |
| POST | `/admin/referrals/{id}/reopen` | `referrals.manage` | `{note?}`. Un rechazo equivocado (familiares con el mismo teléfono): se evalúa de nuevo sin revisar datos compartidos y con ventana nueva si venció |

```
ReferralAdmin = {
  id, code, status, referrer: UserBrief, referred: UserBrief, trips, required_trips, deadline_at,
  qualified_at, rewarded_at, reward_kind, reward_amount, reason, details: {shared?, risk_scores?, free_month?,
  override?}, note, reviewed_at, created_at
}
```

Errores: `referral_not_found` (404), `referral_invalid_status` (409), `referral_budget_exhausted` (409).
