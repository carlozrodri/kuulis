# Contrato de API · Fase 1E (operación en el admin)

Base `/api/v1`, mismo sobre de errores. Montos en USD como string con 2 decimales. Las fechas de los filtros
(`from`, `to`) son días en hora de Caracas (`"2026-10-09"`), ambos incluidos. Viajes en vivo e historial ya
existen desde 1B (`/admin/rides`, `/admin/rides/live`, `/admin/rides/{id}`).

## Reportes

Pasajeros y motorizados pueden reportar un problema, sobre un viaje o en general. El equipo los atiende en el
admin.

`category`: `safety` (me sentí en peligro), `harassment` (acoso o insultos), `driving` (manejo imprudente),
`fare` (cobro distinto al acordado), `vehicle_mismatch` (la moto o la persona no coinciden), `lost_item`
(objeto olvidado), `no_show` (no se presentó), `app_issue` (falla de la app), `other`.

`priority`: `urgent` para `safety` y `harassment`, `normal` para el resto (el admin puede cambiarla).

`status`: `open` → `in_review` → `resolved` | `dismissed`.

`Report = {id, category, description, status, priority, ride_id, reporter_role: "passenger" | "driver" | null, created_at, updated_at, resolution, resolved_at}`

Reglas:

- `description`: 10–2000 caracteres.
- Con `ride_id`: quien reporta debe ser el pasajero o el motorizado de ese viaje, y el viaje debe haber tenido
  motorizado asignado (403 `not_ride_participant`, 409 `ride_without_driver`). La persona reportada es la otra
  parte del viaje y `reporter_role` dice desde qué lado se reporta. Un solo reporte abierto por viaje y por
  persona (409 `report_already_open`, `details.report_id`).
- Sin `ride_id`: reporte general (`reporter_role` null, sin persona reportada). Se permiten `app_issue`,
  `lost_item` y `other`; el resto exige viaje (422).
- Máximo 5 reportes abiertos (`open` o `in_review`) por usuario (409 `too_many_open_reports`).
- Al resolver o descartar, quien reportó recibe una notificación (`kind: "report"`) con la respuesta.

| Método | Ruta | Quién | Notas |
| --- | --- | --- | --- |
| POST | `/reports` | usuario | `{category, description, ride_id?}` → 201 `Report` |
| GET | `/reports/me` | usuario | Paginado, más recientes primero |
| GET | `/reports/me/{id}` | usuario | `Report` |
| GET | `/admin/reports` | staff | `?status&category&priority&q&user_id&ride_id&limit&offset`. `q` busca nombre o email de ambas partes. `user_id` trae los reportes donde esa persona reporta o es reportada. Orden: urgentes abiertos primero, luego más recientes. Respuesta: página de `ReportAdminRead` más `counts: {open, in_review, urgent_open}` |
| GET | `/admin/reports/{id}` | staff | `ReportAdminDetail` |
| PATCH | `/admin/reports/{id}` | staff | `{status?: "open" \| "in_review", priority?, assigned_to_id?: uuid \| null}` |
| POST | `/admin/reports/{id}/notes` | staff | `{body}` (1–2000) → `ReportNote`, nota interna |
| POST | `/admin/reports/{id}/resolve` | staff | `{status: "resolved" \| "dismissed", resolution}` (resolution 3–1000, la ve quien reportó). 409 `report_closed` si ya estaba cerrado |
| POST | `/admin/reports/{id}/reopen` | staff | Vuelve a `in_review` |

`ReportAdminRead = Report + {reporter: UserBrief, reported: UserBrief | null, assigned_to: UserBrief | null, notes_count}`

`ReportAdminDetail = ReportAdminRead + {ride: RideAdminRead | null, notes: ReportNote[], reported_summary: PersonSummary | null, reporter_summary: PersonSummary}`

`UserBrief = {id, name, email}`

`PersonSummary = {user_id, name, email, phone, role_in_ride, rating_avg, rating_count, rides_completed, reports_against: {total, open, last_90_days}, suspension: Suspension | null, driver_profile_id, driver_status}`

`ReportNote = {id, body, kind: "note" | "status" | "suspension", author: UserBrief | null, created_at}`

Las notas con `kind` distinto de `note` las escribe el sistema: cambios de estado, prioridad o asignación, y
suspensiones hechas desde el reporte.

## Suspensiones de cuenta

Herramienta de moderación para cualquier usuario (pasajero, motorizado o ambos). La suspensión del perfil de
motorizado de 1A (`/admin/drivers/{id}/suspend`) se mantiene para temas de documentos y aprobación.

`Suspension = {reason, suspended_at, until: datetime | null, by: UserBrief | null}`. `until` null significa
indefinida. Una suspensión vencida deja de aplicar sola, sin ningún proceso.

Mientras está suspendida, la persona:

- puede iniciar sesión, ver su historial, su billetera y crear reportes;
- no puede pedir viajes: `POST /rides/quote` y `POST /rides` responden 403 `account_suspended` con
  `details: {until, reason}`;
- no puede conectarse como motorizado (`POST /drivers/me/online` → 403 `account_suspended`), y si estaba
  conectado queda desconectado y deja de recibir ofertas;
- los viajes que tenga en curso siguen (el admin puede cancelarlos desde el viaje).

`GET /users/me` y `UserRead` agregan `suspension: Suspension | null` (solo si está vigente).

