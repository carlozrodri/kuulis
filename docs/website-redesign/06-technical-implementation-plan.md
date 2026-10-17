# 06 · Plan técnico

## 1. Principios
- **Misma pila:** Nuxt 4 + Vue 3 + TypeScript + CSS propio + `@nuxtjs/i18n` + pnpm + Dockerfile actual + Coolify.
  No se cambia el framework, el gestor de paquetes ni el modelo de despliegue.
- **Cero dependencias de runtime nuevas.** Animación con CSS + `IntersectionObserver`; iconos copiados como SVG;
  imágenes optimizadas antes de entrar al repo.
- **Solo `web/`.** Las páginas de utilidad (`/v`, `/i`, `/verify-email`, `/reset-password`, contacto y ayuda)
  conservan su lógica; solo heredan tokens, layout y estilos.
- **Los datos siguen viniendo de la API** (`/public/site`, `/app/version`, `/config/public`…). Ningún número del
  negocio se escribe en el código.

## 2. Arquitectura CSS
Hoy: un `main.css` global + `scoped` por página. Se mantiene el enfoque (sin Tailwind ni librería), ordenado en
capas con `@layer` para evitar guerras de especificidad:

```
web/app/assets/css/
  tokens.css      @layer tokens   colores (claro/oscuro), escala tipográfica, espacios, radios, sombras, duraciones
  base.css        @layer base     reset, tipografía, enlaces, foco, .sr-only, movimiento reducido
  layout.css      @layer layout   .container, .grid-12, .section, .field-* (campos de color)
  components.css  @layer components  .btn, .chip, .table, .notice, .field (formularios)
  main.css        importa las cuatro en orden
```

### Tokens nuevos (además de los colores actuales, que no cambian)
| Grupo | Tokens |
| --- | --- |
| Color (alias semánticos) | `--field-brand: var(--primary)`, `--field-brand-deep: #0A5C43` (hoy `--hero-shade`), `--field-ink: var(--text)`, `--on-field: #fff`, `--focus-inner: var(--text)`, `--focus-outer: var(--accent)` |
| Tipografía | `--font-display`, `--font-h1`, `--font-h2`, `--font-h3`, `--font-lead`, `--font-body`, `--font-small`, `--font-label`, `--font-number` (valores de 02 §4), `--leading-*`, `--tracking-*`. (En M1 se cambió el nombre `--step-*` por nombres de rol, más fáciles de leer.) |
| Espacio | `--space-1` (4 px) … `--space-10` (160 px) en múltiplos de 4; `--section-y: clamp(64px, 8vw, 128px)`; `--gutter: clamp(16px, 4vw, 32px)` |
| Forma | `--radius-sm 12px`, `--radius-md 20px` (= `--radius` actual), `--radius-lg 28px`, `--radius-pill 999px` |
| Movimiento | `--dur-fast 120ms`, `--dur-base 200ms`, `--dur-slow 320ms`, `--ease-out cubic-bezier(.2,.7,.2,1)` |

`--hero` y `--hero-shade` se mantienen como alias durante la transición para no romper páginas aún no migradas, y
se eliminan en el último milestone.

**Hecho en M1 (2026-10-17):** capas y tokens en `web/app/assets/css/`; los `h1`–`h3` de las páginas actuales
conservan sus tamaños (las secciones rediseñadas usan los tokens nuevos); `text-wrap: balance` **no** se aplica
por defecto porque en titulares de dos frases («Tu moto en minutos. Sin comisión por viaje.») corta peor: se usará
caso por caso en `Headline`; `text-wrap: pretty` sí en párrafos. Bandas `.band-brand` / `.band-ink` listas (el
botón principal pasa a amarillo dentro de ellas). Cara de respaldo «Plus Jakarta Sans Fallback» (Arial/Roboto con
`size-adjust` 104,8 %, `ascent-override` 99,3 %, `descent-override` 21 %, medidos en el navegador) y precarga del
subconjunto latino de la fuente.

