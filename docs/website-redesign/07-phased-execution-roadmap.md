# 07 · Hoja de ruta por milestones

Reglas para todos los milestones:
- Uno a la vez, solo cuando Carlos lo pide. Cada uno es una rama + PR a `qa`; no se fusiona sin su OK.
- Antes de empezar: leer los docs relevantes, confirmar el alcance en el hilo, revisar el estado de los archivos.
- Validación común (abreviada como **V**): `cd web && pnpm lint && pnpm typecheck && pnpm test && pnpm build`.
- Al terminar: informe con archivos cambiados, decisiones, resultados de validación, capturas y pendientes.
- Si algo obliga a cambiar el plan, se actualiza el doc afectado en el mismo PR y se dice en el informe.
- Rollback general: revertir el PR en `qa` (Coolify redepliega solo). Ningún milestone toca datos ni la API.

---

## M0 · Línea base y capturas de referencia
- **Objetivo:** medir el sitio actual para poder comparar, y dejar listas las herramientas de verificación.
- **Alcance:** Lighthouse (móvil y escritorio) de las 5 páginas públicas en QA; capturas a 7 anchos en es/en;
  inventario de enlaces. Si se aprueba la pregunta 5: añadir `@playwright/test` y `@axe-core/playwright` como
  dependencias de desarrollo y el primer test e2e de humo (sin cambiar la web).
- **Archivos:** `docs/website-redesign/00-…` (sección de línea base), opcionalmente `web/package.json`,
  `web/pnpm-lock.yaml`, `web/playwright.config.ts`, `web/tests/e2e/smoke.spec.ts`.
- **Prerrequisitos:** aprobación del plan.
- **Pasos:** ejecutar Lighthouse con `npx`; script de capturas; registrar resultados; (opcional) instalar dev deps.
- **Aceptación:** números de línea base en 00; el test de humo pasa contra `pnpm preview`.
- **Validación:** V + `pnpm exec playwright test` (si se aprueba).
- **Depende de:** nada.
- **Riesgos:** ninguno para usuarios (no cambia la web).

## M1 · Fundamentos: tokens, tipografía y capas CSS
- **Objetivo:** el sistema de 02/06 en código, sin rediseñar páginas todavía.
- **Alcance:** `tokens.css`, `base.css`, `layout.css`, `components.css`; anillo de foco de dos tonos; `.sr-only`
  correcto; botones según fondo; escala tipográfica; precarga de fuente y cara de respaldo; alias `--hero*`.
- **Archivos:** `web/app/assets/css/*`, `web/nuxt.config.ts` (solo `css` y `link` de precarga).
- **Pasos:** crear capas; migrar `main.css`; comprobar que las páginas actuales se ven igual o mejor.
- **Aceptación:** ninguna página actual se rompe (capturas antes/después en 7 anchos); foco visible en todos los
  fondos; contrastes de 00 §3 sin fallos; CLS de la fuente ≤ línea base.
- **Validación:** V + capturas comparadas + axe.
- **Depende de:** M0.
- **Riesgos:** regresiones visuales en páginas secundarias → mitigado con capturas antes/después de todas las rutas.

## M2 · Marco: cabecera, menú móvil, selector de idioma y footer
- **Objetivo:** el nuevo marco de todas las páginas.
- **Alcance:** `SiteHeader`, `MobileMenu`, `LanguageSwitch` (todavía con el comportamiento actual de cookie si M5
  no está hecho), `SiteFooter`, `AvilaRidge`, `KuulisWordmark` con tonos, favicon con trazos (A9).
- **Archivos:** `layouts/default.vue`, `components/Site*.vue`, `components/brand/AvilaRidge.vue`,
  `public/favicon.svg`, `public/icon-192.png`, `i18n/locales/*.json` (claves de nav y footer).
- **Aceptación:** menú móvil con foco atrapado, Escape, `inert`, cierre al navegar; todos los enlaces del footer
  existen; sin desbordamiento a 320 px; cabecera transparente → sólida sin escuchar scroll.
