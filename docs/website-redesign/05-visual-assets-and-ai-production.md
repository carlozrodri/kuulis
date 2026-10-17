# 05 · Assets visuales y producción con IA

## 1. Resumen y recomendación
- **El lanzamiento del rediseño no depende de ninguna imagen generada.** Lo esencial son capturas reales de la
  app y gráficos de marca en SVG que Claude dibuja en el código.
- **No se recomienda comprar una suscripción ahora.** La mejora que aportaría (atmósfera de Caracas) es real pero
  secundaria, y tiene un riesgo de autenticidad para una marca cuyo posicionamiento es «cuentas claras».
- **Si Carlos quiere fotografía** (pregunta 2 del README), el orden recomendado es: (1) una sesión corta con un
  fotógrafo en Caracas con motorizados reales que firmen autorización; (2) si no es viable, IA solo para planos
  **sin personas identificables**. La decisión se toma antes del milestone de assets (M8), no ahora.

## 2. Inventario
Leyenda: **E** = esencial para lanzar, **O** = opcional.

### 2.1 Se reutiliza
| Asset | Dónde está | Uso en el rediseño |
| --- | --- | --- |
| Logotipo «kuulis.» | `KuulisWordmark.vue` | Igual; se añade una variante SVG con la letra convertida a trazos para favicon y OG |
| Paleta y fuente | `main.css`, fontsource | Igual |
| Icono de la app | `mobile/assets/icon.png` | Dentro de `PhoneFrame` (pantalla de inicio de Android en los pasos de instalación) y en la tarjeta de descarga |
| Tabla de cuota | `FeeTable.vue` | Restilizada |

### 2.2 Se crea (sin IA)
| # | Asset | Propósito | Ubicación | Formato | Proporción / tamaño | Dirección visual | E/O |
| --- | --- | --- | --- | --- | --- | --- | --- |
| A1 | Capturas de la app: inicio del pasajero, cotización con $ y Bs, motorizado asignado (nombre, foto, placa), PIN, viaje en curso, cuota del motorizado | Probar el producto | Hero, precio claro, seguridad, motorizados | Original PNG; servido como AVIF + WebP + PNG de respaldo | 9:19,5 (pantalla de teléfono); originales a 1080×2340; servidos a 360 y 720 px de ancho | Datos de prueba creíbles y neutros (nombres de cuentas de QA de diseño), sin avisos de desarrollo, sin datos personales reales, versión clara y oscura | **E** |
| A2 | Capturas del proceso de instalación del APK en Android (4 pasos) | Reducir el miedo a instalar fuera de la tienda | `/descargar` | AVIF/WebP | 9:19,5, 360 px | Capturas reales de un Android en español, recortadas al diálogo relevante | **E** |
| A3 | `PhoneFrame` | Marco neutro para A1/A2 | Todas las capturas | CSS + SVG | Se adapta | Bisel tinta de 10 px, radio 36 px, sin botones ni marca de fabricante | **E** |
| A4 | Ruta y punto | Hilo narrativo | Hero, cómo funciona, motorizados, descarga | SVG en línea | — | Trazo verde de 6 px, extremos redondeados, curvas suaves; termina siempre en el punto amarillo | **E** |
| A5 | Silueta del Ávila | Lugar | Base del hero, footer | SVG en línea (< 2 KB) | Panorámica 8:1 | Un solo trazo o relleno plano `#0A5C43` sobre verde; trazada a partir de una foto real de la cresta vista desde el este de Caracas | **E** |
| A6 | `PinDigits` | Explicar el PIN | Seguridad (inicio y página) | SVG/HTML | 4:1 | Cuatro casillas tinta con dígitos blancos; el cuarto «llegando» con el punto | **E** |
| A7 | Chips de métodos de pago | Pago directo | Precio claro | HTML + iconos de trazo | — | Píldoras `#EAF5EF` con texto tinta; sin logotipos de marcas de terceros (Zelle y Binance no se dibujan con su logo) | **E** |
| A8 | Imagen Open Graph por idioma y por página principal (inicio, motorizados, seguridad, descargar) | Vista previa en WhatsApp | `<meta og:image>` | PNG optimizado (< 120 KB) | 1200×630 | Campo verde, titular de la página en blanco con el punto, logotipo; texto en el idioma de la página | **E** |
| A9 | Favicon SVG con trazos | Que la «k» no caiga a Arial | `public/favicon.svg` | SVG + `icon-192.png` + `apple-touch-icon` 180 | 1:1 | Igual al actual, con la letra convertida a trazo | **E** |
| A10 | Iconos de trazo (~12) | Filas de seguridad, métodos, navegación | Varias | SVG en línea | 24×24 | Estilo Lucide, 2 px | **E** |

**Cómo se consiguen las capturas A1 (pregunta 4 del README):** recomendado que Carlos las saque en su Android con
el build de QA usando las cuentas de diseño (es la app real, con la barra de estado real); Claude prepara los
datos (viaje de ejemplo en QA) y recorta, limpia la barra de estado y exporta. Alternativa más rápida pero menos
fiel: Claude las saca del build web de Expo (`kuulis-expo.top8.uk`) con Playwright; el render web difiere un poco
de Android y hay que ocultar los avisos de desarrollo.

