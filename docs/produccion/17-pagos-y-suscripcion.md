# 17 · Pagos y suscripción: endurecimiento

**Prioridad:** P1 · **Área:** API · Mobile · Admin · **Depende de:** 03, 06

## Objetivo
Que el único ingreso de Kuulis (la cuota del motorizado) se cobre sin errores ni dependencias frágiles:
respaldo si Binance falla, recibos, disputas, cierres contables mensuales y protección contra errores humanos.

## Estado actual
- Billetera con libro contable, recarga con Binance Pay conciliada cada minuto por API de solo lectura
  (falta **una recarga real de prueba**, bloqueo 10 resuelto con esa nota), confirmación/rechazo/asignación
  manual, transferencias con límite, cuota del día 1 por tramos, 3 meses gratis, 1 semana de gracia, bloqueo,
  finanzas con CSV.
- TRC-20 como respaldo: **pospuesto** (roadmap 1D).
- El dinero se recibe en una **cuenta personal de Binance** (riesgo listado).
- No hay recibos descargables ni cierre de mes.

## Alcance
### Incluye
1. **Prueba real de punta a punta** en QA y luego en producción con montos pequeños: recarga, conciliación,
   cobro de cuota, transferencia. Checklist documentada.
2. **Recibos**: cada recarga acreditada y cada cuota cobrada genera un recibo (número correlativo, fecha,
   motorizado, concepto, monto, saldo) en PDF o página imprimible y email (14).
3. **Estado de cuenta mensual** del motorizado: ganancia del mes según la app, tramo aplicado, cuota, créditos
   de promoción, transferencias. Visible en la app y por email el día 1.
4. **Cierre contable mensual**: al terminar el mes, un registro inmutable con totales (recargas, cuotas,
   promociones, ajustes, saldos) y un hash; conciliación con el extracto de Binance cargado en CSV; diferencias
   listadas para revisar.
5. **Invariantes del libro**: tarea diaria que verifica que la suma de movimientos de cada billetera = saldo, que
   no hay saldos negativos y que no hay recargas duplicadas por id de transacción; alerta (03) si falla.
6. **Disputas de recarga**: el motorizado puede reclamar una recarga no acreditada con comprobante (captura y
   id de transacción) desde la app; entra a soporte (13) con prioridad.
7. **Respaldo si Binance falla**: alerta si la conciliación falla más de 10 min; modo manual automático (la app
   ofrece "Avisar que pagué" con comprobante). Evaluar TRC-20 solo si los datos muestran que hace falta.
8. **Plan de migración a Binance Pay Merchant** cuando exista empresa (documento, no código).
9. **Exonerar cuotas**: acción del admin para exonerar o reducir una cuota con motivo (casos sociales,
   errores), con doble aprobación (06).
10. **Simulador de tramos**: en el admin, ver el ingreso estimado del mes con los tramos actuales vs propuestos,
    usando las ganancias reales del mes anterior.

### Fuera
- Cobro del viaje dentro de la app (decidido: pago directo entre las partes).
- Retiros de saldo (decidido: no se retira).

## App móvil
### Motorizado
- Billetera → cada movimiento con "Ver recibo".
- **Estado de cuenta** por mes.
- Recarga: "No me llegó mi recarga" con formulario de comprobante.

## Admin
- **Cierres**: lista de meses cerrados, totales, carga del CSV de Binance, diferencias y marca de conciliado.
- **Invariantes**: resultado diario en Estado del sistema (03).
- **Simulador de tramos** en Suscripciones.
- Disputas de recarga dentro de Soporte (13) con acceso directo a asignar la recarga.

## API y datos
- `receipts` (`number` secuencia, `user_id`, `entry_id`, `kind`, `amount`, `issued_at`, `file_key`).
- `monthly_closings` (`month`, `totals` JSONB, `hash`, `closed_by`, `closed_at`, `reconciled_at`,
  `binance_statement_key`, `differences` JSONB).
- `GET /wallet/me/statements?month`, `GET /wallet/me/receipts/{id}`, `POST /wallet/me/top-ups/{id}/dispute`.
- Admin: `POST /admin/finance/closings`, `POST /admin/finance/closings/{month}/statement` (CSV),
  `GET /admin/subscriptions/simulate` con tramos propuestos.
- Tarea `wallet.invariants` diaria.

## Criterios de aceptación
- Una recarga real en Binance se acredita sola en menos de 2 minutos y genera recibo.
- Forzar un descuadre en QA dispara la alerta de invariantes.
- El cierre de un mes no cambia aunque luego se modifique un tramo o un ajuste (los ajustes nuevos van al mes
  siguiente).
- El simulador reproduce exactamente las cuotas cobradas del mes anterior con los tramos vigentes.

## Dependencias
03 (alertas), 06 (doble aprobación y auditoría). 13 para disputas.

## Preguntas para Carlos
1. ¿Hacemos la recarga real de prueba en QA esta semana? Necesita tu cuenta de Binance.
   **Abierto:** la lista de pasos está abajo ("Prueba real de punta a punta"); falta que Carlos la haga con su
   cuenta.
2. ¿Los recibos llevan algún dato fiscal? Sin empresa, recomendado: recibo simple "no fiscal".
   **Decidido** (recomendado): recibo "no fiscal" con número correlativo, sin RIF ni datos fiscales.

