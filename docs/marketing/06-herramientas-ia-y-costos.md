# 06 · Herramientas de IA: comparativa honesta y qué suscribir primero

Revisado el **2026-10-18**. Los precios de estas herramientas cambian casi cada mes y varias fuentes se
contradicen; las cifras son **aproximadas** y se confirman en la página oficial el día de pagar.
No se ha suscrito ni pagado nada.

## 1. Resumen
| Herramienta | Qué hace bien | Estado hoy | Precio aproximado | Para Kuulis |
| --- | --- | --- | --- | --- |
| **Higgsfield** (incl. AI Influencer Studio) | Personaje consistente, video con movimiento de cámara, muchos modelos de video en un solo sitio (agregador) | Activo; AI Influencer Studio renovado el 2026-10-03 | Starter ~$15–19/mes · Plus ~$49–59/mes (~$39–47 anual) · Ultra ~$129/mes. Créditos mensuales que **vencen a los 30 días** | **Suscribir primero** (Plus, mensual) |
| **Remotion** | Video programado en React: plantillas de marca, subtítulos, datos animados, carruseles, todo automatizable | Activo, código abierto con licencia propia | **Gratis** para empresas de hasta 3 personas; luego $25/mes por asiento o $0,01 por render (mínimo $100/mes) | **Usar desde el día 1** (gratis) |
| **Midjourney** | La mejor estética de imagen fija (portadas, fondos, conceptos) | Activo, V8.x | Basic $10 · Standard $30 · Pro $60/mes | Opcional en F2; no hace falta para arrancar |
| **Runway** | Edición de video con IA, Gen-4.5, herramientas de postproducción | Activo | Standard ~$12–15 · Pro ~$28–35 · Max ~$95/mes; ~12 créditos por segundo de Gen-4.5 | No ahora: Higgsfield cubre lo mismo para este uso |
| **Sora (OpenAI)** | Fue de los mejores generadores de video | **Descontinuado:** la app cerró en abril de 2026 y la API el 24-09-2026 | — | **Descartado** |
| **DALL-E (OpenAI)** | Imagen | **Retirado** de la API en mayo de 2026; lo reemplaza GPT Image | GPT Image: ~$0,01–0,17 por imagen según calidad | Útil vía API para piezas automáticas (carruseles, fondos) |
| **Buzzy (buzzy.now)** | Lienzo «agéntico» para crear video con IA | Producto nuevo; **sin tabla de precios oficial verificable**; hay otro «Buzzy» distinto (de Creati) que confunde | Desconocido; prueba gratis de 2 videos según terceros | Probar gratis; no suscribir hasta ver precios y términos |
| **Veo 3.1 (Google)** | Video con audio sincronizado, muy realista | Activo, por API | Fast ~$0,10–0,12/s · Standard ~$0,40/s | Por API en F3 para automatizar; también disponible dentro de Higgsfield |
| **Kling 3** | Video realista barato, buen movimiento humano | Activo | Desde ~$7/mes (consumo) | Disponible dentro de Higgsfield; no suscribir aparte |
| **Voz con licencia comercial** (p. ej. ElevenLabs) | Voz fija del personaje, doblaje, locución | Activo | Desde ~$5/mes el plan más bajo con uso comercial; ~$22/mes el siguiente | **Suscribir con el personaje** |
| **CapCut** (o el editor nativo de cada app) | Edición rápida desde el teléfono, plantillas, subtítulos | Activo | Gratis; Pro ~$8–10/mes | Gratis para F1 |
| **Claude** (ya disponible) | Estrategia, guiones, revisión, análisis de datos, orquestación de agentes | Activo | Ya incluido en lo que Carlos usa | El «cerebro» del sistema |

## 2. Lectura honesta de cada una
- **Higgsfield** es la mejor opción para lo que Carlos pidió: un personaje que se ve igual en cada video, con
  calidad de redes de 2026, y acceso a varios modelos (Kling, Veo, Seedance y propios) sin pagar cada uno.
  Contras: el sistema de créditos es confuso, los créditos mensuales se pierden si no se usan, y el plan más
  barato rinde poco en video. No se ha confirmado si tiene API pública estable para automatizar; si no la
  tiene, el agente prepara los prompts y una persona los ejecuta en la web (5–10 minutos al día).
