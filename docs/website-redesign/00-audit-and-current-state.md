# 00 · Auditoría y estado actual

Revisión hecha el 2026-10-17 sobre la rama `qa` (commit `20e956d`) y sobre el sitio desplegado en QA,
`https://kuulis.top8.uk`, con Playwright (Chromium) a 360 y 1440 px de ancho. Todo lo de abajo sale del código o
de esas mediciones, salvo lo marcado como *inferido*.

## 1. Dónde está la web pública
| Qué | Dónde |
| --- | --- |
| App | `web/` del monorepo (doc de origen: `docs/produccion/08-web-publica.md`) |
| Framework | Nuxt 4 (`nuxt ^4.6.0`), Vue 3.5, TypeScript estricto, SSR |
| Paquetes | pnpm 10.18 (`packageManager`), lockfile `web/pnpm-lock.yaml` |
| Dependencias | Solo 4: `nuxt`, `vue`, `@nuxtjs/i18n ^10.6`, `@fontsource-variable/plus-jakarta-sans`. Sin librería de UI, sin store, sin librería de animación |
| Dev | `@nuxt/eslint` (stylistic), `vitest`, `vue-tsc` |
| Scripts | `pnpm dev` (puerto 3001, proxy de `/api` a `:8000`), `lint`, `typecheck`, `test`, `build` |
| Build y deploy | `web/Dockerfile` (node 22 alpine, `.output/server/index.mjs`, healthcheck en `/robots.txt`). Coolify despliega `kuulis-web-<entorno>` con `watch_paths` `web/**` |
| CI | Job `web` en `.github/workflows/ci.yml`: lint, tipos, tests y build cuando cambia `web/**` |
| Datos | La web llama a la API en su mismo dominio (`/api/v1`): `GET /public/site`, `GET /app/version`, `GET /legal`, `GET /help/articles`, `GET /config/public`, `POST /support/contact`, `GET /referrals/codes/{code}`, `GET /public/rides/shared/{token}` |

Dominios: en QA la web vive en `kuulis.top8.uk` (y `www.`), el admin en `kuulis-qa.top8.uk` / `admin.top8.uk`.
El dominio de producción de la web **todavía no existe** (`docs/deployment.md`: «por crear»).

## 2. Páginas y rutas
| Ruta | Archivo | Qué hace | Tipo |
| --- | --- | --- | --- |
| `/` | `app/pages/index.vue` (410 líneas) | Hero, pasajeros, motorizados con tabla de cuota, cómo funciona, ciudades, FAQ, cierre | Marketing |
| `/motorizados` | `app/pages/motorizados.vue` | Por qué, requisitos y documentos (de la API), tabla de cuota, pasos para registrarse | Marketing |
| `/descargar` | `app/pages/descargar.vue` | APK más reciente (versión, tamaño, fecha, SHA-256), «muy pronto» si no hay, aviso para iPhone, pasos de instalación | Conversión |
| `/ayuda`, `/ayuda/[slug]` | `app/pages/ayuda/` | Centro de ayuda con búsqueda, filtro por público y temas; artículo con «¿te ayudó?» | Soporte |
| `/contacto` | `app/pages/contacto.vue` | Formulario sin cuenta con prueba de trabajo (`utils/pow.ts`) en lugar de captcha; WhatsApp y email si están configurados | Soporte |
| `/legal`, `/legal/[kind]` | `app/pages/legal/` | Textos legales versionados desde la API | Legal |
| `/verify-email`, `/reset-password` | `app/pages/` | Destino de los emails; `noindex`, `no-store` | Utilidad (no tocar lógica) |
| `/v/[token]` | `app/pages/v/[token].vue` | Viaje compartido en vivo con mapa OSM, PIN y SOS | Utilidad (no tocar lógica) |
| `/i/[code]` | `app/pages/i/[code].vue` | Invitación de motorizado (referidos) con deep link `kuulis://` | Utilidad (no tocar lógica) |
| 404 / error | `app/error.vue` | Error propio con `noindex` | Utilidad |

Layout único `app/layouts/default.vue`: cabecera fija con blur, logotipo, 4 enlaces (Motorizados, Descargar,
Ayuda, Legal), botón de idioma (muestra el **otro** idioma, `EN`/`ES`), botón amarillo «Descargar la app» y menú
hamburguesa por debajo de 760 px (despliega una lista bajo la cabecera). Footer con logotipo, lema, 7 enlaces,
email de soporte opcional y «© 2026 Kuulis · Hecho en Venezuela».

Componentes: `KuulisWordmark` (texto «kuulis» en 800 con el punto en `--accent`), `FeeTable`, `LegalMarkdown`,
`MarkdownSpans`. Composables `useApi`, `useSite`, `useSupport`.

