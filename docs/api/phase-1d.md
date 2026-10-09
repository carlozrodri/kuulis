# Contrato de API · Fase 1D (billetera y suscripción)

Base `/api/v1`, mismo sobre de errores. Montos en USDT (= USD) como string con 2 decimales. Los meses se cuentan
en hora de Caracas y se escriben `"2026-10"`.

## Billetera

La billetera solo existe para usuarios con perfil de motorizado. Todo movimiento queda en el libro contable;
el saldo nunca es negativo y no se puede retirar.

`WalletEntry.kind`:

| kind | Signo | Origen |
| --- | --- | --- |
| `promo_credit` | + | Descuento de una promoción (1C) |
| `top_up` | + | Recarga confirmada |
| `transfer_in` / `transfer_out` | + / − | Transferencia entre motorizados |
| `subscription_fee` | − | Cobro de la cuota mensual |
| `adjustment` | ± | Ajuste manual de un admin (con motivo) |

`details` según el tipo: `top_up` → `{method, reference}`; `transfer_*` → `{counterpart_name, note}`;
`subscription_fee` → `{month}`; `adjustment` → `{reason}`.

| Método | Ruta | Respuesta |
| --- | --- | --- |
| GET | `/wallet/me` | `{balance, currency: "USDT", binance_pay_id, transfer: {limit, sent_this_month, available}}` |
| PUT | `/wallet/me/binance` | `{binance_pay_id}` (solo dígitos, 6–20) → igual que `GET /wallet/me`. Único entre usuarios (409 `binance_pay_id_taken`) |

## Recargas

Canal: **Binance Pay a la cuenta de Kuulis**. El motorizado registra su Binance Pay ID y envía USDT al Pay ID de
Kuulis. Si hay credenciales de Binance (`BINANCE_API_KEY` / `BINANCE_API_SECRET`, solo lectura), el worker
revisa cada minuto el historial de Binance Pay (`/sapi/v1/pay/transactions`) y acredita solo cada pago entrante
en USDT cuyo pagador coincida con el Binance Pay ID de un motorizado. Un pago sin dueño queda como `unmatched`
para que un admin lo asigne. Sin credenciales, todo se confirma a mano en el admin.

`TopUp = {id, status, amount, method: "binance_pay", reference, payer_binance_id, payer_name, note, created_at, completed_at, rejection_reason}`

`status`: `pending` (el motorizado avisó que pagó), `completed`, `rejected`, `unmatched` (pago recibido sin dueño).

| Método | Ruta | Quién | Notas |
| --- | --- | --- | --- |
| GET | `/wallet/top-up-info` | motorizado | `{method: "binance_pay", pay_id, account_name, min_amount, automatic: bool}` |
| POST | `/wallet/me/top-ups` | motorizado | `{amount, reference?}`: aviso de pago (el `reference` es el ID de la orden de Binance). Mínimo `topup_min_amount`. Máximo 3 avisos pendientes (409 `too_many_pending_top_ups`) |
| GET | `/wallet/me/top-ups` | motorizado | Paginado |
| GET | `/admin/top-ups` | staff | `?status&q&limit&offset` (incluye nombre y email del motorizado) |
| POST | `/admin/top-ups/{id}/confirm` | admin | `{amount, reference?}`: acredita (el monto real recibido) |
| POST | `/admin/top-ups/{id}/reject` | admin | `{reason}` |
| POST | `/admin/top-ups/{id}/assign` | admin | `{user_id}`: asigna un pago `unmatched` a un motorizado y lo acredita |

Cuando una recarga se acredita, se marca `completed` el aviso pendiente más antiguo del mismo motorizado (si
hay) y se intenta cobrar cualquier cuota pendiente.

## Transferencias

| Método | Ruta | Notas |
| --- | --- | --- |
| GET | `/wallet/recipients` | `?q=` email o teléfono exacto → `{user_id, name}` (nombre corto, p. ej. "Luis G.") o 404 `recipient_not_found`. Solo motorizados aprobados o suspendidos |
| POST | `/wallet/me/transfers` | `{to_user_id, amount, note?}` → `WalletEntry` del envío |

Errores: `insufficient_balance` (409), `transfer_limit_exceeded` (409, `details: {limit, sent_this_month, available}`),
`recipient_not_found` (404), `transfer_to_self` (400). El límite (`transfer_monthly_limit`) cuenta solo lo
enviado en el mes calendario. El receptor recibe push y bandeja.

