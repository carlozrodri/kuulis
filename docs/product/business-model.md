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

## Tramos propuestos (supuesto, a validar)
Solo el tramo de 100 USD → 5 USD lo definió Carlos. Esta tabla es una propuesta para discutir:

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

Preguntas que deciden la tabla final: ¿se cobra algo por debajo de 100 USD? ¿cada cuánto sube el tramo?
Ver `open-questions.md`.

## Cómo se sabe cuánto ganó el motorizado (supuesto)
Como el pago es directo, Kuulis no ve el dinero. Propuesta: la ganancia del mes es la **suma del precio
mostrado en la app de los viajes completados**. Es simple y verificable, aunque el monto real acordado
puede variar.

## Cobro de la suscripción (abierto)
Cómo pagan los motorizados a Kuulis en Venezuela: pago móvil, transferencia, Zelle, Binance/USDT, efectivo en
un punto físico u otro. Qué pasa si no pagan (¿se bloquea recibir viajes?). Ver `open-questions.md`.

## Números de referencia (supuesto, solo para dimensionar)
Si 1.000 motorizados activos pagan en promedio 12 USD/mes, son 12.000 USD/mes. Hacen falta datos reales
de ganancias de motorizados para estimar mejor.

## Lanzamiento (decidido + supuesto)
- Decidido: 3 meses sin cobro.
- Supuesto: durante esos meses la app calcula y muestra la cuota que "habría pagado", para que el
  motorizado se acostumbre y para validar los tramos con datos reales.