## 3. Sistema de diseño actual
Un único archivo global, `app/assets/css/main.css` (~330 líneas), con tokens en `:root` y modo oscuro por
`prefers-color-scheme`. Cada página añade CSS `scoped`.

### Colores (fuente de verdad: `main.css` y `docs/product/mobile-design.md`, paleta «Verde Ávila», decidida 2026-10-09)
| Token | Claro | Oscuro | Uso actual |
| --- | --- | --- | --- |
| `--primary` | `#0E7C5A` | `#34C08C` | Botones, enlaces, eyebrow, números de pasos |
| `--primary-pressed` | `#0B6A4C` | `#2AA77A` | Hover |
| `--on-primary` | `#FFFFFF` | `#06231A` | Texto sobre verde |
| `--accent` | `#FFC83D` | `#FFD25E` | Botón principal de descarga, punto del logotipo, foco |
| `--on-accent` | `#3A2A00` | (igual) | Texto sobre amarillo |
| `--bg` | `#F3F7F4` | `#0B1310` | Fondo |
| `--surface` | `#FFFFFF` | `#131D19` | Tarjetas |
| `--surface-alt` | `#EAF5EF` | `#18261F` | Banda de motorizados, botón de idioma |
| `--text` | `#14201B` | `#E8F0EC` | Texto; también fondo del bloque final |
| `--muted` | `#5B6A63` | `#9AADA4` | Texto secundario |
| `--border` | `#DCE6E0` | `#24332C` | Bordes |
| `--hero` / `--hero-shade` | `#0E7C5A` / `#0A5C43` | `#0C4A37` / `#072E22` | Degradado del hero (con `#18A374` fijo en el código) |
| Estados | `--danger #B42318`, `--success #15803D` | `#F97066`, `#4ADE80` | Avisos |

`theme-color` `#0E7C5A`. Favicon SVG: cuadrado verde con «k» blanca y punto amarillo.

### Contraste medido (WCAG 2.x)
| Par | Ratio | Resultado |
| --- | --- | --- |
| Blanco sobre `#0E7C5A` | 5,19 | AA texto normal |
| `#3A2A00` sobre `#FFC83D` | 8,99 | AAA |
| `#0E7C5A` sobre `#F3F7F4` | 4,80 | AA (justo) |
| `#5B6A63` sobre `#F3F7F4` | 5,27 | AA |
| **Blanco sobre `#18A374`** (esquina clara del degradado del hero) | **3,22** | **Falla AA para texto normal**: el lead y la píldora del hero pueden caer ahí en pantallas anchas |
| **`#FFC83D` sobre `#F3F7F4`** | **1,43** | El amarillo nunca puede ser texto ni icono sobre fondo claro (hoy solo es el punto del logo: decorativo, aceptable) |
| `#FFC83D` sobre `#14201B` | 10,85 | Excelente: el amarillo brilla sobre tinta |
| Blanco sobre `#0A5C43` | 8,00 | AAA |

### Tipografía, espacio y forma
- Una sola familia: **Plus Jakarta Sans Variable** (fontsource, autoalojada, por subconjunto de `unicode-range`).
  Misma fuente que la app móvil.
- `body` 17 px / 1,55. `h1` `clamp(2.1rem, 6vw, 3.6rem)` 800; `h2` `clamp(1.6rem, 4vw, 2.3rem)` 800; `h3` 1,15 rem.
- Contenedor de 1080 px con 20 px de margen; secciones de 64 px. Radio 20 px en tarjetas, píldora en botones.
- Botones de 52 px de alto (44 px en la cabecera).
- No hay escala de espaciado como tokens: los valores están sueltos en cada archivo.

### Movimiento
Solo `transform: scale(0.98)` al pulsar botones y transición de fondo de 150 ms. `prefers-reduced-motion` anula
todas las transiciones. No hay librería de animación.

