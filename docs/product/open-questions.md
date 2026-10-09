# Preguntas abiertas, supuestos y riesgos

## Preguntas para Carlos
### Modelo de negocio
1. ¿Cuáles son los tramos exactos de la cuota? ¿Se cobra algo por debajo de 100 USD?
2. ¿La ganancia del mes se calcula con el precio que muestra la app o con lo que declara el motorizado?
3. ¿Cómo pagan los motorizados la suscripción (pago móvil, Zelle, USDT, efectivo)?
4. ¿Qué pasa si un motorizado no paga? ¿Se bloquea, hay días de gracia?
5. Los 3 meses gratis, ¿cuentan desde el lanzamiento general o desde que cada motorizado se registra?

### Producto
6. ¿Solo motos al inicio, o también carros, delivery o encomiendas?
7. ¿El precio lo calcula la app (tarifa base + km + minuto) o el motorizado puede negociarlo?
8. ¿El pasajero puede elegir método de pago en la app (para que el motorizado sepa si es efectivo)?
9. ¿En qué ciudad se lanza primero?
10. ¿Qué requisitos debe cumplir un motorizado (documentos, antigüedad de la moto)?
11. ¿Se necesitan calificaciones, chat in-app o llamadas enmascaradas?

### Precio en dólares
12. ¿Se muestra también el equivalente en bolívares con la tasa del BCV o la paralela?

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
