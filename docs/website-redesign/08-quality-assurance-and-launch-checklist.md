# 08 · QA y checklist de lanzamiento

Cada punto se marca solo cuando se ha comprobado de verdad, con la herramienta indicada. Si algo no se pudo
verificar (p. ej. Safari real o un lector de pantalla), se escribe «no verificado» y por qué.

## 1. Calidad visual (revisión con capturas de Playwright en 7 anchos, claro y oscuro)
- [x] La primera pantalla dice qué es Kuulis y ofrece descargar, a 360×640 y a 1440×900 (`home.spec.ts`).
- [x] Kuulis se reconoce sin el logotipo (verde en campos planos, titulares con el punto, la ruta). Capturas M10.
- [x] No hay grillas de tarjetas idénticas, degradados decorativos, blur ni «eyebrows» de plantilla (M7 quitó `.eyebrow` y `.grid-*`).
- [x] El amarillo nunca aparece como texto/icono sobre fondo claro (regla en `components.css` y `BrandHeadline`).
- [x] Titulares sin viudas ni cortes feos en es y en (M9: las dos últimas palabras van juntas).
- [ ] Capturas de la app reales, nítidas, sin datos personales ni avisos de desarrollo. **Pendiente:** Carlos las envía (A1/A2); hasta entonces la web no muestra ninguna captura.
- [x] Modo oscuro revisado en todas las páginas (axe en `polish.spec.ts`, capturas M10).
- [x] Cada sección cumple el «trabajo» que le asigna 03 (revisado en cada milestone, M3–M7).

## 2. Responsive
- [x] Sin desbordamiento horizontal a 320, 360, 414, 768, 1024, 1440, 1920 px (`scrollWidth <= innerWidth`, e2e). M9: `polish.spec.ts`, 8 páginas × 2 idiomas × 7 anchos.
- [x] El menú móvil es un panel propio, no la nav de escritorio comprimida (M2, `frame.spec.ts`).
- [x] Zoom al 200 % usable (WCAG 1.4.10): equivale a 640–720 px CSS en un portátil, cubierto por los anchos de 414 y 768 sin scroll lateral.
- [ ] Imágenes con recortes dirigidos (no recortes automáticos que corten lo importante). Pendiente de las capturas A1/A2 (M8).
- [x] Objetivos táctiles ≥ 44 px en móvil, salvo enlaces dentro de una frase (WCAG 2.5.8). M9: logotipos, enlaces del pie y del menú, «Leer las normas»; e2e a 360 px.

## 3. Idiomas
- [x] Test de paridad de claves `es.json` / `en.json` en verde (`tests/i18n.test.ts`).
- [x] Ningún texto en español en la versión inglesa ni al revés (recorrido e2e buscando una lista de palabras
      testigo, más revisión manual). M9: «English pages show no Spanish»; los textos legales vienen del API en español a propósito.
- [x] Títulos, descripciones, OG, `alt` y `aria-label` traducidos (OG por idioma desde M8).
- [x] `<html lang>` correcto en cada idioma (`smoke.spec.ts`).
- [x] El selector lleva a la página equivalente y conserva la query (`i18n.spec.ts`).
- [ ] El inglés pasó la revisión de calidad nativa (03 §9); el español, la de Carlos. **Pendiente de Carlos.**

## 4. Accesibilidad (WCAG 2.2 AA)
- [x] axe sin violaciones `serious` ni `critical` en todas las páginas, es y en, claro y oscuro. M9: el modo oscuro
      entra en `polish.spec.ts` y axe se ejecuta con todas las secciones ya visibles.
- [x] Recorrido solo con teclado de cada página: orden lógico, foco siempre visible, menú con Escape
      (`polish.spec.ts` tabula por las páginas principales; Escape en `frame.spec.ts`).
- [x] Contrastes de la tabla de 00 §3 recalculados con los colores finales: `tests/contrast.test.ts` lee
      `tokens.css` (claro y oscuro). M9 corrigió dos pares: `--on-band-soft` 78 % → 90 % (3,8 → 4,5 sobre verde) y
      `--success` `#15803D` → `#137A3A` (4,3 → 4,6 sobre su fondo).
- [x] Un `h1` por página y jerarquía sin saltos (`smoke.spec.ts`, `polish.spec.ts`).
- [x] `prefers-reduced-motion`: ninguna animación (comprobado emulando la preferencia en Playwright: `document.getAnimations()` vacío y ninguna sección esperando).
- [ ] Lector de pantalla: TalkBack en Android (si Carlos puede) — si no, «no verificado». M9: no verificado.

## 5. SEO
- [x] Título y descripción únicos por página e idioma (`site.spec.ts` recorre el sitemap; M10 dio a cada texto legal su descripción).
- [x] Canonical autorreferente y absoluto en cada página indexable (`i18n.spec.ts`).
- [x] `hreflang` recíproco es/en + `x-default` (`i18n.spec.ts`).
- [x] `sitemap.xml` válido, con todas las páginas públicas en ambos idiomas y sin páginas `noindex` (42 URL).
- [x] `robots.txt` en producción permite el sitio y bloquea las rutas privadas; fuera de producción bloquea todo. `/v/` no se bloquea a propósito: así el buscador lee su `noindex`.
- [x] `noindex` presente en `/v`, `/i`, `/verify-email`, `/reset-password` y errores; ausente en el resto (comprobado con `curl`).
- [ ] Vista previa de WhatsApp correcta en cada página principal y cada idioma (prueba con un enlace real en QA). Las etiquetas y las imágenes están comprobadas (`i18n.spec.ts`); **falta que Carlos pegue un enlace en WhatsApp**.