## 3. Componentes
| Componente | Nuevo / cambia | Responsabilidad |
| --- | --- | --- |
| `layouts/default.vue` | Cambia | Cabecera con estado transparente/sólido, menú móvil accesible, footer de 4 columnas |
| `components/SiteHeader.vue`, `SiteFooter.vue`, `MobileMenu.vue`, `LanguageSwitch.vue` | Nuevos | Se extraen del layout (hoy 330 líneas en un archivo) |
| `components/KuulisWordmark.vue` | Cambia poco | Admite `tone` (claro/oscuro); el punto sigue en `--accent` |
| `components/brand/BrandDot.vue`, `Headline.vue`, `RouteLine.vue`, `AvilaRidge.vue`, `PinDigits.vue` | Nuevos | Elementos de marca (02 §10) |
| `components/PhoneFrame.vue` | Nuevo | Marco + `<picture>` con fuentes AVIF/WebP y `alt` traducido |
| `components/PaymentChips.vue` | Nuevo | Métodos de `/public/site` con etiquetas traducidas |
| `components/FeatureRows.vue` | Nuevo | Filas editoriales (icono/número + título + texto) en vez de grillas de tarjetas |
| `components/FeeTable.vue` | Cambia | Estilo nuevo, `caption`, cifras tabulares; lógica igual |
| `components/FeeExample.vue` | Nuevo | Ejemplo «si ganas $250 pagas X» calculado con los tramos reales |
| `components/Icon.vue` | Nuevo | ~12 iconos de trazo en un mapa de rutas SVG |
| `components/home/*.vue` | Nuevos | Una sección por archivo: `HomeHero`, `HomePrice`, `HomeHow`, `HomeDrivers`, `HomeSafety`, `HomeFaq`, `HomeDownload` |
| `composables/useReveal.ts` + directiva `v-reveal` | Nuevo | Aparición con `IntersectionObserver`, respeta movimiento reducido, no oculta nada sin JS |
| `composables/useSeo.ts` | Nuevo | Título, descripción, OG por idioma, canonical y alternates en un solo sitio |
| `pages/index.vue` | Reescrita | Solo compone las secciones |
| `pages/motorizados.vue` | Reescrita | Estructura de 03 §6 |
| `pages/seguridad.vue` | **Nueva** | Estructura de 03 §7 |
| `pages/descargar.vue` | Cambia | Plantilla y estilos; lógica de versión e iPhone intacta |
| `pages/ayuda/*`, `contacto.vue`, `legal/*`, `i/[code].vue`, `v/[token].vue`, `verify-email.vue`, `reset-password.vue`, `error.vue` | Solo estilos | Sustituir valores sueltos por tokens; ningún cambio de `<script>` salvo `useSeo` |

## 4. Idiomas (i18n)
### Estado actual
`strategy: 'no_prefix'` + cookie: una URL para dos idiomas, inglés no indexable, sin `hreflang` posible.

### Propuesta (pregunta 1 del README)
```ts
i18n: {
  defaultLocale: 'es',
  strategy: 'prefix_except_default',      // español en /, inglés en /en
  customRoutes: 'config',
  pages: {
    motorizados: { es: '/motorizados', en: '/drivers' },
    seguridad: { es: '/seguridad', en: '/safety' },
    descargar: { es: '/descargar', en: '/download' },
    'ayuda': { es: '/ayuda', en: '/help' },
    'ayuda-slug': { es: '/ayuda/[slug]', en: '/help/[slug]' },
    contacto: { es: '/contacto', en: '/contact' },
  },
  baseUrl: <NUXT_PUBLIC_SITE_URL>,         // para hreflang y canonical absolutos
  detectBrowserLanguage: { useCookie: true, cookieKey: 'kuulis_locale', redirectOn: 'root', fallbackLocale: 'es' },
}
```
- **Enlaces internos** con `localePath()` / `<NuxtLinkLocale>`; el selector usa `switchLocalePath()`.
- **Páginas de utilidad** (`/v`, `/i`, `/verify-email`, `/reset-password`): los emails y la app enlazan a la URL
  sin prefijo. Para no romper a quien hoy las recibe en inglés, un middleware de ruta solo para esas páginas
  redirige a la variante `/en/...` si la cookie `kuulis_locale` es `en` (mismo comportamiento que hoy, con URL
  correcta). La API no cambia.
- **Riesgo de redirección por idioma:** solo se redirige en la raíz y solo la primera visita; los buscadores
  (que no mandan cookie ni suelen mandar `Accept-Language` en inglés) ven el español en `/` y llegan al inglés por
  `hreflang`. Se verifica en M5.
- **Paridad de textos:** test de Vitest que compara las claves de `es.json` y `en.json` y falla si falta alguna o
  si un valor en inglés es idéntico al español (salvo una lista de excepciones como «Kuulis», «Zelle»).
- Los nombres de los métodos de pago, documentos y temas de ayuda siguen en los JSON, como hoy.

Si Carlos prefiere **no** cambiar URLs: se mantiene `no_prefix`, se añade canonical, y el inglés queda sin indexar
(se documenta como limitación).

## 5. SEO
| Elemento | Plan |
| --- | --- |
| Título y descripción | Por página y por idioma (ya existen; se reescriben con 03) vía `useSeo` |
| Canonical | Autorreferente por idioma, absoluto con `NUXT_PUBLIC_SITE_URL`, sin query string |
| `hreflang` | `es-VE`, `en` y `x-default` (→ español) en las páginas indexables, generados por `useLocaleHead` de `@nuxtjs/i18n` |
| Open Graph | `og:title`, `og:description`, `og:image` por página e idioma (A8), `og:locale` `es_VE` / `en_US` + `og:locale:alternate` |
| `sitemap.xml` | Ambas variantes de cada página con `xhtml:link rel="alternate"`; artículos de ayuda por idioma (la API ya acepta `locale`) |
| `robots.txt` | Igual que hoy (bloquea todo fuera de producción) + `Disallow: /en/i/` |
| `noindex` | Se mantiene en `/v`, `/verify-email`, `/reset-password`, `/i` y errores, también en sus variantes `/en` |
| Encabezados | Un `h1` por página; jerarquía sin saltos |
| Datos estructurados | **Ninguno** por ahora: no hay organización registrada, ni reseñas reales, ni app en tiendas. `FAQPage` tampoco (Google ya no lo muestra para sitios no oficiales/sanitarios). Se reevalúa al registrar la empresa |

