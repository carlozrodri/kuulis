# Preguntas abiertas, supuestos y riesgos

## Resuelto (2026-10-09)
- Tramos de la cuota: confirmados (tabla en `business-model.md`) y configurables desde el admin.
- Pago de la suscripción: USDT, con billetera en la app y recarga mínima de 5 USDT.
- Vehículos: solo motos al inicio, carros después.
- Monto del viaje: lo fija Kuulis; pasajero y motorizado solo acuerdan el método de pago.
- Ganancia del mes: suma de los precios de la app en viajes completados.
- Canal: Binance Pay o la red más fácil (recomendación en `business-model.md`).
- Impago: 1 semana de gracia y luego no recibe viajes.
- 3 meses gratis: desde el primer viaje completado de cada motorizado.
- Lanzamiento: Caracas u otra ciudad o país de Latinoamérica, como experimento sin empresa registrada.
- La cuota se cobra el día 1 por lo ganado el mes anterior.
- El saldo de la billetera no se retira, pero se puede transferir a otro motorizado.
- Solo se recarga cuando toca pagar; la semana de gracia empieza el día del cobro.
- El precio del viaje se calcula como en otras apps, configurable desde el admin, con promociones.
- En otro país se mantiene USDT por ahora; Apple Pay y Google Pay quedan a evaluar.
- Promociones al pasajero: Kuulis acredita la diferencia en la billetera del motorizado.
- Transferencias entre motorizados: límite de 50 USD editable desde el admin; cuenta solo lo enviado.
- Con promoción, para el tramo cuenta el precio con descuento.
- Motorizado: 21 años o más, certificado médico y moto 2013 o más nueva (configurables).
- Inicio de sesión: solo email y Google.
- Los recargos por demanda alta cuentan para el tramo de la cuota.
- Documentos del motorizado: cédula, RIF (Venezuela), licencia, carnet de circulación, selfie y fotos de la moto; aprobación manual.
- Chat dentro de la app y calificación obligatoria de ambos lados.
- Llamadas enmascaradas: fuera, por costo. La operación debe ser de muy bajo costo.
- Precios en USDT con equivalente en bolívares a tasa BCV y a tasa Binance.

## Preguntas para Carlos
1. Color de marca: elegir entre las paletas A (Verde Ávila, recomendada), B (Naranja Moto) o C (Azul Eléctrico): https://claude.ai/artifact/38jgHYUuqhFoqDxHhp9Usj
2. Agregar "Iniciar sesión con Apple" en iOS (Apple lo exige si hay Google). Recomendado: sí.
3. ¿Caracas u otro país? Se puede decidir más adelante; el diseño no depende de eso.

## Riesgos
| Riesgo | Por qué importa | Mitigación propuesta (supuesto) |
| --- | --- | --- |
| Pagos fuera de la app | Kuulis no ve el dinero real; los motorizados podrían subdeclarar | Calcular ganancias con el precio mostrado; cuota baja con tope para que no compense hacer trampa |
| Viajes fuera de la app | Pasajero y motorizado se ponen de acuerdo por WhatsApp tras el primer viaje | Valor continuo: seguridad, historial, flujo constante de clientes |
| Seguridad | Moto, efectivo y desconocidos | Verificación de identidad, botón de pánico, compartir viaje en vivo, calificaciones |
| Regulación | Normas locales de transporte y mototaxis | Revisar con abogado venezolano antes del lanzamiento |
| Conectividad | Datos móviles lentos o inestables | App ligera, mapas eficientes, reintentos, WebSocket con reconexión (ya en la plantilla) |
| Costo de mapas | Google Maps cobra por petición | Evaluar Mapbox u OpenStreetMap; cachear geocodificación |
| Arranque en frío | Sin motorizados no hay pasajeros y viceversa | 3 meses gratis, captación de motorizados antes de abrir a pasajeros, una sola ciudad al inicio |
| Cobro de suscripción | Medios de pago limitados en Venezuela | Ofrecer varios métodos; conciliación manual en el admin al principio |
| Tiendas de apps | Faltan cuentas de Apple y Google Play | Ya está en `docs/blockers.md`; ambas permiten cuenta de persona natural |
| Operar sin empresa registrada | Responsabilidad personal de Carlos ante accidentes, reclamos o autoridades; Binance Pay Merchant y algunos procesadores exigen empresa | Términos y condiciones claros (Kuulis conecta, no transporta), billetera no reembolsable, asesoría legal antes de escalar |
| Custodia de saldos de motorizados | Guardar dinero de terceros puede tener implicaciones legales y contables | Saldo como crédito prepago no reembolsable; registro contable de cada movimiento en la app |
| Fuentes de tasas de cambio | El sitio del BCV o la API de Binance P2P pueden cambiar o caerse | Guardar la última tasa válida, alerta en el admin y opción de cargarla a mano |
| Abuso de promociones | Viajes falsos para cobrar saldo de Kuulis | Presupuesto y tope por promoción, detección de pares pasajero-motorizado repetidos |
| Transferencias de saldo entre motorizados | Mercado de reventa de saldo, fraude con cuentas robadas | Límites por mes, registro de cada transferencia y alertas en el admin |
| Reglas de las tiendas sobre cobros dentro de la app | Si Apple o Google consideran la suscripción un bien digital, exigirían su sistema de pago (15–30 %) | Validar con las guías de revisión antes de publicar; cobrar fuera de la app (USDT) |
| Cuenta personal de Binance para cobrar | Riesgo de bloqueo o límites de la cuenta; mezcla de fondos personales | Cuenta dedicada solo a Kuulis; exportar movimientos; plan para migrar a Merchant |

## Supuestos técnicos (no decididos)
- Mapas y rutas: Mapbox u OSM + OSRM, por costo; Google Maps como alternativa.
- Ubicación en vivo del motorizado por WebSocket cada pocos segundos, guardada en Redis.
- Emparejamiento: ofrecer el viaje a los motorizados más cercanos uno por uno o en grupo, con tiempo límite.
- PostGIS en Postgres para búsquedas por cercanía.
