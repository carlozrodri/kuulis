# 01 · Estrategia de marca y posicionamiento

## 1. Lo que Kuulis es de verdad (base de todo el mensaje)
Hechos verificados en el código y en `docs/product/` (2026-10-17). Solo se comunica lo que está aquí.

| Hecho | Fuente |
| --- | --- |
| Viajes en **moto** (solo motos al lanzamiento) | `vision.md`, `/public/site` `vehicle_types: ["moto"]` |
| Lanzamiento **solo en Caracas** | `vision.md`, `business-model.md` (decidido) |
| **Cero comisión por viaje**: el motorizado se queda con todo lo que cobra | `vision.md`, `business-model.md` |
| Cuota mensual por tramos según lo ganado, **$0 si ganó $100 o menos**, tope **$30**; nada si no trabajó | `/public/site` `fee_tiers` |
| **3 meses sin cuota** desde el primer viaje del motorizado | `free_months: 3`, `business-model.md` |
| Precio **calculado por la app en USD** antes de pedir; el pasajero no regatea | `business-model.md` («Precio del viaje») |
| Equivalente en **bolívares a tasa BCV y Binance**, congelado al confirmar | `api/apps/rates`, `rides/events.py` (`FrozenRates`) |
| El pasajero **paga directo** al motorizado: efectivo USD, efectivo Bs, pago móvil, Zelle, Binance | `/public/site` `payment_methods` |
| Seguridad: nombre, foto, moto y placa; **PIN de inicio**; **viaje compartido en vivo**; **SOS** al 911 y a contactos; chat en la app; calificación obligatoria | docs 11, 15, 23; `mobile/src/features/ride` (`PinScreen`, `ChatScreen`, `RateScreen`) |
| Pedir para otra persona, con su enlace y PIN | doc 23 |
| Motorizados verificados: cédula, RIF, licencia, certificado médico, carnet de circulación, selfie, fotos de la moto, 21+ años, moto 2013 o más nueva | `/public/site` `driver` |
| App solo **Android**, instalada desde la web (APK); **sin iPhone** por ahora | docs 09 y 08 |
| Sin empresa registrada; experimento de mercado | `vision.md` |

Lo que **no** se puede decir: número de usuarios, viajes, motorizados, tiempos de espera promedio, «el más
seguro», «el más barato», cobertura fuera de Caracas, seguros, alianzas, inversión, premios, testimonios.

## 2. Público
| Público | Quién es | Qué le importa | Qué tiene que creer al salir de la web |
| --- | --- | --- | --- |
| **Pasajero** (principal en volumen) | Caraqueño de 18–45 años con Android, que ya usa mototaxi o apps de viaje; se mueve entre trabajo, estudios y diligencias; tráfico pesado | Llegar rápido, saber cuánto cuesta antes, pagar como pueda (efectivo, Bs, pago móvil), saber quién lo lleva | «Es rápido, el precio es claro y sé quién me lleva» |
| **Motorizado** (principal en estrategia: sin oferta no hay producto) | Motorizado de Caracas, a menudo ya trabaja en delivery o mototaxi; desconfía de apps que le quitan un porcentaje | Cuánto le queda en el bolsillo, que le lleguen viajes, que lo traten con respeto, requisitos claros | «Lo que cobro es mío, y si me va mal no pago» |
| Secundario: familia del pasajero | Recibe un enlace de viaje compartido | Que su familiar llegue bien | «Puedo seguir el viaje en vivo» |
| Secundario: prensa / curiosos / posibles aliados | Llegan por enlaces | Entender qué es y quién está detrás | «Es un producto serio y honesto» |

## 3. Posicionamiento
**Frase de posicionamiento (interna):** Para la gente de Caracas que se mueve en moto, Kuulis es la app de viajes
donde **el precio está claro antes de salir** y **el motorizado se queda con todo lo que cobra**, porque Kuulis no
cobra comisión por viaje.