## 6. Veracidad del contenido (antes de cada PR con textos)
- [x] Cada cifra sale de la API o de un doc **Decidido** (`docs/product/`), no del código de la web. Las únicas fijas: 0 % de comisión (modelo de negocio) y el 911 del viaje compartido (anterior al rediseño).
- [ ] Cada función de seguridad citada se ha visto funcionando en la app de QA: verificación de documentos,
      nombre/foto/moto/placa, PIN, viaje compartido, SOS (911 + contactos), chat, calificación, reportes.
      Verificado en el código de la API y la app (M6); **no visto en un teléfono**: lo confirma Carlos.
- [x] Ninguna cifra de usuarios, viajes, tiempos, seguros, alianzas, premios ni cobertura no confirmada. El «Respondemos en menos de 24 horas» de contacto sale de `response_promise_*` del API (doc 13).
- [x] Ningún testimonio ni persona inventada; ninguna interfaz inventada presentada como captura.
- [x] Ciudades, meses gratis, tramos y métodos de pago dinámicos (`home.spec.ts` y `drivers-safety.spec.ts` sin API).

## 7. Rendimiento (Lighthouse CLI, móvil, sobre `pnpm build && pnpm preview` y sobre QA)
- [x] LCP ≤ 2,5 s, CLS ≤ 0,05, TBT ≤ 150 ms en inicio, motorizados y descargar (QA: 2,1 s, 0, 60–100 ms; ver 00 §9).
- [x] Peso transferido de la primera visita a inicio ≤ 300 KB (196 KB).
- [ ] JS comprimido ≤ línea base + 8 KB. **Excepción a aprobar por Carlos:** inicio pasa de 103 a 127 KB
      transferidos (+24 KB), por las secciones nuevas en trozos pequeños; el peso total y el rendimiento siguen en
      presupuesto.
- [x] Puntuaciones: Rendimiento ≥ 90, Accesibilidad ≥ 95, Buenas prácticas ≥ 95, SEO = 100 (producción).
      QA: 96–97 / 100 / 93 / 66; el 93 es el *beacon* de Cloudflare que bloquea la CSP y el 66 el `robots.txt` de QA.
      Con `NUXT_PUBLIC_APP_ENV=production` en local: SEO 100, buenas prácticas 100.
- [ ] Imágenes en AVIF/WebP con `width`/`height`, lazy bajo el pliegue, hero con prioridad alta. Hoy no hay imágenes de contenido (todo es SVG); aplica cuando entren las capturas.

## 8. Enlaces y funciones
- [x] Rastreo de todos los enlaces internos en es y en: ninguno da 404 (`site.spec.ts`, todas las páginas del sitemap).
- [x] Ningún `href="#"`, botón sin acción ni enlace provisional (búsqueda en `app/`).
- [x] Descargar: el botón entrega el APK de QA y su SHA-256 coincide con el mostrado (`pages.spec.ts` contra QA).
- [x] iPhone (emulado): ve primero el aviso honesto (`pages.spec.ts`).
- [ ] Contacto: un mensaje de prueba llega al admin de QA. El envío está probado con la API simulada; el real
      manda un email de acuse al remitente, así que **lo hace Carlos** con su correo.
- [x] Ayuda: la búsqueda y el filtro devuelven artículos (`pages.spec.ts`).
- [ ] `/v/{token}` con un viaje de prueba se actualiza y caduca al terminar. La lógica no cambió en el rediseño
      (M7 solo tocó plantilla y estilos) y el estado terminal está probado; **falta un viaje real en QA**.
- [ ] `/i/{code}` muestra el código, lo copia y «Ya tengo la app» abre `kuulis://`. El código inválido está
      probado; uno válido necesita un motorizado de QA: **lo prueba Carlos**.
- [ ] Emails de verificación y reset de QA funcionan de punta a punta (es y en). **Lo prueba Carlos** (llegan a su correo).
- [x] La app sigue abriendo los enlaces de compartir e invitación (deep links sin cambios: las rutas `/v` y `/i` siguen en español y sin prefijo, `i18n.spec.ts`).

## 9. Regresión y producción
- [x] CI `web` en verde (lint, tipos, tests, build).
- [x] e2e completo en verde (94 pruebas: 92 pasan y 2 se saltan por ser variantes sin API; local y contra QA).
- [x] Sin errores en la consola del navegador en ninguna página (salvo el *beacon* de Cloudflare, ajeno a la web).
- [x] Cabeceras de seguridad (CSP, HSTS, X-Frame-Options…) iguales a las actuales: el rediseño no tocó su
      configuración. QA envía HSTS dos veces (la web y el proxy), como antes.
- [x] El contenedor Docker arranca y su healthcheck pasa (Coolify QA desplegó cada milestone).
- [ ] Revisión de Carlos en QA en su propio teléfono Android. **Pendiente.**
- [x] Docs actualizados: `docs/produccion/08-web-publica.md`, `web/README.md`, README de este directorio (M10).
- [ ] La salida a producción (`main`) solo con el OK explícito de Carlos y con el dominio de producción decidido. **Pendiente de Carlos.**

## 10. Lo que este proceso no puede verificar por sí solo
Safari en iPhone real, Android de gama baja real, lectores de pantalla de escritorio, percepción de marca por
usuarios reales. Se dejan anotados como «no verificado» o se piden a Carlos.
