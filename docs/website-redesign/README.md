# Rediseño de la web pública

Plan del rediseño completo de la web pública de Kuulis (`web/`). **Estado: plan aprobado (2026-10-17), en ejecución por milestones (ver Avance).**
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
  (propuesta a validar). Las decisiones de Carlos están abajo.
- Los milestones se entregan uno por uno, como PR a `qa`. Nada pasa a `main` sin el OK de Carlos.

## Decidido (2026-10-17)
Carlos respondió «apruebo todo»: vale la opción recomendada de cada pregunta.
1. **URLs en inglés:** sí (`/en`, `/en/drivers`, `/en/safety`…), para que el inglés se indexe y se comparta.
2. **Fotografía:** se lanza solo con capturas reales y gráficos de marca; las fotos se deciden después. No se
   compra ninguna suscripción de IA por ahora.
3. **Tipografía:** solo Plus Jakarta Sans (la de la app).
4. **Capturas de la app:** las saca Carlos en su Android con el build de QA; Claude prepara los datos y las limpia.
5. **Pruebas automáticas:** se añaden `@playwright/test` y `@axe-core/playwright` como dependencias de desarrollo.
6. **Titular del hero:** «En moto por Caracas. Precio claro, y punto.» / «Across Caracas by motorbike. A clear
   price, full stop.»
7. **Redes sociales:** el footer va sin iconos hasta que existan cuentas.

## Avance
| Milestone | Estado |
| --- | --- |
| Plan (este directorio) | Aprobado 2026-10-17 |
| M0 · Línea base | Hecho 2026-10-17 (ver 00 §9) |
| M1 · Fundamentos | Hecho 2026-10-17 (ver 06 §2) |
| M2 · Marco | Hecho 2026-10-17 (ver 07 M2) |
| M5 · Idiomas en URL y SEO por idioma | Hecho 2026-10-17 (ver 07 M5) |
| M3 · Inicio: hero y precio claro | Primer paso hecho 2026-10-17; faltan las capturas de la app (ver 07 M3) |
| M4 · Inicio: resto de secciones | Hecho 2026-10-17 (ver 07 M4) |
| M6 · Motorizados y Seguridad | Hecho 2026-10-17 (ver 07 M6) |
| M7 · Descargar y páginas secundarias | Hecho 2026-10-17 (ver 07 M7) |
| M8 · Producción e integración de assets | En parte 2026-10-17: imágenes para compartir; faltan capturas de la app (ver 07 M8) |
| M9 · Movimiento, responsive fino y accesibilidad | Hecho 2026-10-17; TalkBack no verificado (ver 07 M9) |
| M10 · Verificación final y salida | Verificado 2026-10-17; faltan las pruebas de Carlos y su OK para `main` (ver 08) |
