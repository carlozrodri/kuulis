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
- **El saldo no se puede retirar**, pero **se puede transferir a otro motorizado**, con un **límite de 50 USD**
  editable desde el admin. El límite cuenta **solo lo que el motorizado envía**, no lo que recibe (supuesto: el
  periodo es el mes calendario). Cada transferencia queda registrada.
- La cuota se cobra **el día 1 de cada mes por lo ganado el mes anterior**.
- Solo hace falta recargar **cuando le toca pagar**. No se exige saldo para empezar ni durante los 3 meses gratis.
- La **semana de gracia empieza el día del cobro** si el saldo no alcanza.
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

## Precio del viaje (decidido)
- Lo calcula Kuulis **como las otras empresas** (tarifa base, distancia, tiempo, mínimo y recargos por horario
  o demanda), y **todo es configurable desde el admin** para competir.
- Desde el admin se pueden crear **promociones**. El descuento al pasajero lo asume **Kuulis**: el
  motorizado cobra menos en efectivo y Kuulis le **acredita la diferencia en su billetera**.
- Para el tramo de la cuota cuenta el **precio con descuento** (lo que paga el pasajero). El saldo que Kuulis
  acredita por la promoción no suma a la ganancia del mes.
- Los **recargos por demanda alta cuentan** para la ganancia del mes y, por tanto, para el tramo.

### Moneda y tasas de cambio (decidido)
- Todos los precios y la billetera están en **USD/USDT**.
- La app muestra además el **equivalente en bolívares** con dos tasas: **BCV** (oficial) y **Binance** (P2P
  USDT/VES), para que pasajero y motorizado sepan cuánto pagar si el pago es en Bs.
- Supuesto de implementación a costo cero: una tarea programada del worker consulta la tasa BCV (sitio del BCV)
  y la tasa promedio de Binance P2P, las guarda en Redis y en un historial en Postgres. Frecuencia sugerida:
  BCV una vez al día, Binance cada 15–30 minutos. Desde el admin se puede corregir una tasa a mano si una fuente
  falla, y la app muestra la hora de la última actualización.
- Supuesto: el precio del viaje se **congela en USD y en Bs al confirmar**, para que no cambie durante el viaje.

### Riesgo de las promociones
Como Kuulis acredita saldo por cada viaje con promoción, ese saldo es un **costo real de marketing**. Requisitos:
presupuesto y fecha de fin por promoción, tope de usos por pasajero y alertas de abuso (viajes falsos entre un
pasajero y un motorizado que se conocen).

## Otros medios de pago a futuro (supuesto)
Carlos propuso **Apple Pay / Google Pay** además de USDT. Hallazgos a validar:
- Apple Pay y Google Pay no cobran por sí solos: necesitan un procesador (Stripe, Adyen…), que exige una
  empresa registrada en un país soportado. Venezuela no está entre los países soportados.
- Por ahora la recomendación es **solo USDT** y evaluar estos medios cuando haya empresa o si se lanza en otro país.
- Hay que confirmar que las reglas de Apple y Google no exigen cobrar la suscripción con sus compras
  integradas (que se quedan con un 15–30 %). Las apps de transporte suelen quedar fuera porque es un servicio
  físico, pero hay que validarlo antes de publicar.

## Números de referencia (supuesto, solo para dimensionar)
Si 1.000 motorizados activos pagan en promedio 12 USD/mes, son 12.000 USD/mes. Hacen falta datos reales
de ganancias de motorizados para estimar mejor.

## Lanzamiento (decidido + supuesto)
- Decidido: 3 meses sin cobro, **contados para cada motorizado desde su primer viaje completado**.
- Decidido: ciudad inicial **Caracas**, o otra ciudad o país de Latinoamérica con leyes más flexibles.
  Es un **experimento de mercado sin empresa registrada**.
- Supuesto: durante esos meses la app calcula y muestra la cuota que "habría pagado", para que el
  motorizado se acostumbre y para validar los tramos con datos reales.
