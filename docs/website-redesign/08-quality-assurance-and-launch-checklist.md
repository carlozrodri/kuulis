# 08 · QA y checklist de lanzamiento

Cada punto se marca solo cuando se ha comprobado de verdad, con la herramienta indicada. Si algo no se pudo
verificar (p. ej. Safari real o un lector de pantalla), se escribe «no verificado» y por qué.

## 1. Calidad visual (revisión con capturas de Playwright en 7 anchos, claro y oscuro)
- [ ] La primera pantalla dice qué es Kuulis y ofrece descargar, a 360×640 y a 1440×900.
- [ ] Kuulis se reconoce sin el logotipo (verde en campos planos, titulares con el punto, la ruta).
- [ ] No hay grillas de tarjetas idénticas, degradados decorativos, blur ni «eyebrows» de plantilla.
- [ ] El amarillo nunca aparece como texto/icono sobre fondo claro.
- [ ] Titulares sin viudas ni cortes feos en es y en (revisión manual en los 7 anchos).
- [ ] Capturas de la app reales, nítidas, sin datos personales ni avisos de desarrollo.
- [ ] Modo oscuro revisado en todas las páginas.
- [ ] Cada sección cumple el «trabajo» que le asigna 03.

## 2. Responsive
- [ ] Sin desbordamiento horizontal a 320, 360, 414, 768, 1024, 1440, 1920 px (`scrollWidth <= innerWidth`, e2e).
- [ ] El menú móvil es un panel propio, no la nav de escritorio comprimida.
- [ ] Zoom al 200 % usable (WCAG 1.4.10).
- [ ] Imágenes con recortes dirigidos (no recortes automáticos que corten lo importante).
- [ ] Objetivos táctiles ≥ 44 px en móvil.

## 3. Idiomas
- [ ] Test de paridad de claves `es.json` / `en.json` en verde.
- [ ] Ningún texto en español en la versión inglesa ni al revés (recorrido e2e buscando una lista de palabras
      testigo, más revisión manual).
- [ ] Títulos, descripciones, OG, `alt` y `aria-label` traducidos.
- [ ] `<html lang>` correcto en cada idioma.
- [ ] El selector lleva a la página equivalente y conserva la query.
- [ ] El inglés pasó la revisión de calidad nativa (03 §9); el español, la de Carlos.

## 4. Accesibilidad (WCAG 2.2 AA)
- [ ] axe sin violaciones `serious` ni `critical` en todas las páginas, es y en, claro y oscuro.
- [ ] Recorrido solo con teclado de cada página: orden lógico, foco siempre visible, menú con Escape.
- [ ] Contrastes de la tabla de 00 §3 recalculados con los colores finales.
- [ ] Un `h1` por página y jerarquía sin saltos.
- [ ] `prefers-reduced-motion`: ninguna animación (comprobado emulando la preferencia en Playwright).
- [ ] Lector de pantalla: TalkBack en Android (si Carlos puede) — si no, «no verificado».

## 5. SEO
- [ ] Título y descripción únicos por página e idioma.
- [ ] Canonical autorreferente y absoluto en cada página indexable.
- [ ] `hreflang` recíproco es/en + `x-default`.
- [ ] `sitemap.xml` válido, con todas las páginas públicas en ambos idiomas y sin páginas `noindex`.
- [ ] `robots.txt` en producción permite el sitio y bloquea las rutas privadas; fuera de producción bloquea todo.
- [ ] `noindex` presente en `/v`, `/i`, `/verify-email`, `/reset-password` y errores; ausente en el resto.
- [ ] Vista previa de WhatsApp correcta en cada página principal y cada idioma (prueba con un enlace real en QA).

## 6. Veracidad del contenido (antes de cada PR con textos)
- [ ] Cada cifra sale de la API o de un doc **Decidido** (`docs/product/`), no del código de la web.
- [ ] Cada función de seguridad citada se ha visto funcionando en la app de QA: verificación de documentos,
      nombre/foto/moto/placa, PIN, viaje compartido, SOS (911 + contactos), chat, calificación, reportes.
- [ ] Ninguna cifra de usuarios, viajes, tiempos, seguros, alianzas, premios ni cobertura no confirmada.
- [ ] Ningún testimonio ni persona inventada; ninguna interfaz inventada presentada como captura.
- [ ] Ciudades, meses gratis, tramos y métodos de pago dinámicos.

## 7. Rendimiento (Lighthouse CLI, móvil, sobre `pnpm build && pnpm preview` y sobre QA)
- [ ] LCP ≤ 2,5 s, CLS ≤ 0,05, TBT ≤ 150 ms en inicio, motorizados y descargar.
- [ ] Peso transferido de la primera visita a inicio ≤ 300 KB.
- [ ] JS comprimido ≤ línea base + 8 KB.
- [ ] Puntuaciones: Rendimiento ≥ 90, Accesibilidad ≥ 95, Buenas prácticas ≥ 95, SEO = 100 (producción).
- [ ] Imágenes en AVIF/WebP con `width`/`height`, lazy bajo el pliegue, hero con prioridad alta.

## 8. Enlaces y funciones
- [ ] Rastreo de todos los enlaces internos en es y en: ninguno da 404 (e2e).
- [ ] Ningún `href="#"`, botón sin acción ni enlace provisional.
- [ ] Descargar: el botón entrega el APK de QA y su SHA-256 coincide con el mostrado.
- [ ] iPhone (emulado): ve primero el aviso honesto.
- [ ] Contacto: un mensaje de prueba llega al admin de QA.
- [ ] Ayuda: la búsqueda y el filtro devuelven artículos.
- [ ] `/v/{token}` con un viaje de prueba se actualiza y caduca al terminar.
- [ ] `/i/{code}` muestra el código, lo copia y «Ya tengo la app» abre `kuulis://`.
- [ ] Emails de verificación y reset de QA funcionan de punta a punta (es y en).
- [ ] La app sigue abriendo los enlaces de compartir e invitación (deep links sin cambios).

## 9. Regresión y producción
- [ ] CI `web` en verde (lint, tipos, tests, build).
- [ ] e2e completo en verde.
- [ ] Sin errores en la consola del navegador en ninguna página.
- [ ] Cabeceras de seguridad (CSP, HSTS, X-Frame-Options…) iguales a las actuales (comparación con `curl -I`).
- [ ] El contenedor Docker arranca y su healthcheck pasa (Coolify QA en verde).
- [ ] Revisión de Carlos en QA en su propio teléfono Android.
- [ ] Docs actualizados: `docs/produccion/08-web-publica.md`, `web/README.md`, README de este directorio.
- [ ] La salida a producción (`main`) solo con el OK explícito de Carlos y con el dominio de producción decidido.

## 10. Lo que este proceso no puede verificar por sí solo
Safari en iPhone real, Android de gama baja real, lectores de pantalla de escritorio, percepción de marca por
usuarios reales. Se dejan anotados como «no verificado» o se piden a Carlos.