## Cómo quedó (2026-10-14)
### API
- **Recibos** (`wallet_receipts`, `apps/wallet/receipts.py`): cada recarga acreditada y cada cuota cobrada
  genera un recibo no fiscal con número correlativo (secuencia de Postgres), concepto, monto, saldo después y
  referencia, en la misma transacción que el movimiento. Los movimientos traen `receipt_id`;
  `GET /wallet/me/receipts/{id}`. Los correos "Recarga acreditada" y "Recibo de cuota" llevan el número y el
  saldo, así que sirven de recibo por email.
- **Estado de cuenta** (`apps/finance/statements.py`): `GET /wallet/me/statements?month=` con lo ganado según
  la app, lo que cuenta para la cuota, viajes, tramo, cuota (estimada si el mes sigue abierto), recargas,
  créditos de promoción, transferencias, cuotas, ajustes y saldo al inicio y al cierre. El correo del día 1
  ("Estado de cuenta mensual") ahora sale **después** de cobrar las cuotas (antes podía salir antes del cobro y
  no encontrar a nadie).
- **Cierres** (`monthly_closings`, `apps/finance`): `POST /admin/finance/closings` congela los totales del mes
  (movimientos por tipo, recargas automáticas y manuales, cuotas por estado, saldos al inicio y al cierre)
  con un hash SHA-256 encadenado al cierre anterior; si alguien edita un cierre guardado, la lista lo marca.
  Solo meses terminados y en orden. Los ajustes posteriores llevan la fecha del día, así que caen en el mes
  abierto y el cierre no cambia. Luego se carga el CSV del historial de Binance Pay
  (`POST .../{mes}/statement`, columnas en inglés o español) y se listan los pagos que están en Binance y no en
  Kuulis, los que están en Kuulis y no en Binance, y los montos distintos. Marcar como conciliado pide nota si
  hay diferencias. Permiso nuevo `finance.close` (rol Finanzas).
- **Invariantes** (tarea `finance` del worker, una vez al día; `POST /admin/finance/invariants/run` a mano):
  saldo = suma de movimientos y = último `balance_after`, sin saldos negativos, ningún pago de Binance
  acreditado dos veces (id de transacción o referencia), recargas y cuotas pagadas con su movimiento. El
  resultado sale en Estado del sistema y, si falla, la alerta "Descuadre en las billeteras" va a Telegram
  hasta que se corrija.
- **Disputas**: `POST /wallet/me/top-ups/{id}/dispute` (recarga pendiente o rechazada, con id de transacción y
  captura) abre un ticket urgente de Soporte en la categoría nueva "Pagos y recargas", enlazado a la recarga.
- **Respaldo si Binance falla**: si la conciliación no completa una pasada en 10 minutos llega la alerta
  "La conciliación de Binance Pay falla…" y `top-up-info` responde `automatic: false` con
  `manual_reason: "binance_down"`, así que la app pasa sola al "Ya pagué" con referencia. TRC-20 sigue
  pospuesto hasta que los datos digan que hace falta.
- **Exonerar o bajar una cuota** (`POST /admin/subscriptions/charges/{id}/waive {reason, fee}`): pendiente o ya
  pagada (se devuelve la diferencia a la billetera como ajuste). Guarda la cuota original y pide doble
  aprobación (`approval_waivers`, activado por defecto).
- **Simulador de tramos** (`POST /admin/subscriptions/simulate`): con las ganancias guardadas en las cuotas del
  mes, compara lo que cobran los tramos vigentes (y si reproducen exactamente lo cobrado) con tramos propuestos.
- **Plan de Binance Pay Merchant**: [binance-merchant.md](binance-merchant.md).

## Prueba real de punta a punta
En QA primero y luego en producción, con montos pequeños (5 USDT):
1. En la app del motorizado de prueba, guardar su Binance Pay ID en Billetera.
2. Desde esa cuenta de Binance, pagar 5 USDT por Binance Pay al Pay ID de Kuulis (Ajustes del admin).
3. Tocar "Ya pagué" con el id de la orden. La primera vez el admin la confirma en Recargas (eso verifica el Pay
   ID); desde la segunda debe acreditarse sola en menos de 2 minutos.
4. Revisar que llegó el push y el correo con el número de recibo, y que el recibo se abre en Billetera.
5. Con una cuota pendiente, recargar y ver que la cuota se cobra sola y genera su recibo.
6. Transferir 1 USDT a otra cuenta de prueba (la primera espera 24 h por antifraude).
7. Al mes siguiente: cerrar el mes en Finanzas → Cierres, subir el CSV de Binance Pay y conciliar.

### Admin
- **Finanzas → Cierres**: invariantes del libro con "Verificar ahora", lista de meses cerrados (aviso rojo si un
  hash no cuadra), cerrar mes con vista previa de los totales, subir y descargar el CSV de Binance Pay, las tres
  listas de diferencias y marcar como conciliado.
- **Suscripciones**: pestaña "Simulador" (tramos propuestos contra los vigentes) y "Condonar o bajar" en cuotas
  pendientes y pagadas, con doble aprobación. Se ve la cuota original cuando se bajó.
- **Estado del sistema**: tarjeta "Libro de billeteras" y el proceso `finance`.
- **Soporte**: tarjeta "Recarga reclamada" en el ticket, con "Acreditar" y enlace a Recargas.
- **Ajustes**: interruptor de doble aprobación para exoneraciones. Permiso nuevo `finance.close`.
### App (OTA)
- Billetera: "Ver recibo" en recargas y cuotas (recibo no fiscal, compartir como texto) y "Estado de cuenta"
  por mes.
- "No me llegó mi recarga" desde Recargar y desde cada recarga pendiente o rechazada, con id de transacción y
  captura; abre la conversación en Soporte. Aviso cuando Binance falla y la recarga se confirma a mano.
