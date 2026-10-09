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

## Preguntas para Carlos
1. **Promociones al pasajero:** el pasajero le paga al motorizado, así que si hay un descuento, ¿quién lo asume?
   - A) El motorizado cobra menos (es difícil que lo acepte).
   - B) Kuulis le compensa al motorizado con saldo en su billetera.
   - C) Las promociones son solo para motorizados (por ejemplo, un mes sin cuota).
2. **Transferencias entre motorizados:** ¿con mínimo y máximo? ¿Gratis? Se pueden usar para revender saldo,
   así que propongo un límite mensual y que queden registradas en el admin.
3. **Recargo por demanda alta:** ¿también cuenta para la ganancia del mes y, por tanto, para el tramo de la cuota?
   Propuesta: sí, porque es lo que cobró el motorizado.
4. ¿Qué requisitos y documentos debe tener un motorizado para ser aprobado?
5. ¿Hace falta chat dentro de la app, llamadas enmascaradas y calificaciones?
6. ¿Se muestra el equivalente en bolívares? ¿Con qué tasa?
7. ¿Caracas u otro país? Se puede decidir más adelante; el diseño no depende de eso.

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
| Transferencias de saldo entre motorizados | Mercado de reventa de saldo, fraude con cuentas robadas | Límites por mes, registro de cada transferencia y alertas en el admin |
| Reglas de las tiendas sobre cobros dentro de la app | Si Apple o Google consideran la suscripción un bien digital, exigirían su sistema de pago (15–30 %) | Validar con las guías de revisión antes de publicar; cobrar fuera de la app (USDT) |
| Cuenta personal de Binance para cobrar | Riesgo de bloqueo o límites de la cuenta; mezcla de fondos personales | Cuenta dedicada solo a Kuulis; exportar movimientos; plan para migrar a Merchant |

## Supuestos técnicos (no decididos)
- Mapas y rutas: Mapbox u OSM + OSRM, por costo; Google Maps como alternativa.
- Ubicación en vivo del motorizado por WebSocket cada pocos segundos, guardada en Redis.
- Emparejamiento: ofrecer el viaje a los motorizados más cercanos uno por uno o en grupo, con tiempo límite.
- PostGIS en Postgres para búsquedas por cercanía.
