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

## Preguntas para Carlos
### Cuota y billetera
1. **¿Cuándo se cobra la cuota?** Opción A: el día 1 de cada mes, por lo ganado el mes anterior. Opción B:
   durante el mes, a medida que pasa cada tramo (100 USD → se descuentan 5, 200 USD → otros 5…).
   Recomiendo la A porque es más simple y predecible.
2. **¿Cuándo empieza la semana de gracia?** ¿Desde el día de cobro si el saldo no alcanza?
3. **¿Hace falta saldo para recibir viajes?** Por ejemplo, ¿debe recargar los 5 USDT antes de su primer viaje,
   o solo cuando le toque pagar (después de los 3 meses gratis)?
4. **¿El saldo de la billetera se puede retirar** si el motorizado deja la app? ¿O es crédito prepago no
   reembolsable? Recomiendo **no reembolsable** (solo sirve para pagar cuotas): así Kuulis no custodia dinero
   de terceros, lo que importa mucho sin empresa registrada.
5. **Mes parcial:** si el primer viaje es el día 20, ¿los 3 meses gratis terminan el día 20 del tercer mes,
   y la primera cuota cuenta solo los días restantes de ese mes?

### Precio del viaje
6. **¿Cómo se calcula el precio?** Propuesta: tarifa base + por km + por minuto, con un precio mínimo, todo
   configurable desde el admin. ¿Quieres recargos por horario nocturno o demanda alta?
7. ¿Se muestra también el equivalente en bolívares? ¿Con qué tasa?

### Lanzamiento
8. **¿Caracas o otro país?** Si es otro país, ¿también se cobra en USD y se usa USDT? Afecta moneda, idioma,
   mapas y métodos de pago.
9. ¿Qué requisitos y documentos debe tener un motorizado para ser aprobado?
10. ¿Hace falta chat dentro de la app, llamadas enmascaradas y calificaciones?

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
| Cuenta personal de Binance para cobrar | Riesgo de bloqueo o límites de la cuenta; mezcla de fondos personales | Cuenta dedicada solo a Kuulis; exportar movimientos; plan para migrar a Merchant |

## Supuestos técnicos (no decididos)
- Mapas y rutas: Mapbox u OSM + OSRM, por costo; Google Maps como alternativa.
- Ubicación en vivo del motorizado por WebSocket cada pocos segundos, guardada en Redis.
- Emparejamiento: ofrecer el viaje a los motorizados más cercanos uno por uno o en grupo, con tiempo límite.
- PostGIS en Postgres para búsquedas por cercanía.