### 2.3 Opcional: fotografía (real o IA)
| # | Asset | Propósito | Ubicación | Formato | Proporción / resolución | Recortes | E/O |
| --- | --- | --- | --- | --- | --- | --- | --- |
| P1 | Calle de Caracas con el Ávila al fondo, hora dorada, tráfico desenfocado | Lugar y atmósfera | Fondo parcial de la sección de seguridad o de la página de motorizados (no en el hero: el hero es del producto) | AVIF/WebP | 16:9 a 2400×1350; recorte móvil 4:5 a 1080×1350 | Sí: dos encuadres dirigidos (no un recorte automático) | O |
| P2 | Detalle de moto estacionada: casco sobre el asiento, soporte de teléfono en el manubrio | Mundo del motorizado | Hero de `/motorizados` | AVIF/WebP | 4:5 a 1200×1500; escritorio 3:2 a 2400×1600 | Sí | O |
| P3 | Motorizado real de espaldas o de perfil, con casco, en marcha | Personas reales | `/motorizados` | AVIF/WebP | 3:2 | Sí | O — **solo con foto real y autorización firmada**, nunca IA |

**Video:** no se recomienda. Un loop de 6 s de fondo costaría ~1–2 MB en datos móviles venezolanos, no se
reproduce automáticamente en modo ahorro de datos y no cuenta nada que la animación de la ruta no cuente ya.
Si en el futuro se quiere, sería solo en escritorio, ≤ 1,5 MB, MP4 H.264 + WebM, sin audio, con póster estático
y desactivado con movimiento reducido.

## 3. Si se usa IA (P1 y P2)
### Reglas
1. Nunca personas reconocibles, motorizados «de ejemplo» ni interfaces de la app generadas.
2. Nunca matrículas legibles, logotipos de marcas de motos ni de bancos.
3. Toda la serie con la misma dirección: luz natural de tarde, contraste medio, verdes profundos en sombras, un
   solo punto de color cálido (amarillo/ámbar) en la escena, grano fino de película, lente de 35–50 mm.
4. Revisión de artefactos a 100 % (cables, letreros con texto falso, ruedas deformes) antes de usar.
5. Se registra en `web/public/images/CREDITS.md` qué herramienta, plan y fecha generó cada imagen (para licencias).

### Prompts de partida
**P1 — Caracas y el Ávila**
> Documentary photograph, wide avenue in Caracas, Venezuela, late afternoon golden light, the green Ávila mountain
> ridge filling the background, light traffic slightly motion-blurred, mid-rise residential buildings, palm trees,
> one small warm amber light accent, deep green shadows, natural colours, fine film grain, 35mm lens, eye level,
> no legible signs, no logos, no recognisable faces, no text. Aspect ratio 16:9.

**P2 — La moto esperando**
> Close documentary photograph of a parked commuter motorcycle on a Caracas street at dusk, black helmet resting
> on the seat, a smartphone mounted on the handlebar with its screen off, warm amber street light on the tank,
> green-tinted shadows, shallow depth of field, the Ávila mountain softly out of focus in the background, no brand
> logos, no license plate visible, no people, no text. Aspect ratio 4:5.

## 4. Plataformas (si Carlos decide producir P1/P2 con IA)
Precios según comparativas de terceros consultadas el 2026-10-17; **hay que confirmarlos en la web oficial antes
de pagar**, porque cambian a menudo y las fuentes no coinciden.

| Plataforma | Para qué sirve aquí | Precio aproximado | Licencia / riesgo | Veredicto |
| --- | --- | --- | --- | --- |
| Adobe Firefly | Fotos de lugar, buena coherencia, edición por zonas | ~$10/mes (2.000 créditos) | Uso comercial en planes de pago e **indemnización de Adobe**; entrenado con contenido con licencia | **Recomendada si se usa IA**: menor riesgo legal para una marca nueva |
| Midjourney | Estética fotográfica más rica | ~$10–30/mes | Uso comercial en planes de pago, **sin indemnización**; las imágenes son públicas salvo en planes altos | Alternativa si Firefly no da la calidad |
| Google Veo / Runway | Video | Veo vía planes de Google (~$20/mes) o API por segundo; Runway ~$12–35/mes | Términos a revisar | **No**: no se recomienda video (§2.3) |

Recomendación: **un solo mes** del plan básico de Firefly, después de aprobar la dirección y solo si se elige IA en
la pregunta 2. Producción estimada: 2 imágenes finales con sus recortes, a partir de ~40 generaciones.

Fuentes consultadas: [Envato — AI image generators for commercial use](https://elements.envato.com/learn/ai-image-generators-for-commercial-use),
[aicomparison.ai — Midjourney vs Firefly](https://aicomparison.ai/midjourney-vs-adobe-firefly/),
[eesel.ai — Runway pricing](https://eesel.ai/blog/runway-ai-pricing),
[costbench — Veo vs Runway](https://costbench.com/compare/google-veo-vs-runway/).

## 5. Manejo técnico de imágenes
- Carpeta `web/public/images/` con subcarpetas por tipo (`app/`, `install/`, `og/`, `photo/`).
- Cada imagen raster en AVIF + WebP + PNG/JPEG de respaldo con `<picture>`, `width`/`height` explícitos (sin CLS),
  `loading="lazy"` y `decoding="async"` bajo el pliegue; la captura del hero con `fetchpriority="high"` y sin lazy.
- Conversión con `sharp` o `squoosh` **en la máquina de quien produce el asset** (o un script de un solo uso fuera
  del repo); no se añade `@nuxt/image` (ver 06 §6).
- Presupuesto por imagen: capturas ≤ 45 KB (360 px, AVIF), fotos ≤ 120 KB en móvil, OG ≤ 120 KB.