| Método | Ruta | Quién | Notas |
| --- | --- | --- | --- |
| POST | `/admin/users/{id}/suspend` | staff | `{reason (3–500), until?: datetime, report_id?}`. `until` debe ser futuro. No se puede suspender a staff ni a admin (403 `cannot_suspend_staff`). Si ya estaba suspendida, reemplaza la suspensión. Con `report_id` queda una nota en ese reporte. Notifica a la persona (`kind: "account"`) |
| POST | `/admin/users/{id}/unsuspend` | staff | Levanta la suspensión y notifica. 409 `not_suspended` |
| GET | `/admin/users/{id}/suspensions` | staff | Historial: `[{reason, suspended_at, until, by, lifted_at, lifted_by, report_id}]`, más recientes primero |

`GET /users` (lista del admin) acepta `?suspended=true|false`. `GET /users`, `GET /users/{id}`, `GET /users/me` y las respuestas de login traen `suspension`. `POST /admin/users/{id}/unsuspend` responde 204.

## Finanzas y conciliación

Para cuadrar lo que entró a la cuenta de Binance de Kuulis con lo que se acreditó, y ver el dinero que hay en
las billeteras.

`GET /admin/finance/summary?from&to` (staff):

```json
{
  "from": "2026-10-01", "to": "2026-10-31",
  "top_ups": {
    "completed": {"count": 12, "amount": "140.00"},
    "completed_auto": {"count": 9, "amount": "110.00"},
    "completed_manual": {"count": 3, "amount": "30.00"},
    "pending": {"count": 2, "amount": "15.00"},
    "unmatched": {"count": 1, "amount": "7.00"},
    "rejected": {"count": 1, "amount": "5.00"}
  },
  "fees": {"collected": "85.00", "pending": "20.00", "waived_count": 31},
  "promo_credits": "12.40",
  "adjustments": {"credit": "3.00", "debit": "1.00"},
  "transfers": {"count": 4, "amount": "45.00"},
  "wallet_balances": "210.55",
  "by_day": [{"date": "2026-10-01", "top_ups": "20.00", "fees": "85.00", "promo_credits": "0.40"}]
}
```

- Recargas por la fecha en que se acreditaron (`completed_at`); pendientes, sin asignar y rechazadas por fecha
  de creación. `completed_auto` son las que vinieron de la conciliación automática.
- `fees.collected` son los movimientos `subscription_fee` del periodo; `fees.pending` es el total de cuotas
  pendientes hoy, sin importar el periodo.
- `wallet_balances` es la suma de todos los saldos en este momento (lo que Kuulis "debe" en servicio).
- Rango máximo 366 días (422).

Exportaciones CSV (staff, UTF-8 con BOM para que Excel lo abra bien, separador `,`):

| Ruta | Columnas |
| --- | --- |
| `GET /admin/finance/entries.csv?from&to&kind` | `fecha (Caracas), usuario, email, tipo, monto, saldo_después, referencia, detalle` |
| `GET /admin/finance/top-ups.csv?from&to&status` | `creada, acreditada, estado, origen, monto, motorizado, email, binance_pay_id_pagador, nombre_pagador, transacción, referencia, nota` |

## Métricas

`GET /admin/metrics?from&to&area` (staff). `area` es el nombre de una ciudad de `service_areas`; sin `area`,
todas. Rango máximo 366 días.

```json
{
  "from": "2026-10-01", "to": "2026-10-09", "area": null,
  "totals": {
    "rides_requested": 120, "rides_completed": 96, "rides_cancelled_passenger": 10,
    "rides_cancelled_driver": 4, "rides_cancelled_admin": 1, "rides_no_drivers": 9,
    "completion_rate": 0.8, "gmv": "230.40", "discounts": "12.40", "avg_fare": "2.40",
    "avg_distance_m": 4200, "avg_assign_s": 35, "avg_pickup_s": 290, "avg_trip_s": 840,
    "active_drivers": 14, "active_passengers": 61, "new_passengers": 40, "new_drivers": 5,
    "avg_rating_drivers": 4.8, "avg_rating_passengers": 4.9
  },
  "by_day": [
    {"date": "2026-10-01", "requested": 10, "completed": 8, "cancelled": 1, "no_drivers": 1, "gmv": "19.20", "active_drivers": 4}
  ],
  "by_hour": [{"hour": 0, "requested": 1, "completed": 1}],
  "top_drivers": [{"user_id": "…", "name": "Luis G.", "rides": 30, "earnings": "72.00", "rating_avg": 4.9}]
}
```

- Un viaje cuenta en el día (hora de Caracas) en que se pidió, y en la ciudad donde está su punto de recogida.
- `gmv` es la suma de precios (`fare`) de los viajes completados; `discounts`, lo que pagó Kuulis en promociones.
- `avg_assign_s`: de pedido a motorizado asignado. `avg_pickup_s`: de asignado a "llegué". `avg_trip_s`: de
  inicio a fin.
- `active_*`: personas distintas con al menos un viaje completado en el rango. `new_passengers`: cuentas creadas
  en el rango. `new_drivers`: motorizados aprobados en el rango.
- `by_hour`: viajes por hora del día (0–23, hora de Caracas) sumando todo el rango, para ver horas pico.
- `top_drivers`: los 10 con más viajes completados.

`GET /admin/overview` (staff), para la portada del admin, sin filtros:

```json
{
  "online_drivers": 7, "rides_in_progress": 3, "rides_today": 25, "completed_today": 21, "gmv_today": "50.40",
  "pending_driver_applications": 2, "pending_top_ups": 1, "unmatched_top_ups": 0,
  "open_reports": 4, "urgent_reports": 1, "overdue_drivers": 2, "stale_rates": ["bcv"]
}
```

## Notificaciones nuevas

| Evento | kind | Para |
| --- | --- | --- |
| Reporte resuelto o descartado | `report` | quien reportó (`data: {report_id}`) |
| Cuenta suspendida | `account` | la persona (`data: {until}`) |
| Suspensión levantada | `account` | la persona |
