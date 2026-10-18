# Hechos permitidos

Lo único que una pieza de Kuulis puede afirmar. Si una frase no sale de esta lista, no se publica.
El revisor marca cada afirmación de un guion con el número de hecho que la respalda (por ejemplo `[H4]`).

**Antes de producir**, el guionista confirma los valores vivos en `GET /api/v1/public/site` (producción, o QA
mientras no haya producción): tramos de la cuota, meses gratis, requisitos, métodos de pago. Si un valor de la
API no coincide con esta tabla, **gana la API** y se avisa para corregir este archivo.

Revisado: 2026-10-18 (contra `docs/product/`, `api/apps/config/schemas.py` y `/public/site` de QA).

## Lo que sí
| # | Hecho | Cómo se puede decir | Fuente |
| --- | --- | --- | --- |
| H1 | Viajes en **moto**; solo motos por ahora | «Viajes en moto» | `vision.md`; `/public/site` `vehicle_types` |
| H2 | Lanzamiento **solo en Caracas** | «En Caracas» (nunca otras ciudades, aunque QA tenga datos de prueba de otras) | `vision.md` |
| H3 | **0 % de comisión por viaje**: lo que cobra el motorizado es suyo | «Lo que cobras es tuyo», «cero comisión por viaje» | `business-model.md` |
| H4 | Cuota mensual por tramos según lo ganado: **$0 hasta $100**, $5 de $100 a $200, $10, $15, $20, $25 y **tope de $30** a partir de $600 | «Si ganaste $100 o menos, pagas $0», «nunca más de $30 al mes» | `/public/site` `fee_tiers` |
| H5 | **Mes sin viajes = $0** | «Si no trabajaste, no pagas» | `business-model.md` |
| H6 | **3 meses sin cuota** desde el primer viaje del motorizado | «Tus primeros 3 meses no pagas cuota» | `/public/site` `free_months` |
| H7 | El **precio lo calcula la app** antes de pedir, en **USD** y con su equivalente en **Bs** | «Ves el precio antes de montarte», «en dólares y en bolívares» | `business-model.md` |
| H8 | El pasajero **paga directo** al motorizado; métodos: efectivo en dólares, efectivo en bolívares, pago móvil, Zelle, Binance | «Pagas como acuerden», listar los métodos | `/public/site` `payment_methods` |
| H9 | El motorizado ve los datos del viaje y el pasajero ve **nombre, foto, moto y placa** del motorizado | «Sabes quién te lleva» | docs `produccion/11`, app |
| H10 | **PIN de inicio**: el viaje no empieza sin el PIN del pasajero | «Sin tu PIN, el viaje no arranca» | `produccion/11`; `PinScreen` |
| H11 | **Viaje compartido en vivo** con un enlace | «Comparte tu viaje y te siguen en vivo» | `produccion/11` |
| H12 | Botón **SOS**: llama al número de emergencia y envía el enlace del viaje a tus contactos | «Con un toque llamas a emergencias y avisas a tus contactos» | `produccion/11` (nunca prometer un equipo de Kuulis que responda) |
| H13 | **Chat** en la app y **calificación** después de cada viaje | «Chateas dentro de la app» | app |
| H14 | **Pedir para otra persona**, con su propio enlace y PIN | «Pide una moto para tu mamá desde tu teléfono» | `produccion/23` |
| H15 | Motorizados **verificados**: cédula, RIF, licencia, certificado médico, carnet de circulación, selfie y fotos de la moto; **21 años o más**; moto **2013 o más nueva** | «Motorizados verificados con sus documentos» | `/public/site` `driver` |
| H16 | App **solo para Android**, se instala desde la web de Kuulis (APK); **no hay iPhone** todavía | «Descárgala para Android en la web» | `produccion/09` |
| H17 | La billetera del motorizado se recarga con USDT; la cuota se descuenta de ahí | Solo en piezas para motorizados que lo necesiten | `business-model.md` |
| H18 | Invitaciones: el motorizado gana crédito en su billetera cuando su invitado cumple los viajes del programa | Solo con los valores vivos del programa, si está activo | `produccion/22`, app |

## Precios de viajes
Las tarifas se cambian desde el admin. **Nunca se dice un precio de un trayecto de memoria.** Opciones:
- Mostrar una **cotización real** de la app hecha el mismo día de producción (captura con fecha guardada en S3).
- Usar un número de **ejemplo** dicho como ejemplo: «si una carrera te sale en $3…».

## Lo que no se puede decir nunca
- Cifras de usuarios, viajes, motorizados, descargas o ciudades que no salgan de datos reales del momento.
- Tiempos de espera o de llegada promedio.
- «El más seguro», «el más barato», «el mejor», «el número 1».
- Cobertura fuera de Caracas, iPhone, Google Play o App Store.
- Seguros, alianzas, inversión, premios, prensa.
- Testimonios, reseñas o historias de motorizados o pasajeros que no existan (decidido: no se simulan con IA).
- Que Kuu maneja moto, viajó, o es una persona real.
- Nombres, logotipos o pantallas de otras apps de viajes.
- Que Kuulis tiene un equipo que responde al SOS.
- Que la app es gratis «para siempre» para el motorizado (la cuota existe).

## Cuentas de ejemplo para comparar con «apps con comisión»
Se permiten como **ejemplo explícito**, sin nombrar a nadie:
> «Si una app te quita el 20 % de una carrera de $3, te quedan $2,40. En Kuulis te quedas los $3.»

El porcentaje de ejemplo debe presentarse como hipotético («si una app te quita…»), nunca como el de una marca.