- **Validación:** V + e2e de navegación por teclado + axe + capturas.
- **Depende de:** M1.
- **Riesgos:** la cabecera transparente necesita que cada página tenga un primer bloque conocido → las páginas no
  migradas usan la cabecera sólida por defecto.
- **Hecho (2026-10-17):** cabecera sólida con dos enlaces (Motorizados, Ayuda), selector de idioma y «Descargar la
  app»; menú móvil como panel propio dentro de `SiteHeader` (no hizo falta un `MobileMenu` aparte); el selector
  muestra el nombre del otro idioma («English»/«Español»), lo que quita la excepción de axe
  `label-content-name-mismatch`; footer con la silueta del Ávila sacada de datos de elevación SRTM (Open-Meteo);
  favicon e `icon-192.png` con la «k» y el punto amarillo. Pruebas nuevas en `web/tests/e2e/frame.spec.ts`.
  Queda para después: la cabecera transparente sobre el hero (M3, necesita el hero nuevo) y el enlace «Seguridad»
  (M6, cuando exista la página). Ojo: los componentes de `components/brand/` se usan con el prefijo `Brand`
  (`<BrandAvilaRidge>`), por la convención de nombres de Nuxt.

## M3 · Inicio: hero y precio claro
- **Objetivo:** la primera impresión.
- **Alcance:** `HomeHero` (titular elegido, CTA, `RouteLine` animada, `Headline` con punto, captura en
  `PhoneFrame`), `HomePrice` (filas + `PaymentChips` + captura de cotización). Usa capturas provisionales
  marcadas `TODO-captura` si A1 aún no existe; **no se fusiona a `qa` con provisionales**.
- **Archivos:** `pages/index.vue`, `components/home/HomeHero.vue`, `HomePrice.vue`, `components/brand/*`,
  `components/PhoneFrame.vue`, `PaymentChips.vue`, `Icon.vue`, `composables/useReveal.ts`, `i18n/locales/*`.
- **Prerrequisitos:** titular elegido (pregunta 6); capturas A1 (o aceptar M3 en dos pasos).
- **Aceptación:** el titular, el lead y el CTA caben en 360×640; LCP ≤ 2,5 s en Lighthouse móvil; animación
  desactivada con movimiento reducido; sin JS todo se ve; textos es/en revisados.
- **Validación:** V + Lighthouse + e2e responsive + axe.
- **Depende de:** M2.
- **Riesgos:** peso de la captura del hero → presupuesto de 45 KB.
- **Hecho, primer paso (2026-10-17):** como no hay capturas A1 todavía y el plan prohíbe fusionar provisionales,
  el M3 va en dos pasos. Ahora: `HomeHero` en campo verde plano con el titular aprobado (`BrandHeadline`: el punto
  final es amarillo sobre verde o tinta y verde sobre claro), lead, botones, nota «Gratis. Por ahora, solo para
  Android.», `BrandRouteLine` que se dibuja hasta el punto amarillo (CSS, sin JS, quieta con movimiento reducido) y
  el Ávila; `HomePrice` en filas con `PaymentChips` de `/public/site`. Se quitó la tarjeta inventada del hero
  («Luis está en camino», $2.40) y la sección de tres tarjetas de pasajeros (el punto de seguridad vuelve en M4).
  La cabecera lleva el verde del hero (sólido, no transparente, para que sin JS se lea en todo el sitio) y pasa
  a clara cuando `#hero-end` queda debajo. Lighthouse móvil local: rendimiento 92–96, accesibilidad 100, LCP
  2,2–2,4 s, CLS 0, 222 KB. Segundo paso: la captura de cotización en `PhoneFrame` en el hero y en precio claro,
  cuando Carlos pase las capturas (05 A1).

## M4 · Inicio: resto de secciones
- **Objetivo:** completar la narrativa de la página de inicio.
- **Alcance:** `HomeHow`, `HomeDrivers` (0 % + `FeeTable` + `{max}` dinámico), `HomeSafety` (`PinDigits`),
  `HomeFaq`, `HomeDownload` (final de la ruta).
