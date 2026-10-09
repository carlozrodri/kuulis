# Preguntas abiertas, supuestos y riesgos

## Resuelto (2026-10-09)
- Tramos de la cuota: confirmados (tabla en `business-model.md`), configurables desde el admin.
- Método de pago de la suscripción: USDT.
- Vehículos: solo motos al inicio, carros después.

## Preguntas para Carlos
### Precio y pago del viaje
1. Dijiste que el pasajero paga "como ellos lo acuerden". ¿Lo que se acuerda es solo **el método de
   pago** (efectivo, pago móvil, USDT…) o también **el monto**? Si el monto se puede negociar, el precio
   en USD de la app sería una referencia y no el precio final.
2. ¿El precio lo calcula la app con una tarifa (base + km + minuto) configurable desde el admin?
3. ¿Se muestra también el equivalente en bolívares? ¿Con qué tasa (BCV u otra)?

### Cuota mensual
4. La "ganancia del mes" que define el tramo, ¿es la suma de los precios que mostró la app en los viajes
   completados? (Si el monto se negocia, esto cambia.)
5. ¿El mes es calendario (del 1 al último día) y se cobra a mes vencido?
6. Los 3 meses gratis, ¿cuentan desde el lanzamiento general o desde que cada motorizado se registra?

### USDT
7. ¿Qué red: TRON (TRC-20), BNB Chain (BEP-20) u otra? ¿Aceptamos más de una?
8. ¿Billetera propia de Kuulis o un proveedor como Binance Pay?
9. ¿Verificación manual (el admin confirma el pago) o automática? Para producción recomiendo automática.
10. ¿Cuántos días de gracia hay, y qué pasa si no paga: se bloquea recibir viajes hasta pagar?

### Lanzamiento y operación
11. ¿En qué ciudad se lanza primero?
12. ¿Qué requisitos y documentos debe tener un motorizado para ser aprobado?
13. ¿Hace falta chat dentro de la app, llamadas enmascaradas y calificaciones?

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
| Tiendas de apps | Faltan cuentas de Apple y Google Play | Ya está en `docs/blockers.md` |

## Supuestos técnicos (no decididos)
- Mapas y rutas: Mapbox u OSM + OSRM, por costo; Google Maps como alternativa.
- Ubicación en vivo del motorizado por WebSocket cada pocos segundos, guardada en Redis.
- Emparejamiento: ofrecer el viaje a los motorizados más cercanos uno por uno o en grupo, con tiempo límite.
- PostGIS en Postgres para búsquedas por cercanía.