- **Remotion** no es IA generativa: es la **fábrica de plantillas**. Todo lo que sea texto, números,
  subtítulos, carruseles, portadas y cierres de marca se produce con código, gratis, igual siempre y sin
  errores de ortografía de la IA. Encaja con el monorepo (React/TypeScript).
- **Midjourney** da las imágenes más bonitas, pero no hace falta para arrancar: la fotografía nocturna de la web
  y las capturas reales ya dan identidad, y Higgsfield genera imagen también.
- **Runway** es excelente, pero duplica a Higgsfield para este uso. Tiene sentido solo si se necesita edición
  avanzada de video real (quitar objetos, extender planos).
- **Sora y DALL-E** ya no son opciones: OpenAI cerró Sora y retiró DALL-E. Cualquier plan que los nombre está
  desactualizado.
- **Buzzy** es demasiado nuevo para apostar: sin precios publicados, sin historial. Se puede probar la cuenta
  gratis para comparar, nada más.

## 3. Qué suscribir y cuándo
| Momento | Qué | Coste mensual aprox. | Por qué |
| --- | --- | --- | --- |
| **F0, mes 1** | Higgsfield **Plus, mensual** (no anual) + voz con licencia comercial (plan bajo) | ~$55–65 | Crear y probar el personaje; con el mes de uso se ve cuántos créditos se gastan de verdad |
| F0 | Remotion, CapCut, editores nativos | $0 | Plantillas y edición |
| F1, mes 2 | Mantener o bajar de plan según el consumo real del mes 1 | ~$25–65 | Decidir con datos |
| F2 | Opcional: Midjourney Basic si las portadas lo piden; pauta pagada sobre ganadores | +$10 + pauta | Solo si los datos lo justifican |
| F3 | APIs por uso (Veo/Kling vía proveedor, GPT Image) para automatizar | Según volumen | Automatización completa |

**Regla:** nunca plan anual hasta tener 2 meses de datos. Revisar el consumo de créditos cada semana
(lo registra el sistema, ver [09](09-registro-datos-y-medicion.md)).

## 4. Equipo físico mínimo para lo real
Un teléfono con buena cámara (ya existe), un micrófono inalámbrico de solapa (~$20–40), un estabilizador o
trípode pequeño (~$15–30). Es la inversión con mejor retorno de todo el plan: el contenido real de la calle
suele rendir más que el generado.

## 5. Fuentes consultadas
- [Higgsfield: nuevo AI Influencer](https://higgsfield.ai/blog/new-ai-influencer) ·
  [precios Higgsfield 2026 (Krea)](https://www.krea.ai/blog/higgsfield-pricing-explained-2026-unlimited-credits-and-real-monthly-costs) ·
  [expiración de créditos (Krater)](https://krater.ai/blog/higgsfield-pricing)
- [Remotion: precios de licencia](https://www.remotion.dev/docs/license/pricing)
- [Midjourney 2026 (eesel)](https://eesel.ai/blog/midjourney-pricing)
- [Runway 2026 (Creatify)](https://creatify.ai/blog/runway-pricing-(2026)-plans-credits-and-what-you-ll-actually-pay)
- [Cierre de Sora (NYU Shanghai RITS)](https://rits.shanghai.nyu.edu/ai/openai-shuts-down-sora-ai-video-app-discontinued-after-six-months/) ·
  [fin de la API de Sora (Zilliz)](https://zilliz.com/ai-faq/can-developers-still-use-the-sora-api)
- [Retiro de DALL-E (AgentDeals)](https://agentdeals.dev/dall-e-shutdown)
- [Buzzy: precios no verificados (Kingy)](https://kingy.ai/?p=925784) ·
  [Buzzy (Neuronfeed)](https://neuronfeed.com/news/buzzy-launches-agentic-video-creation-platform-with-infinite-canvas)
- [Veo 3.1 precios por segundo (BenchLM)](https://benchlm.ai/media-pricing/veo)
