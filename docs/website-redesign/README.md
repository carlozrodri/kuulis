# Rediseño de la web pública

Plan del rediseño completo de la web pública de Kuulis (`web/`). **Estado: plan aprobado (2026-10-17), nada implementado todavía.**
Carlos aprobó el plan completo el 2026-10-17 («apruebo todo»). Cada milestone se ejecuta solo cuando él lo pide.

| Doc | Qué contiene |
| --- | --- |
| [00 · Auditoría y estado actual](00-audit-and-current-state.md) | Arquitectura, páginas, colores, assets, SEO, i18n, rendimiento medido y debilidades |
| [01 · Estrategia de marca](01-brand-strategy-and-positioning.md) | Público, posicionamiento, personalidad, jerarquía de mensajes, diferenciales reales |
| [02 · Dirección creativa](02-creative-direction-and-visual-system.md) | Concepto «El punto», tipografía, color, composición, imágenes, iconos, movimiento |
| [03 · Arquitectura de información y contenido](03-information-architecture-and-content.md) | Mapa del sitio, orden de secciones, navegación, footer y textos reales en español e inglés |
| [04 · UX e interacción](04-ux-and-interaction-specification.md) | Navegación, estados, animaciones, accesibilidad y recorridos |
| [05 · Assets visuales e IA](05-visual-assets-and-ai-production.md) | Inventario de assets, qué se reutiliza, qué se crea, briefs y recomendación sobre suscripciones |
| [06 · Plan técnico](06-technical-implementation-plan.md) | Arquitectura, componentes, cambios por archivo, i18n, SEO, rendimiento y tests |
| [07 · Hoja de ruta](07-phased-execution-roadmap.md) | Milestones pequeños con alcance, criterios de aceptación y validación |
| [08 · QA y lanzamiento](08-quality-assurance-and-launch-checklist.md) | Checklist final de calidad, accesibilidad, SEO, rendimiento y producción |

## Límites del proyecto
- **Se puede cambiar:** solo `web/` (excepto `web/app/pages/v/`, `verify-email`, `reset-password` e `i/`, que solo
  reciben los estilos nuevos sin cambiar su lógica) y esta carpeta de docs.
- **No se toca:** `api/`, `admin/`, `mobile/`, `infra/`, `scripts/`, `loadtest/`, Coolify, CI (salvo que un
  milestone aprobado lo pida de forma explícita), base de datos.

## Convenciones
- Igual que `docs/produccion/`: cada decisión se marca como **Decidido** (lo dijo Carlos) o **Supuesto**
  (propuesta a validar). Las preguntas abiertas están abajo.
- Los milestones se entregan uno por uno, como PR a `qa`. Nada pasa a `main` sin el OK de Carlos.

## Decidido (2026-10-17)
Carlos respondió «apruebo todo»: cuenta la opción recomendada de cada pregunta.
1. **URLs en inglés** (`/en`, `/en/drivers`…) para que el inglés se pueda indexar y compartir. Recomendado: sí.
2. **Fotografía:** (a) lanzar solo con capturas reales y gráficos de marca, y decidir fotos después; (b) sesión
   con fotógrafo en Caracas; (c) imágenes con IA sin personas. Recomendado: (a). No hace falta comprar nada ahora.
3. **Tipografía:** mantener solo Plus Jakarta Sans (la de la app). Recomendado: sí.
4. **Capturas de la app:** las sacas tú en tu Android con el build de QA y yo preparo los datos y las limpio, o las
   saco yo del build web. Recomendado: tu Android (es la app real).
5. **Pruebas automáticas:** añadir `@playwright/test` y `@axe-core/playwright` como dependencias de desarrollo
   (no pesan en la web). Recomendado: sí.
6. **Titular del hero:** A «En moto por Caracas. Precio claro, y punto.», B «Pide tu moto. Mira el precio. Y punto.»,
   C «Tu moto, sin regateo.» Recomendado: A.
7. **Redes sociales:** ¿Kuulis tiene cuentas? Si no, el footer va sin iconos. Recomendado: sin iconos hasta que existan.

## Avance
| Milestone | Estado |
| --- | --- |
| Plan (este directorio) | Aprobado 2026-10-17 |
| M0 · Línea base | Siguiente |
