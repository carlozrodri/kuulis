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
2. ¿Los recibos llevan algún dato fiscal? Sin empresa, recomendado: recibo simple "no fiscal".