- **Archivos:** `components/home/*.vue`, `components/FeeTable.vue`, `components/brand/PinDigits.vue`,
  `components/FeatureRows.vue`, `i18n/locales/*`.
- **Aceptación:** cada dato de negocio sale de la API y tiene estado sin datos (04 §8); FAQ con `<details>`;
  ningún enlace a `/seguridad` hasta que exista (o se entrega en el mismo PR que M6).
- **Validación:** V + test unitario de `{max}` y estados sin datos (API simulada) + e2e + axe + Lighthouse.
- **Depende de:** M3.
- **Riesgos:** texto de seguridad que prometa algo no verificado → checklist de 08 §6 antes del PR.

## M5 · Idiomas en URL y SEO por idioma
- **Objetivo:** inglés indexable con URLs propias (si se aprueba la pregunta 1).
- **Alcance:** `prefix_except_default`, rutas personalizadas, `localePath` en todos los enlaces, selector con
  `switchLocalePath`, middleware de cookie para páginas de utilidad, `useSeo` con canonical/hreflang/og:locale,
  sitemap con alternates, `robots.txt` con `/en/i/`, test de paridad de claves.
- **Archivos:** `nuxt.config.ts`, `composables/useSeo.ts`, `middleware/utility-locale.ts`,
  `server/routes/sitemap.xml.ts`, `server/routes/robots.txt.ts`, todas las páginas (solo enlaces y `useSeo`),
  `tests/i18n.test.ts`.
- **Aceptación:** `/` y `/en` sirven cada idioma sin cookie; cada página tiene canonical propio y `hreflang`
  recíproco; `/verify-email` con cookie `en` termina en `/en/verify-email` con el token intacto; sitemap válido;
  ningún `noindex` accidental; enlaces de los emails en QA funcionan de punta a punta.
- **Validación:** V + e2e de idioma (con y sin cookie, con `Accept-Language` en/es) + validación de sitemap +
  prueba manual de un email de verificación y uno de reset en QA.
- **Depende de:** M2 (puede ir antes de M3/M4 si conviene).
- **Riesgos:** romper enlaces de emails o de la app → el middleware y los tests cubren las 4 rutas de utilidad;
  rollback = revertir el PR.
- **Hecho (2026-10-17):** español en `/`, inglés en `/en` con `/en/drivers`, `/en/download`, `/en/help`,
  `/en/contact` (la tabla vive en `web/i18n/pages.ts` y la usan el router y el sitemap). Solo la portada redirige:
  a la última elección (cookie) o, en la primera visita, al idioma del navegador. El selector es un enlace a la
  misma página en el otro idioma, con la query. Los enlaces sin prefijo de emails y app (`/verify-email`,
  `/reset-password`, `/v/…`, `/i/…`) van a `/en/…` si la cookie es `en` o, sin cookie, si el navegador prefiere
  inglés (como hacía la web antes); el token no se toca. Canonical, `hreflang` (es-VE, en, x-default) y
  `og:locale`/`og:url` salen de `composables/useLocaleSeo.ts` con `NUXT_PUBLIC_SITE_URL`, en vez de
  `useLocaleHead`, para no necesitar una variable de entorno nueva en Coolify; las páginas privadas no los llevan.
  Sitemap con alternates y artículos de ayuda por idioma; `robots.txt` bloquea también las variantes `/en`.
  Pruebas: `tests/i18n.test.ts` (paridad de claves, rutas) y `tests/e2e/i18n.spec.ts`. Falta la prueba manual de
  un email de verificación y uno de reset en QA, después de fusionar.

## M6 · Motorizados y Seguridad
- **Objetivo:** las dos páginas de público específico.
- **Alcance:** `/motorizados` reescrita (03 §6) con `FeeExample`; `/seguridad` nueva (03 §7); enlaces desde
  inicio, cabecera y footer; OG por página.
- **Archivos:** `pages/motorizados.vue`, `pages/seguridad.vue`, `components/FeeExample.vue`, `i18n/locales/*`,
  `server/routes/sitemap.xml.ts` (añadir `/seguridad`).
