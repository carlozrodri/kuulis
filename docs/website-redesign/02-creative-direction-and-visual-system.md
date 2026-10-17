# 02 · Dirección creativa y sistema visual

## 1. Concepto: «Y punto.»
El logotipo de Kuulis ya tiene su elemento más distintivo: **el punto amarillo** de «kuulis.». En la app, el
amarillo marca **el destino** en el mapa. Y en español «y punto» significa «así de claro, sin más vueltas», que es
exactamente la promesa de la marca (precio fijo, cero comisión, cuentas claras, ver 01).

La dirección creativa convierte ese punto en el sistema visual:

| El punto es… | Dónde aparece |
| --- | --- |
| **El final de cada titular** | Los titulares grandes terminan en un punto amarillo (el carácter «.» del titular pintado con `--accent`), igual que el logotipo. «Precio fijo. Y punto.» |
| **El destino** | En las ilustraciones de ruta, el viaje siempre termina en el punto amarillo |
| **La marca de «llegaste»** | Indicador de sección activa en la navegación, viñetas, estados seleccionados |
| **El favicon y el avatar de marca** | Punto amarillo sobre verde |

Y su compañero es **la ruta**: una sola línea verde de trazo redondeado que sale del hero, cruza la página de
forma discreta (como un recorrido) y termina en el punto del bloque final de descarga. Es el hilo narrativo
«de donde estás a donde vas».

Prueba de reconocimiento sin logotipo: verde Ávila en campos planos + titulares negros muy pesados que terminan
en un punto amarillo + una línea de ruta. Ese conjunto es de Kuulis, no de Bolt (verde sobre blanco con fotos
de producto en tarjetas) ni de Uber (blanco y negro).

### Elemento local: el Ávila
La paleta se llama «Verde Ávila». Se propone una **silueta del Ávila** (la línea de la cresta vista desde Caracas)
dibujada como un solo trazo vectorial, usada como horizonte en dos sitios: la base del hero y el footer. Debe
trazarse a partir de una referencia real (foto de dominio público o foto propia), simplificada a ~20 puntos.
Nada de skyline genérico de ciudad.

## 2. Tres cualidades pedidas, traducidas a reglas
| Cualidad | Regla concreta |
| --- | --- |
| Contención premium | Máximo **un** color de campo por sección; nada de sombras grandes; tarjetas solo donde hay datos (tabla de cuota, cotización); 8 tamaños de texto, no más |
| Impacto creativo | Titulares enormes a ancho completo con el punto; el «0 %» como pieza gráfica; capturas reales recortadas por el borde de la sección en lugar de flotar en tarjetas |
| Ejecución digital moderna | Una animación con significado (la ruta que llega al punto); transiciones de 200–300 ms; todo en CSS y SVG |

## 3. Composición
- **Campos de color planos y completos** (de borde a borde) en lugar del degradado radial actual. Secuencia de
  fondos de la página de inicio: verde (hero) → claro → claro con la captura → tinta (motorizados) → claro
  (seguridad) → verde (descarga). La alternancia da ritmo sin tarjetas.
- **Rejilla de 12 columnas** en escritorio (contenedor de 1200 px, frente a 1080 hoy), 4 columnas en móvil.
  Composiciones **asimétricas**: texto en 5–6 columnas, imagen en 6–7 que se sale del contenedor hacia el borde.
- **Tipografía como imagen**: en las secciones clave el titular es la pieza principal (hasta 6 rem en escritorio).
- **Capturas recortadas**: el teléfono entra desde abajo o el costado y el borde de la sección lo corta. Se ve
  intencional y ahorra altura en móvil.
- **Sin grillas de tarjetas idénticas.** Las listas de beneficios se escriben como filas con un número o un icono
  y una línea divisoria (estilo editorial), no como tres cajas redondeadas.

## 4. Tipografía
**Se mantiene Plus Jakarta Sans Variable** (Supuesto, pregunta 3 en el README): es la fuente de la app, ya está
autoalojada y cargada, y tiene un 800 con carácter. Lo distintivo sale de la escala y el uso, no de añadir familias.

| Rol | Tamaño (fluido) | Peso | Interletrado | Uso |
| --- | --- | --- | --- | --- |
| Display | `clamp(2.75rem, 1.6rem + 5.2vw, 6rem)` | 800 | −0,045 em | Hero, una vez por página |
| H1 de página | `clamp(2.25rem, 1.5rem + 3.4vw, 4.25rem)` | 800 | −0,04 em | Títulos de páginas internas |
| H2 | `clamp(1.75rem, 1.3rem + 2vw, 3rem)` | 800 | −0,03 em | Secciones |
| H3 | `1.25rem` | 700 | −0,01 em | Subtítulos |
| Lead | `clamp(1.125rem, 1rem + 0.5vw, 1.375rem)` | 500 | 0 | Entradilla |
| Cuerpo | `1.0625rem` (17 px, igual que hoy) | 400–500 | 0 | Texto |
| Nota | `0.875rem` | 500 | 0 | Pie, metadatos |
| Etiqueta | `0.8125rem` | 700 | 0,06 em, mayúsculas | Muy poco: solo en tablas |
| Número héroe | `clamp(5rem, 3rem + 10vw, 11rem)` | 800 | −0,06 em | «0 %», «$30» |

- Precios y tablas con `font-variant-numeric: tabular-nums`.
- Longitud de línea: 60–68 caracteres en cuerpo, 18–22 en titulares display.
- `text-wrap: balance` en titulares y `pretty` en párrafos (mejora progresiva, sin costo).
- Se elimina el «eyebrow» verde en mayúsculas encima de cada título (es la firma de las plantillas). Donde haga
  falta contexto, se usa una **parada de ruta**: un punto pequeño + texto normal («● Para motorizados»).

