# Marketing y contenido en redes

Plan para crear contenido con potencial viral (videos cortos, imágenes y carruseles) para TikTok, Instagram
Reels y YouTube Shorts, con un equipo de agentes que generen, revisen, publiquen, midan y recomienden mejoras.
**Estado: plan aprobado (2026-10-18), sin decisiones pendientes.** No se ha suscrito ni pagado nada.

| Doc | Qué contiene |
| --- | --- |
| [01 · Estrategia y posicionamiento](01-estrategia-y-posicionamiento.md) | Objetivo, métrica norte, públicos, lo que se puede y no se puede decir, fases |
| [02 · Plataformas y algoritmos](02-plataformas-y-algoritmos.md) | Cómo reparte cada red, formatos, música, APIs, WhatsApp y Facebook, horarios |
| [03 · Pilares y formatos](03-pilares-y-formatos.md) | 6 pilares, 9 formatos, fórmulas de gancho, estructura de guion, 20 ideas iniciales, series |
| [04 · Calendario y flujo diario](04-calendario-y-flujo-diario.md) | Cadencia por fase, semana tipo, flujo diario con aprobación, quién publica |
| [05 · Personaje de marca](05-personaje-de-marca.md) | Tres conceptos, recomendación, biblia del personaje, cómo se crea en Higgsfield |
| [06 · Herramientas de IA y costos](06-herramientas-ia-y-costos.md) | Comparativa honesta (Higgsfield, Buzzy, Remotion, Midjourney, Sora, Runway, DALL-E y más) y qué suscribir primero |
| [07 · Evaluación de agency-agents](07-evaluacion-agency-agents.md) | Qué es, qué sirve, qué no, y veredicto |
| [08 · Arquitectura de agentes](08-arquitectura-de-agentes.md) | Los 8 agentes, dónde viven, cómo se ejecutan, cómo aprenden, qué decide una persona |
| [09 · Registro, datos y medición](09-registro-datos-y-medicion.md) | Modelo de datos, métricas por API, atribución hasta el registro, panel e informe semanal |
| [10 · Riesgos y cumplimiento](10-riesgos-y-cumplimiento.md) | Disclosure de IA, derechos, políticas de plataformas, contexto venezolano, crisis |
| [11 · Hoja de ruta](11-hoja-de-ruta.md) | Pasos MK0 a MK10, quién hace cada uno y qué cuesta |

## En una frase
Un **personaje de IA declarado + escenas de Caracas hechas con IA + pantallas reales de la app + plantillas de
marca automáticas**, probado a diario con datos, con agentes propios de Kuulis que aprenden de cada publicación y una persona que
aprueba todo lo que sale.

## Convenciones
- Igual que `docs/produccion/` y `docs/website-redesign/`: lo que dijo Carlos es **Decidido**; el resto es
  **Supuesto** hasta que lo confirme.
- Los pasos se ejecutan uno a uno, cuando Carlos los pide. Pagos y cuentas, siempre con su OK explícito.
- Los precios de herramientas son aproximados al 2026-10-18 y se confirman el día de pagar.

## Decidido
- Plan primero, en `.md`, paso a paso (Carlos, 2026-10-18).
- Redes objetivo: TikTok, Instagram y YouTube Shorts; imágenes, videos y shorts.
- Agentes que trabajen la generación de contenido y el marketing, midan y recomienden mejoras; todo queda
  registrado para monitorear qué rinde.
- **Herramientas (2026-10-18):** se suscriben **Higgsfield Plus** (€59/mes, personaje) y **Buzzy Basic**
  ($19/mes, escenas e imágenes) para probar la calidad; al final del mes 1 se decide con la prueba de
  [06 §3](06-herramientas-ia-y-costos.md#3-qué-suscribir-y-cuándo). El pago lo hace Carlos.
- **agency-agents descartado por completo** (2026-10-18). Agentes propios de Kuulis.
- **Sin contenido real grabado por ahora** (2026-10-18): todo sale de IA, plantillas y pantallas de la app.
  Las entrevistas en la calle y las historias de motorizados quedan en pausa (no se simulan con IA).

- **Respuestas del 2026-10-18 (todas):**
  1. Personaje: **«Kuu»**, presentadora caraqueña declarada como IA (concepto A de [05](05-personaje-de-marca.md)).
  2. **Las cuentas aún no existen**; se crean en MK2.
  3. **Publica una persona en Caracas con un teléfono real**; solo recibe lo que tiene que publicar: archivo,
     título, texto, hashtags y hora (paquete en [04 §4](04-calendario-y-flujo-diario.md#4-quién-publica)).
  4. **Carlos aprueba cada día** el paquete en el hilo de marketing.
  5. **Pauta $0 las primeras 4 semanas**, luego solo ganadores con $3–5 al día.
  6. **Se arranca antes del lanzamiento** (captar motorizados).
  7. **Carlos se suscribe a Higgsfield y Buzzy cuando todo esté montado** y conecta las cuentas para que Claude
     genere por MCP (las dos tienen MCP oficial) (ver [08 §4](08-arquitectura-de-agentes.md#4-cómo-se-ejecutan)). **Todo el contenido
     generado se guarda en S3**: MinIO del homelab, o Cloudflare R2 si no sirve
     ([09 §1.1](09-registro-datos-y-medicion.md#11-almacenamiento-de-archivos-decidido-2026-10-18)).

## Siguiente paso
**MK4 · Estudio de plantillas** (Remotion) cuando Carlos apruebe MK1. MK1 entregó hechos permitidos, tono, biblia de «Kuu», playbooks de ganchos y los 5 guiones de
la prueba Higgsfield vs Buzzy), sin costo, cuando Carlos lo pida. Orden completo en [11](11-hoja-de-ruta.md).

## Avance
| Paso | Estado |
| --- | --- |
| MK0 · Plan | Aprobado y fusionado 2026-10-18 (#76) |
| MK1 · Marca para redes | En revisión 2026-10-18: [`marketing/`](../../marketing/README.md) con hechos, tono, identidad visual, biblia de Kuu, playbooks y los 5 guiones de la prueba |