## 4. Assets existentes
| Asset | Dónde | Estado |
| --- | --- | --- |
| Logotipo tipográfico «kuulis.» | `KuulisWordmark.vue` (texto, no SVG) | Decidido como logo provisional (doc 08). No hay logo final |
| Favicon | `web/public/favicon.svg` | Usa la fuente por nombre: en sistemas sin Plus Jakarta Sans la «k» se dibuja en Arial |
| Icono 192 | `web/public/icon-192.png` | Correcto |
| Open Graph | `web/public/og.png` (1200×630) | Uno solo para los dos idiomas |
| Ilustración del hero | SVG en línea en `index.vue`: mapa esquemático con ruta punteada y tarjeta «Luis está en camino · Yamaha YBR · $2.40 · 4 min» | Es una **interfaz inventada** (no es la app real). Sirve como ilustración, pero no debe parecer captura |
| Iconos de la app móvil | `mobile/assets/` (icon, adaptive icon, splash) | Reutilizables para la web (marco de dispositivo, favicon) |
| Capturas de la app | `/mnt/project-files/kuulis/rediseno-2026-10/app-actual/` y `perfil-2026-10/` (780 px de ancho) | Sacadas del build web de desarrollo: una muestra el aviso rojo de error de React. **No sirven para marketing**; hay que sacar capturas limpias |
| Referencias de Yummy | `docs/product/references/yummy/` | Solo referencia interna; nunca se publican |
| Fotos, video, ilustraciones | — | No hay ninguno |

## 5. SEO, metadatos e indexación
- `useSeoMeta` por página con título y descripción traducidos; `og:image` absoluta en `app.vue`.
- `robots.txt` dinámico: bloquea todo salvo `NUXT_PUBLIC_APP_ENV=production`; en producción excluye
  `/verify-email`, `/reset-password` e `/i/`.
- `sitemap.xml` dinámico: 11 páginas fijas + artículos de ayuda publicados (en español).
- **No hay `<link rel="canonical">`** ni `hreflang`.
- **El inglés no es indexable**: la estrategia de i18n es `no_prefix` con cookie `kuulis_locale`; la misma URL
  sirve los dos idiomas, así que un buscador solo ve el que detecte. No hay forma de enlazar a la versión en inglés.
- No hay datos estructurados (correcto por ahora: no hay organización registrada ni reseñas).
- `og:locale` no está definido.

## 6. Idiomas
- `@nuxtjs/i18n` con `es` (por defecto, `es-VE`) y `en` (`en-US`), archivos `web/i18n/locales/{es,en}.json`
  con las mismas 376 líneas. Detección por navegador con cookie. `<html lang>` se actualiza.
- El español suena natural y venezolano neutro. El inglés es correcto pero en varios sitios es traducción literal.
- Textos desactualizados encontrados:
  - `invite.freeMonth` habla de «un mes de suscripción gratis», pero el doc 22 cambió el premio a 5 USD en la
    billetera del que invita. Solo se muestra si `program.referred_free_month` es verdadero, así que hoy
    probablemente no aparece (*inferido*), pero conviene revisarlo.
  - FAQ «¿Tengo iPhone?»: correcto (la PWA para iPhone quedó pospuesta el 2026-10-12, doc 09).

## 7. Analítica y conversión
- **La web no tiene analítica** (ni Umami, ni Plausible, ni eventos). El doc 08 la proponía; el doc 19 implementó
  analítica de producto solo en la API y la app.
- Conversión principal: botón **Descargar** → `/descargar` → `GET /api/v1/app/download` (redirección a un enlace
  temporal del APK en S3). Hoy no se puede medir cuántos lo pulsan.
- Conversión secundaria: «Quiero manejar» → `/motorizados` → descarga; registro como motorizado dentro de la app.
- No hay tiendas (Play Store/App Store): el APK se instala a mano. iPhone: sin app.

## 8. Elementos funcionales a preservar (inventario)
| Elemento | Destino actual | Nota |
| --- | --- | --- |
| Logotipo en cabecera | `/` | |
| Nav: Motorizados, Descargar, Ayuda, Legal | rutas internas | |
| Botón de idioma | `setLocale(otro)` | Etiqueta accesible fija en el otro idioma |
| «Descargar la app» (cabecera) | `/descargar` | |
| Hero: «Descargar para Android», «Quiero manejar» | `/descargar`, `/motorizados` | |
| «Ver requisitos» | `/motorizados` | |
| FAQ | `<details>` nativo | |
| Bloque final «Descargar para Android» | `/descargar` | |
| Botón APK | `/api/v1/app/download` (`rel=nofollow`) | Solo si hay versión publicada |
| Huella SHA-256 | `<details>` | |
| Footer: 7 enlaces + email | rutas internas, `mailto:` | WhatsApp aparece solo en Ayuda/Contacto si está configurado |
| Formulario de contacto | `POST /support/contact` con prueba de trabajo | No tocar lógica |
| Búsqueda y filtros de ayuda | query string | No tocar lógica |
| «Ya tengo la app» | `kuulis://profile/invite?code=` | |

Datos dinámicos que **no** se pueden fijar en el diseño: ciudades (`/public/site`: en QA devuelve
«Caracas · Valencia» porque QA tiene la ciudad de pruebas de Carlos; en producción será Caracas), meses gratis,
tramos de la cuota, requisitos, métodos de pago y la existencia del APK.