- **Prerrequisitos:** verificación en la app de cada función de seguridad citada (08 §6).
- **Aceptación:** ejemplo de cuota correcto con los tramos de la API (test); ninguna afirmación sin respaldo.
- **Validación:** V + test de `FeeExample` + e2e + axe + Lighthouse.
- **Depende de:** M4 (y M5 si ya está, para las URLs `/en/drivers` y `/en/safety`).
- **Riesgos:** funciones de seguridad que cambian de config (p. ej. `sos_team_alert`) → el texto no promete un
  equipo de respuesta.

## M7 · Descargar y páginas secundarias
- **Objetivo:** coherencia en todo el sitio.
- **Alcance:** `/descargar` (pasos ilustrados con A2, aviso de seguridad destacado, iPhone primero si es
  iPhone); estilos nuevos en ayuda, contacto, legal, invitación, viaje compartido, verificar, reset y error;
  revisión del texto `invite.freeMonth`; eliminar alias `--hero*`.
- **Archivos:** las páginas citadas (solo `<template>` y `<style>`, salvo `useSeo`), `i18n/locales/*`.
- **Aceptación:** la lógica de cada página intacta (formulario de contacto envía, búsqueda de ayuda filtra, APK
  descarga con la huella correcta, `/v` actualiza, `/i` copia el código); sin valores de color sueltos fuera de
  `tokens.css`.
- **Validación:** V + e2e de cada flujo funcional contra QA o API simulada + axe.
- **Depende de:** M2.
- **Riesgos:** regresión en flujos con token → probar con tokens reales de QA.

## M8 · Producción e integración de assets
- **Objetivo:** sustituir todo lo provisional por assets finales.
- **Alcance:** capturas A1 definitivas en claro y oscuro, A2, OG por página e idioma (A8), y P1/P2 solo si se
  aprueban. `CREDITS.md` de imágenes.
- **Archivos:** `web/public/images/**`, componentes que las referencian.
- **Prerrequisitos:** decisión sobre fotografía/IA (pregunta 2) y, si aplica, compra de la suscripción por Carlos.
- **Aceptación:** presupuestos de peso de 05 §5; `alt` en los dos idiomas; ninguna captura con datos personales.
- **Validación:** V + Lighthouse + revisión visual de capturas.
- **Depende de:** M3, M4, M6, M7.
- **Riesgos:** retrasos en la producción de capturas → M3/M4 pueden ir con capturas reales provisionales de QA.

## M9 · Movimiento, responsive fino y accesibilidad
- **Objetivo:** pulido.
- **Alcance:** ajustar tiempos de animación; revisar cada página en los 7 anchos y en modo oscuro; cortes de
  línea en titulares (es/en); zoom 200 %; TalkBack si Carlos puede probarlo.
- **Archivos:** estilos de componentes y páginas.
- **Aceptación:** checklist de 08 §2–§4 completa.
- **Validación:** V + e2e completo + axe + Lighthouse.
- **Depende de:** M8.

## M10 · Verificación final y salida
- **Objetivo:** listo para producción.
- **Alcance:** checklist completo de 08; medición final frente a la línea base; actualización de
  `docs/produccion/08-web-publica.md` y de este README.
- **Aceptación:** todos los puntos de 08 en verde o con excepción aprobada por Carlos.
- **Validación:** todo lo anterior sobre QA.
- **Depende de:** M9.
- **Riesgos:** la producción de la web aún no tiene dominio → la salida a `main` queda sujeta a esa decisión de
  Carlos, fuera de este proyecto.

## Orden recomendado
M0 → M1 → M2 → M5 → M3 → M4 → M6 → M7 → M8 → M9 → M10.
M5 va pronto porque cambia cómo se escriben todos los enlaces: hacerlo antes de reescribir las páginas evita
tocarlas dos veces. Si Carlos dice que no a las URLs en inglés, M5 se reduce a canonical + og:locale y se mueve al
final.
