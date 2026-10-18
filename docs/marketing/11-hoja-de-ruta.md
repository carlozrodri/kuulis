# 11 · Hoja de ruta paso a paso

Igual que en el rediseño de la web: cada paso se ejecuta **solo cuando Carlos lo pide**, como PR a `qa`
cuando hay código o documentos, y con su OK explícito cuando hay que pagar algo o abrir cuentas.

| Paso | Qué se entrega | Quién | Pagos | Criterio de terminado |
| --- | --- | --- | --- | --- |
| **MK0 · Plan** (este directorio) | Estrategia, plataformas, pilares, calendario, personaje, herramientas, agentes, datos, riesgos | Claude | $0 | Carlos responde las decisiones del README |
| **MK1 · Marca para redes** | `marketing/brand/`: hechos permitidos, tono, biblia del personaje (borrador), playbooks de ganchos por plataforma, formulario de autorización de imagen | Claude | $0 | Carlos aprueba la biblia |
| **MK2 · Cuentas** | Crear o revisar @kuulis en TikTok (empresa), Instagram (Business), YouTube, Facebook y canal de WhatsApp; perfiles completos con bio, enlace con UTM y destacadas | Carlos (son sus cuentas) con guía de Claude | $0 | Cuentas listas y conectadas al panel cuando exista |
| **MK3 · Personaje** | Exploración y fijación del personaje en Higgsfield, voz elegida, 5 videos de prueba, referencias exportadas | Carlos genera (o Claude si hay API), Claude dirige y documenta | ~$55–65 (mes 1) | Personaje consistente en 5 videos; Carlos lo aprueba |
| **MK4 · Estudio de plantillas** | `marketing/studio/` con Remotion: subtítulos, carrusel de cuentas, dato animado, portada, cierre de marca, render por plataforma | Claude | $0 | 5 plantillas renderizan desde un JSON de guion |
| **MK5 · Registro y panel** | `api/apps/marketing` (tablas de [09](09-registro-datos-y-medicion.md)), endpoints con rol `marketing`, panel admin (calendario, aprobar, rendimiento, carga manual de métricas, gasto) | Claude | $0 | Una pieza recorre todo el ciclo y sus métricas manuales aparecen en el panel |
| **MK6 · Agentes** | `.claude/agents/marketing-*.md`, rutinas programadas del flujo diario, paquete diario en el hilo con decisión de aprobar | Claude | $0 | Una semana completa de paquetes generados sin intervención técnica |
| **MK7 · Banco y arranque (F1)** | 20 piezas en reserva (10 reales + 10 IA/plantilla); publicación diaria según [04](04-calendario-y-flujo-diario.md) | Agentes + persona que publica + sesión semanal de grabación | Equipo mínimo ~$35–70 una vez | 4 semanas publicadas y registradas |
| **MK8 · Métricas por API y atribución** | Conexión de Insights de Instagram, TikTok Display/Business y YouTube Analytics; UTM en la web; códigos de campaña y «¿Cómo nos conociste?» en la app | Claude | $0 | El informe semanal sale con datos automáticos y registros por canal |
| **MK9 · Revisión de F1** | Informe de 4 semanas: qué formatos, ganchos y horarios funcionan; decisión de planes y de pauta | Agentes + Carlos | — | Carlos decide F2 |
| **MK10 · Publicación automática** | Instagram y YouTube por API desde el panel; trámite de auditoría de TikTok | Claude | $0 | Publicaciones programadas con aprobación previa |

**Orden recomendado:** MK1 → MK2 y MK3 en paralelo → MK4 → MK5 → MK6 → MK7 → MK8 → MK9 → MK10.

Se puede empezar a publicar antes de tener el panel (MK5): en ese caso el registro se lleva en un archivo
del repo (`marketing/registro/`) con el mismo formato, y se importa a la base de datos cuando exista.