## 6. Imágenes y assets
- Archivos en `web/public/images/…`, servidos por Nitro con `compressPublicAssets` (ya activo). Cabecera
  `Cache-Control: public, max-age=31536000, immutable` para `/images/**` mediante `routeRules` (los nombres
  llevan hash o versión: `quote-es-v1.avif`).
- Formatos y presupuestos en 05 §5.
- **No se añade `@nuxt/image`:** las imágenes son pocas y fijas; optimizarlas una vez es más simple que añadir un
  módulo con su proveedor y su caché. Alternativa considerada y descartada por costo/beneficio.
- CSP: no cambia (`img-src 'self' data: https:` ya cubre todo; no hay fuentes ni scripts externos).

## 7. Rendimiento
### Línea base
Se mide en M0 con Lighthouse (móvil, 4G lenta simulada) sobre QA y se registra en 00 §9. Medido hoy sin
limitación: ~381 KB descomprimidos en `/`, ~306 KB de JS descomprimido (~85 KB comprimido según el doc 08).

### Objetivos (página de inicio, móvil, producción)
| Métrica | Objetivo |
| --- | --- |
| LCP | ≤ 2,5 s (Lighthouse móvil) |
| CLS | ≤ 0,05 |
| INP / TBT | TBT ≤ 150 ms |
| Peso transferido primera visita | ≤ 300 KB (HTML + CSS + JS + fuente + imagen del hero) |
| JS comprimido | ≤ línea base + 8 KB |
| Lighthouse | Rendimiento ≥ 90, Accesibilidad ≥ 95, Buenas prácticas ≥ 95, SEO = 100 (en configuración de producción) |

### Medidas
- La captura del hero es la candidata a LCP: `fetchpriority="high"`, sin lazy, ~45 KB AVIF.
- Fuente: precarga del archivo `latin` de la variable (`<link rel="preload" as="font" crossorigin>`), `font-display:
  swap` y una cara de respaldo con `size-adjust`/`ascent-override` calculados para que el cambio no mueva el texto.
- Animaciones solo con `transform`/`opacity`; la ruta es un `<path>` pequeño.
- Componentes de secciones bajo el pliegue sin JS propio (son estáticos; el SSR los entrega en HTML).
- Revisar si `nuxt` incluye algo innecesario en cliente (p. ej. `payloadExtraction`); cualquier ajuste se mide
  antes y después.

## 8. Accesibilidad
Requisitos en 04 §9. Herramientas: revisión manual con teclado y lector (TalkBack en Android si Carlos puede;
VoiceOver/NVDA no disponibles en el entorno de Claude), y `axe-core` automático (ver §9).

## 9. Pruebas y validación
| Nivel | Herramienta | Qué |
| --- | --- | --- |
| Estático | `pnpm lint`, `pnpm typecheck` | Igual que hoy (CI) |
| Unitario | `vitest` (existente) | Paridad de claves i18n; `FeeExample` (tramos → cuota); utilidades de idioma/rutas |
| Build | `pnpm build` | Igual que hoy (CI) |
| E2E / responsive / a11y | Playwright + axe | Recorrido de cada página en 320, 360, 414, 768, 1024, 1440 y 1920 px, en es y en; sin desbordamiento horizontal; sin errores de consola; sin enlaces rotos internos; axe sin violaciones serias; capturas para revisión visual |
| Rendimiento | Lighthouse CLI | Por milestone visual, sobre `pnpm build && pnpm preview` y sobre QA |

**Dependencias de desarrollo propuestas** (pregunta 5 del README; solo dev, sin efecto en el bundle):
`@playwright/test` (mantenido por Microsoft, estándar) y `@axe-core/playwright` (Deque, estándar de a11y). Con
ellas los checks viven en el repo (`web/tests/e2e/`) y cualquiera los puede repetir. Alternativa sin dependencias:
Claude los ejecuta con su Playwright global y pega los resultados en cada PR, pero no quedan en el repo ni en CI.
Lighthouse se ejecuta con `npx` cuando se necesita, sin añadirlo a `package.json`.

## 10. Analítica (fuera de alcance salvo aprobación)
La web no mide nada hoy. Propuesta para después del rediseño, como milestone opcional: Umami autoalojado en
Coolify (sin cookies, ~2 KB), con eventos `download_click`, `apk_download`, `drive_cta`, `language_switch`. Exige
añadir su dominio a `script-src` y `connect-src` de la CSP. No se implementa sin el OK de Carlos.

## 11. Fuera de alcance
API, admin, app móvil, infraestructura, Coolify, dominios, CI (salvo añadir los e2e si se aprueba), PWA para
iPhone, blog, CMS, modo oscuro manual, nuevas funciones de producto.