**La idea central que une a los dos públicos: _cuentas claras_.**
- Para el pasajero: el precio en dólares (y en bolívares) antes de pedir, sin regateo, sin sorpresas.
- Para el motorizado: cero comisión, una cuota pequeña con tope y nada en los meses flojos.
- Para los dos: saben quién es el otro (nombre, foto, placa, PIN).

En Venezuela «cuentas claras» es una expresión cotidiana («cuentas claras, amistades largas»). Es local, honesta y
es exactamente lo que el modelo de negocio hace distinto. **No se usa como eslogan repetido**, sino como principio
que decide qué se muestra y cómo.

## 4. Personalidad
| Es | No es |
| --- | --- |
| Directa: dice el precio y el porcentaje (0 %) sin rodeos | Grandilocuente («revolucionamos la movilidad») |
| Cálida y caraqueña, tutea, habla como la gente | Chabacana ni llena de jerga forzada |
| Segura y competente: se ve hecha con cuidado | Corporativa y fría |
| Ágil: frases cortas, ritmo de moto | Acelerada ni gritona (nada de «¡¡YA!!») |
| Honesta: dice lo que todavía no hay (iPhone, tiendas) | Promesas que el producto no cumple |

Tono de voz: frases cortas, verbos concretos, números reales, cero signos de exclamación salvo en confirmaciones
(«¡Mensaje enviado!»). El español es el original; el inglés se escribe, no se traduce (ver doc 03).

## 5. Jerarquía de mensajes
1. **Qué es** (en 3 segundos): viajes en moto por Caracas, con precio fijo antes de salir.
2. **Por qué es distinto**: cero comisión por viaje; el motorizado se queda con todo.
3. **Cómo funciona para el pasajero**: pides, ves precio en $ y Bs, sabes quién llega, pagas directo como acuerden.
4. **Por qué es confiable**: motorizados verificados con documentos, PIN, viaje compartido, SOS, calificaciones.
5. **Para motorizados**: cuota con tope de $30, nada si no trabajas, 3 meses gratis, requisitos claros.
6. **Acción**: descargar para Android (con la verdad sobre APK e iPhone).

## 6. Diferenciales reales y cómo hacerlos memorables
| Diferencial | Cómo se vuelve memorable (sin inventar) |
| --- | --- |
| 0 % de comisión por viaje | Un número enorme, «0 %», como pieza gráfica protagonista de la sección de motorizados; la tabla de la cuota real al lado |
| Precio en USD + Bs (BCV y Binance) | Mostrar una cotización real de la app (captura) con los dos equivalentes: nadie más en la web lo enseña así |
| Pago directo con el método que acuerden | Fila de métodos reales (Efectivo $, Efectivo Bs, Pago móvil, Zelle, Binance) leídos de la API |
| PIN de inicio | Ilustrar los 4 dígitos como objeto gráfico: «sin tu PIN, el viaje no empieza» |
| Hecho en y para Caracas | El Ávila como horizonte gráfico; nombres de zonas reales en ejemplos (Chacao, Altamira, La Candelaria) sin afirmar cobertura por zonas |

## 7. Principios que guían la experiencia
1. **Cuentas claras en todo**: si un número aparece, es real y sale de la API o del código; si no, no aparece.
2. **El producto es la prueba**: capturas reales de la app en lugar de promesas.
3. **Un mensaje por sección**: si una sección necesita dos ideas, son dos secciones o sobra una.
4. **Respeto por el teléfono del visitante**: cada KB cuenta; nada de video pesado en datos móviles.
5. **Honestidad visible**: decir «solo Android por ahora» con la misma calidad visual que el resto.
6. **Caracas, no «Latinoamérica»**: referencias concretas, no genéricas.

## 8. Qué tomamos de Bolt (y qué no)
Revisado `bolt.eu` el 2026-10-17. Tomamos la **claridad comercial**: un titular corto que dice el beneficio, CTA de
app arriba, separación clara entre «usar» y «ganar dinero», footer completo con enlaces legales e idioma.
No tomamos: su verde, su lógica de «super-app» con muchas tarjetas de servicios, su tipografía ni sus
composiciones. Kuulis tiene un solo servicio: la página debe ser **más enfocada**, no una lista de productos.