## 9. Rendimiento medido (QA, 2026-10-17)
| Página | Peso total descomprimido | JS descomprimido | Desbordamiento horizontal |
| --- | --- | --- | --- |
| `/` 360 px | 381 KB | 306 KB | No |
| `/motorizados` | 348 KB | 306 KB | No |
| `/descargar` | 342 KB | 304 KB | No |
| `/ayuda` | 368 KB | 314 KB | No |
| `/contacto` | 353 KB | 310 KB | No |

El doc 08 registró ~85 KB de JS **comprimido**. Las medidas de arriba son con Playwright, sin limitación de red.

### Línea base con Lighthouse (M0, 2026-10-17)
Lighthouse 12 (`npx`, Chromium sin interfaz) contra QA, `https://kuulis.top8.uk`. Móvil = perfil por defecto
(Moto G, 4G lenta simulada); escritorio = `--preset=desktop`. Las ejecuciones de escritorio salieron **en inglés**
(Lighthouse manda `Accept-Language: en-US` y la web detecta el idioma); las de móvil, en español.

| Página | Perf. / A11y / Buenas prácticas / SEO (móvil) | LCP | CLS | TBT | Peso transferido | Escritorio (Perf. / A11y) |
| --- | --- | --- | --- | --- | --- | --- |
| `/` | 93 / 100 / 93 / 63 | 1,9 s | 0,031 | 260 ms | 159 KB | 100 / 100 |
| `/motorizados` | 98 / 98 / 93 / 63 | 1,9 s | 0 | 100 ms | 150 KB | 100 / 98 |
| `/descargar` | 98 / 100 / 93 / 63 | 1,9 s | 0,012 | 80 ms | 148 KB | 100 / 100 |
| `/ayuda` | 98 / 100 / 93 / 63 | 1,9 s | 0 | 80 ms | 159 KB | 92 / 100 (**CLS 0,178**) |
| `/contacto` | 98 / 100 / 93 / 63 | 1,9 s | 0 | 80 ms | 153 KB | 100 / 100 |

Lectura:
- **SEO 63 es esperado en QA**: `robots.txt` bloquea todo fuera de producción. Se medirá en configuración de
  producción (`pnpm build` + `NUXT_PUBLIC_APP_ENV=production`) en los milestones de SEO.
- **Buenas prácticas 93** por errores de consola ajenos a la web: (1) Cloudflare inyecta su *beacon* de Web
  Analytics (`static.cloudflareinsights.com`) y la CSP lo bloquea; (2) una petición a
  `/_nuxt/builds/meta/<build>.json` devolvió 502 una vez (al repetirla dio 200: intermitente del proxy).
- **CLS 0,178 en `/ayuda` (escritorio, inglés)**: la sección `container narrow` se desplaza al cargar. Se
  corrige en M7.
- **`heading-order` en `/motorizados`**: tarjetas con `h3` justo después del `h1`. Se corrige en M6.
- **`label-content-name-mismatch`** en el botón de idioma: se ve «EN» pero se llama «Change language to
  English» (WCAG 2.5.3). Se corrige en M2.
- El LCP móvil de 1,9 s es casi todo latencia del servidor (documento en ~640 ms) y la CSS bloqueante; la página
  ya es ligera (~150 KB). El rediseño tiene que mantenerse en ese orden de magnitud (objetivo de 06 §7: ≤ 300 KB).

### Medición final (M10, 2026-10-17, QA con el rediseño M0–M9)
Mismo método que la línea base (Lighthouse 12 contra `https://kuulis.top8.uk`, móvil por defecto y escritorio).

| Página | Perf. / A11y / Buenas prácticas / SEO (móvil) | LCP | CLS | TBT | Peso transferido | Escritorio (Perf. / A11y) |
| --- | --- | --- | --- | --- | --- | --- |
| `/` | 96 / 100 / 93 / 66 | 2,1 s | 0 | 90 ms | 196 KB | 100 / 100 |
| `/motorizados` | 97 / 100 / 93 / 66 | 2,1 s | 0 | 100 ms | 194 KB | 100 / 100 |
| `/seguridad` | 97 / 100 / 93 / 66 | 2,1 s | 0 | 60 ms | 194 KB | 100 / 100 |
| `/descargar` | 97 / 100 / 93 / 66 | 2,1 s | 0 | 100 ms | 193 KB | 100 / 100 |
| `/ayuda` | 96–97 / 100 / 93 / 66 | 2,1 s | 0 | 110–120 ms | 199 KB | 100 / 100 (CLS 0) |
| `/contacto` | 97 / 100 / 93 / 66 | 2,1 s | 0,021 | 110 ms | 192 KB | 100 / 100 |