## 5. Color: se conserva la paleta, cambia el reparto
La paleta «Verde Ávila» (00 §3) **no cambia**. Cambia cómo se aplica:

| Color | Reparto aproximado | Dónde | Dónde nunca |
| --- | --- | --- | --- |
| Fondo `#F3F7F4` / superficie `#FFFFFF` | 55 % | Base de lectura | — |
| Verde `#0E7C5A` (y `#0A5C43` para campos grandes en zonas de mucho texto) | 25 % | Hero, bloque de descarga, botones principales sobre claro, la ruta | Texto pequeño sobre `#EAF5EF` por debajo de 16 px |
| Tinta `#14201B` | 15 % | Texto, sección de motorizados en campo oscuro, cabecera al hacer scroll sobre el hero | — |
| Amarillo `#FFC83D` | ≤ 5 % | El punto, el destino, el CTA principal **sobre verde o tinta**, el número héroe sobre tinta | Texto, iconos o bordes sobre fondo claro (1,43:1) |
| Tinte `#EAF5EF` | resto | Fondos de tablas, chips de métodos de pago | — |

### Ajustes mínimos justificados
1. **Quitar el degradado radial del hero** (y el `#18A374` fijo): el texto blanco cae a 3,22:1 en la esquina
   clara. Campo plano `#0E7C5A` → blanco 5,19:1. Es además más sobrio.
2. **Anillo de foco de dos tonos** (`outline` tinta de 2 px + `box-shadow` amarillo de 2 px): hoy el foco amarillo
   es invisible sobre fondo claro. Cumple WCAG 2.2 sobre todos los fondos sin cambiar la paleta.
3. **Botón principal según el fondo**: amarillo con texto `#3A2A00` sobre verde/tinta; verde con texto blanco
   sobre claro. Nunca amarillo sobre claro (el botón amarillo sobre `#F3F7F4` no tiene borde perceptible).
4. Nombrar como tokens los colores que hoy están sueltos (`#0A5C43` ya existe como `--hero-shade`).

Modo oscuro: se mantiene (es funcionalidad existente). El campo verde pasa a `#0C4A37` (ya definido), la tinta a
`#0B1310`, y el amarillo `#FFD25E`. Los campos claros se invierten; las capturas usan la versión oscura de la app
cuando exista (ver 05).

## 6. Imágenes
Orden de prioridad (ver 05 para el inventario):
1. **Capturas reales de la app** en un marco de teléfono neutro dibujado en CSS/SVG (sin marca de fabricante).
   Fondos de las capturas recortados y sin barra de estado con datos personales.
2. **Gráficos de marca** propios en SVG: la ruta, el punto, el Ávila, el PIN, el «0 %», chips de métodos de pago.
3. **Fotografía documental de Caracas** (opcional, fase posterior): luz natural de tarde, motorizados reales con
   casco y consentimiento firmado, calles reconocibles, color natural con un leve sesgo verde en sombras. Nada de
   gente sonriendo a cámara con el teléfono en la mano.
4. Imágenes generadas con IA solo para planos **sin personas identificables** (ver 05) y nunca como si fueran el
   producto o un motorizado real.

## 7. Iconografía
- Trazo de 2 px, extremos redondeados, cuadrícula de 24 px: el mismo estilo que la app (Lucide, `docs/product/mobile-design.md`).
- Se copian a mano en un componente local solo los ~12 iconos necesarios (licencia ISC), sin añadir la librería.
- Los iconos acompañan, no decoran: solo en métodos de pago, funciones de seguridad y navegación.

## 8. Movimiento
| Principio | Aplicación |
| --- | --- |
| Solo se anima lo que cuenta algo | La ruta del hero se dibuja una vez (≤ 1,2 s, `stroke-dashoffset`) y termina con el punto que «llega» (escala 0 → 1, 240 ms). Es la historia del producto en un gesto |
| Aparición discreta | Las secciones entran con 16 px de desplazamiento y opacidad, 320 ms, una sola vez, con `IntersectionObserver` |
| Respuesta táctil | Botones: 120 ms de escala 0,98 al pulsar; enlaces: subrayado que crece desde la izquierda en 200 ms |
| Nada de contadores | El «0 %» no cuenta desde 100: sería teatro |
| Movimiento reducido | Con `prefers-reduced-motion: reduce` todo aparece en su estado final, sin transiciones |
| Rendimiento | Solo `transform` y `opacity`; nada de animaciones de scroll continuas ni parallax |

## 9. Lo que el diseño evita a propósito
Degradados decorativos, glassmorfismo (el blur de la cabecera se sustituye por fondo sólido), manchas flotantes,
grillas de tarjetas iguales, «eyebrows» sobre cada título, ilustraciones 3D genéricas, mockups de teléfono
inclinados en 3D, contadores animados, carruseles automáticos, testimonios.

## 10. Componentes de marca nuevos
| Componente | Qué es |
| --- | --- |
| `BrandDot` | El punto amarillo como elemento (tamaño por prop, `aria-hidden`) |
| `Headline` | Titular que pinta el punto final con `--accent` si el texto termina en «.» |
| `RouteLine` | SVG de la ruta con animación opcional de dibujo |
| `AvilaRidge` | SVG de la silueta del Ávila (decorativo, `aria-hidden`) |
| `PhoneFrame` | Marco de teléfono neutro con `<picture>` dentro |
| `PinDigits` | Los 4 dígitos del PIN como gráfico (con número de ejemplo marcado como ilustración) |
| `PaymentChips` | Métodos de pago reales desde `/public/site` |
