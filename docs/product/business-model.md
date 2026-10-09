# Modelo de negocio

## Decidido
- **Ingreso único:** suscripción mensual de los motorizados.
- **Solo se cobra si el motorizado hizo viajes ese mes.** Un mes sin viajes cuesta 0.
- **Cobro escalonado según lo que ganó en el mes**, con un **máximo de 30 USD al mes**.
- Ejemplo dado por Carlos: **si gana más de 100 USD en el mes, paga 5 USD**, y así subiendo por tramos
  hasta llegar al máximo.
- **Lanzamiento:** los primeros **3 meses gratis**.
- **Los viajes los paga el pasajero directamente al motorizado.** Entre ellos solo acuerdan el **método de pago**; **el monto lo fija Kuulis** y es el que muestra la app. Kuulis no toca ese dinero.
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

## Cómo se calcula la ganancia del mes (decidido)
La ganancia del mes es la **suma de los precios que mostró la app en los viajes completados**. Como el monto
lo fija Kuulis, coincide con lo que cobró el motorizado.

## Cobro de la suscripción (decidido)
- Se paga en **USDT**.
- Cada motorizado tiene una **billetera dentro de la app** que recarga con USDT; la cuota se descuenta de ese saldo.
- **Recarga mínima: 5 USDT.**
- Si no paga, tiene **1 semana de gracia**; después **no recibe más viajes** hasta ponerse al día.
- Canal: **Binance Pay** o la red más fácil de implementar, según la recomendación de abajo.

### Recomendación de canal de pago (propuesta, a confirmar)
| Opción | Verificación automática | Comisión para el motorizado | Uso en Venezuela | Esfuerzo / requisitos |
| --- | --- | --- | --- | --- |
| **Binance Pay a una cuenta de Kuulis** (transferencia entre usuarios de Binance) | Posible leyendo el historial de pagos con la API de la cuenta (a confirmar técnicamente) | 0 | Muy alto: es la forma más común de mover USDT | Bajo. No exige empresa, pero el dinero queda en una cuenta personal de Binance |
| **Binance Pay Merchant** (API oficial de cobros) | Sí, con webhooks | 0 | Muy alto | Exige verificar una **empresa** (KYB), y hoy no la hay |
| **USDT en red TRON (TRC-20) a una dirección por motorizado** | Sí, vigilando la blockchain (TronGrid u otro) | ~1 USDT por retiro desde exchanges | Alto | Medio. Sin terceros ni empresa; hay que custodiar las llaves con mucho cuidado |
| Procesador cripto (NOWPayments, CoinPayments…) | Sí, con webhooks | Pequeña comisión | Medio | Bajo–medio. Algunos piden verificación del comercio |

**Recomendación:** empezar con **Binance Pay a una cuenta de Kuulis** como canal principal, porque es gratis
e instantáneo para el motorizado y es lo que ya usa. El motorizado registra su Binance Pay ID en la app y cada
pago se concilia automáticamente por ID y monto. Si la API no permite conciliar de forma confiable, el
respaldo es la confirmación manual en el admin. Como segunda vía, **TRC-20** para quien no use Binance. Cuando
exista empresa, pasar a Binance Pay Merchant. Antes de construir hay que validar técnicamente la conciliación
con la API de Binance.

## Números de referencia (supuesto, solo para dimensionar)
Si 1.000 motorizados activos pagan en promedio 12 USD/mes, son 12.000 USD/mes. Hacen falta datos reales
de ganancias de motorizados para estimar mejor.

## Lanzamiento (decidido + supuesto)
- Decidido: 3 meses sin cobro, **contados para cada motorizado desde su primer viaje completado**.
- Decidido: ciudad inicial **Caracas**, o otra ciudad o país de Latinoamérica con leyes más flexibles.
  Es un **experimento de mercado sin empresa registrada**.
- Supuesto: durante esos meses la app calcula y muestra la cuota que "habría pagado", para que el
  motorizado se acostumbre y para validar los tramos con datos reales.
