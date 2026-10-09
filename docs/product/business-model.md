# Modelo de negocio

## Decidido
- **Ingreso único:** suscripción mensual de los motorizados.
- **Solo se cobra si el motorizado hizo viajes ese mes.** Un mes sin viajes cuesta 0.
- **Cobro escalonado según lo que ganó en el mes**, con un **máximo de 30 USD al mes**.
- Ejemplo dado por Carlos: **si gana más de 100 USD en el mes, paga 5 USD**, y así subiendo por tramos
  hasta llegar al máximo.
- **Lanzamiento:** los primeros **3 meses gratis**.
- **Los viajes los paga el pasajero directamente al motorizado**, como acuerden. Kuulis no toca ese dinero.
- Precios en **dólares**.

## Tramos de la cuota (decidido 2026-10-09)
Carlos confirmó esta tabla. **Requisito:** los tramos (límites, montos y tope) deben poder cambiarse
más adelante desde el panel admin sin desplegar código, así que se guardan en base de datos, no en el código.

| Ganancia del mes (USD) | Cuota (USD) |
| --- | --- |
| 0 (sin viajes) | 0 |
| 0,01 – 100 | 0 |
| 100,01 – 200 | 5 |
| 200,01 – 300 | 10 |
| 300,01 – 400 | 15 |
| 400,01 – 500 | 20 |
| 500,01 – 600 | 25 |
| más de 600 | 30 (tope) |

Supuesto técnico: un cambio de tramos aplica desde el mes siguiente y queda registrado quién lo hizo y cuándo,
para que la cuota de un mes ya cerrado no cambie.

## Cómo se sabe cuánto ganó el motorizado (supuesto)
Como el pago es directo, Kuulis no ve el dinero. Propuesta: la ganancia del mes es la **suma del precio
mostrado en la app de los viajes completados**. Es simple y verificable, aunque el monto real acordado
puede variar.

## Cobro de la suscripción
**Decidido:** los motorizados pagan la suscripción en **USDT**.

Pendiente de definir (ver `open-questions.md`): red (TRON/TRC-20, BNB Chain/BEP-20, Polygon u otra),
billetera propia o proveedor (por ejemplo Binance Pay), cómo se verifica cada pago (manual en el admin o
automático por blockchain/proveedor), quién paga la comisión de red, día de corte, días de gracia y qué
pasa si no paga.

## Números de referencia (supuesto, solo para dimensionar)
Si 1.000 motorizados activos pagan en promedio 12 USD/mes, son 12.000 USD/mes. Hacen falta datos reales
de ganancias de motorizados para estimar mejor.

## Lanzamiento (decidido + supuesto)
- Decidido: 3 meses sin cobro.
- Supuesto: durante esos meses la app calcula y muestra la cuota que "habría pagado", para que el
  motorizado se acostumbre y para validar los tramos con datos reales.