Frente a la línea base: rendimiento igual o mejor, accesibilidad 100 en todas, el CLS de `/ayuda` en escritorio
pasó de 0,178 a 0, y el peso subió de ~155 a ~195 KB (presupuesto 300 KB). El JavaScript transferido de inicio pasó
de 103 a 127 KB, por encima del margen de +8 KB de 06 §7 (ver 08 §7). Buenas prácticas sigue en 93 por el
*beacon* de Cloudflare y SEO en 66 por el `robots.txt` de QA; en configuración de producción (local) dan 100 y 100.
Capturas de página completa a 360 y 1440 px, claro y oscuro: `kuulis/web-m10/` en la carpeta del proyecto.

### Capturas y enlaces de referencia (M0)
- Capturas de página completa en español e inglés: todas las páginas a 360 y 1440 px, y la de inicio a 320,
  360, 414, 768, 1024, 1440 y 1920 px, más los JSON de Lighthouse, en la carpeta compartida del proyecto
  `kuulis/web-linea-base-2026-10-17/` (fuera del repo por tamaño, 18 MB).
- Sin desbordamiento horizontal en ninguna página a ningún ancho, `<html lang>` correcto y un solo `h1` por página.
- Todos los enlaces internos responden 200 (inicio, motorizados, descargar, ayuda y sus 9 artículos, contacto,
  legal y sus 5 textos); `/api/v1/app/download` responde 302 al APK. En QA no hay email ni WhatsApp de soporte
  configurados, así que esos enlaces no aparecen.

## 10. Accesibilidad e infraestructura de pruebas
- Bien: enlace «Saltar al contenido», `aria-label` en nav y menú, `aria-expanded`, `:focus-visible` amarillo de
  3 px, `<details>` nativos, campos con etiquetas, `prefers-reduced-motion`.
- Mal o a revisar: el contraste del degradado del hero; `.sr-only` sin `margin:-1px`/`padding:0`; el menú móvil no
  atrapa foco ni se cierra con Escape; el foco amarillo es casi invisible sobre fondos claros (1,43:1) — no cumple
  WCAG 2.2 «Focus Appearance»; el botón de idioma muestra «EN» sin indicar que es un cambio de idioma visible.
- Tests: 4 archivos de Vitest con funciones puras (`invite`, `markdown`, `pow`, `sharedRide`). Desde M0 hay
  además un test e2e de humo con Playwright y axe (`web/tests/e2e/smoke.spec.ts`, `pnpm e2e`): 6 páginas × 2
  idiomas × 2 anchos (320 y 1440 px). No hay tests de componentes ni de regresión visual.

## 11. Restricciones
- El público son teléfonos Android de gama baja con datos móviles caros y lentos (README de `web/`).
- CSP estricta en `nuxt.config.ts`: `script-src 'self'`, `font-src 'self'`, `img-src 'self' data: https:`,
  `connect-src 'self'`. Nada de fuentes de Google, CDNs de scripts ni videos de terceros sin cambiarla.
- Sin empresa registrada (doc de visión): nada de datos legales de empresa, premios, cifras ni inversores.
- Coolify despliega en cada push a `qa`; cada milestone sale a QA al fusionarse.

## 12. Debilidades principales
1. **Parece una plantilla correcta, no una marca.** Hero verde con degradado radial + tarjetas blancas iguales +
   tabla + pasos numerados + FAQ + bloque oscuro: es el patrón de cualquier landing de startup. Sin el logotipo
   no se reconocería como Kuulis.
2. **El producto no se ve.** No hay ni una captura real de la app; la única imagen es un mapa esquemático.
3. **El diferencial más fuerte (cero comisión por viaje) está repartido** en la píldora, el título y una sección
   intermedia en lugar de contarse con fuerza.
4. **Mezcla de públicos en el hero**: el título habla al motorizado («sin comisión») y el lead al pasajero.
5. **Seguridad infravalorada**: PIN de inicio, SOS, viaje compartido en vivo, chat y calificaciones existen en la
   app (docs 11, 15, 23) pero la web lo resume en una tarjeta.
6. **El amarillo se usa poco y mal**: botón sobre verde (3,35:1 entre ambos colores, bien para el botón pero
   compite con el texto blanco) y foco ilegible sobre fondo claro.
7. **Inglés no indexable** y sin URL propia.
8. **Sin medición** de la conversión principal.
9. **Sin sistema de espaciado ni escala tipográfica** como tokens: cada página improvisa.