## Suscripción

**Tramos.** `FeeSchedule = {id, effective_month: "2026-11", tiers: [{above: "0.00", fee: "0.00"}, {above: "100.00", fee: "5.00"}, …], created_by, created_at}`.
La cuota de un mes es el `fee` del tramo con el mayor `above` que la ganancia supere; con ganancia 0, la cuota es 0.
Cada mes usa el esquema vigente más reciente con `effective_month` ≤ ese mes. Los esquemas nuevos solo pueden
empezar el mes siguiente o después, así que un mes cerrado nunca cambia. El esquema inicial es la tabla de
`business-model.md` (de 0 a 30 USD).

**Ganancia del mes** = suma de `total` de los viajes completados en el mes. Los viajes completados antes de que
termine el periodo gratis (`first_trip_completed_at` + `subscription_free_months` meses) no cuentan.

**Cobro.** El día 1 de cada mes (hora de Caracas) el worker crea un `Charge` por cada motorizado con viajes
completados el mes anterior:
- `fee` 0 (por ganancia o porque el mes cayó completo en el periodo gratis) → `waived`.
- Saldo suficiente → se descuenta y queda `paid`.
- Si no → `pending`, con `due_at` = momento del cobro + `subscription_grace_days` días. Cada vez que entra
  saldo se reintenta. Pasado `due_at` sin pagar, el motorizado queda **bloqueado**: no puede conectarse
  (403 `subscription_overdue`) ni recibir ofertas, hasta que la cuota se pague o un admin la condone.

`Charge = {id, month, earnings, fee, status: "paid" | "pending" | "waived", free_period: bool, due_at, paid_at, waived_reason}`

| Método | Ruta | Quién | Respuesta |
| --- | --- | --- | --- |
| GET | `/wallet/me/subscription` | motorizado | `{month, earnings, estimated_fee, free_until, in_free_period, tiers, next_charge_at, pending: [Charge], overdue, blocked}` (mes en curso) |
| GET | `/wallet/me/charges` | motorizado | Paginado de `Charge` |
| GET | `/admin/subscriptions/charges` | staff | `?month&status&q&limit&offset`, con nombre y email |
| POST | `/admin/subscriptions/charges/{id}/waive` | admin | `{reason}` → `Charge` (desbloquea) |
| POST | `/admin/subscriptions/run` | admin | `{month}` → `{created, paid, pending, waived}`; corre el cobro de un mes ya cerrado (idempotente) |
| GET | `/admin/subscriptions/schedules` | staff | Lista de `FeeSchedule`, la vigente primero |
| POST | `/admin/subscriptions/schedules` | admin | `{effective_month, tiers}`: tramos ordenados por `above`, el primero con `above` 0 y fees de 0 a 1000 |

El motorizado recibe push y bandeja al cobrarse la cuota (pagada o pendiente), un día antes de vencer y al quedar
bloqueado.

## Admin de billeteras

| Método | Ruta | Quién | Notas |
| --- | --- | --- | --- |
| GET | `/admin/wallets/{user_id}` | staff | `{user: {id, name, email}, balance, binance_pay_id, sent_this_month, entries (20 últimos), pending_charges}` |
| GET | `/admin/wallets/{user_id}/entries` | staff | Paginado |
| POST | `/admin/wallets/{user_id}/adjust` | admin | `{amount (±), reason}`; no puede dejar saldo negativo (409 `insufficient_balance`) |
| GET | `/admin/transfers` | staff | `?q&limit&offset`: envíos con remitente, receptor, monto y nota |

## Configuración nueva (`AppConfig`)

| Clave | Defecto | Descripción |
| --- | --- | --- |
| `topup_min_amount` | `"5.00"` | Recarga mínima |
| `topup_binance_pay_id` | `""` | Binance Pay ID de Kuulis que ve el motorizado |
| `topup_account_name` | `"Kuulis"` | Nombre de la cuenta de Binance de Kuulis |
| `transfer_monthly_limit` | `"50.00"` | Máximo enviado por mes |
| `subscription_free_months` | `3` | Meses gratis desde el primer viaje |
| `subscription_grace_days` | `7` | Días para pagar antes del bloqueo |
