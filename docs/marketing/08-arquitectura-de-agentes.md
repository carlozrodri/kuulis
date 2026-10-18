# 08 · Arquitectura de agentes de contenido y marketing

## 1. Idea general
Un equipo pequeño de agentes especializados, cada uno con un trabajo claro, que se pasan el trabajo en orden
y dejan todo registrado. Las personas aprueban lo que sale; los agentes hacen el resto.

```
                    ┌──────────────────────── datos de Kuulis (registros, viajes, UTM) ───────────────┐
                    │                                                                                  │
   tendencias ──► ESTRATEGA ──► GUIONISTA ──► REVISOR ──► PRODUCTOR ──► [APROBACIÓN HUMANA] ──► PUBLICADOR
                    ▲              (3 ganchos)  (marca,     (IA +          (Carlos, en el hilo      (manual F1,
                    │                           hechos,     Remotion)       o en el panel)           API F2–F3)
                    │                           riesgos)                                                │
                    │                                                                                   ▼
               RECOMENDADOR ◄──────────────────────── ANALISTA ◄──────────── métricas de TikTok / IG / YouTube
               (aprendizajes,                         (24 h, 72 h, 7 d)
                experimentos)
                                    COMUNIDAD: sugiere respuestas a comentarios y DMs (una persona publica en F1)
```

## 2. Los agentes
| Agente | Entra | Sale | Cuándo | Reglas clave |
| --- | --- | --- | --- | --- |
| **Estratega** | Aprendizajes, calendario base ([04](04-calendario-y-flujo-diario.md)), tendencias, reserva de piezas, datos de oferta y demanda | Calendario semanal (pilar, formato, plataforma, franja), alertas de reserva baja, propuestas F-TENDENCIA | Domingos + revisión de tendencias 2 veces al día | Respeta la mezcla de la fase; nunca tendencias sensibles |
| **Guionista** | Una entrada del calendario + biblia de marca + biblia del personaje | Guion con 3 ganchos, texto en pantalla, subtítulos, descripción y hashtags por red, CTA con UTM | Diario | Solo hechos de [01](01-estrategia-y-posicionamiento.md); estructura de [03](03-pilares-y-formatos.md) |
| **Revisor de marca y cumplimiento** | Guion (y luego el video) | Aprobado / cambios pedidos / rechazado, con motivo | Antes de producir y antes de publicar | Lista de [10](10-riesgos-y-cumplimiento.md); verifica cada cifra contra la fuente; exige etiqueta de IA si toca |
| **Productor** | Guion aprobado | Prompts de Higgsfield y Buzzy, voz, renders de Remotion, grabaciones de pantalla de la app, versiones por plataforma (sin marcas de agua cruzadas), portada | Diario | Usa las plantillas de marca; registra herramienta, modelo y créditos gastados |
| **Publicador** | Paquete aprobado | Publicación programada (API) o paquete listo para publicar a mano; registro del enlace y la hora | En la franja | Nunca publica sin aprobación; F1 siempre manual |
| **Analista** | APIs de métricas, carga manual, eventos de la web y de la app | Instantáneas de métricas por publicación, informe diario corto y semanal | Diario 06:00 + domingo | Compara contra la mediana de la cuenta, no contra cifras de manual |
| **Recomendador** | Métricas + atributos de cada pieza | Aprendizajes con evidencia, ajuste de pesos de pilares y formatos, experimentos A/B propuestos | Diario (ligero) y semanal (profundo) | Toda recomendación cita las piezas y números que la respaldan; distingue «probado» de «hipótesis» |
| **Comunidad** | Comentarios y DMs | Respuestas sugeridas, preguntas frecuentes nuevas, ideas de F-RESPUESTA, alertas de crisis | Cada pocas horas | Nunca discute; escala quejas de seguridad a soporte de inmediato |

## 3. Dónde viven
Todo en el monorepo, para que cualquier sesión de Claude (o una persona) los use igual:

```
.claude/agents/            Definición de cada agente (Markdown propio de Kuulis)
  marketing-estratega.md
  marketing-guionista.md
  marketing-revisor.md
  marketing-productor.md
  marketing-publicador.md
  marketing-analista.md
  marketing-recomendador.md
  marketing-comunidad.md
marketing/
  brand/                   Biblia de marca, hechos permitidos, personaje (texto + parámetros + referencias)
  studio/                  Proyecto Remotion: plantillas de subtítulos, carruseles, datos, portadas, cierres
  playbooks/               Fórmulas de ganchos, guías por plataforma (se actualizan con lo aprendido)
api/apps/marketing/        Tablas, endpoints y tareas (registro de piezas, publicaciones, métricas, aprendizajes)
admin/app/pages/marketing/ Panel: calendario, aprobación, rendimiento, aprendizajes, consumo de créditos
```

Los archivos grandes (videos, imágenes) no van a git: **todo lo que se genera se guarda en S3** (decidido):
el MinIO del homelab, o Cloudflare R2 si MinIO no sirve. El registro guarda la ruta. Detalle de datos en [09](09-registro-datos-y-medicion.md).

## 4. Cómo se ejecutan
- **Motor:** Claude (Claude Code) trabajando sobre el repo, con los agentes como subagentes. No hace falta un
  servidor nuevo de agentes.
- **Programación:** rutinas programadas (tareas recurrentes en la nube de Claude) que se disparan a las horas
  del flujo diario: métricas y aprendizaje temprano, guiones y producción después, informe los domingos.
- **Acceso a datos:** los agentes leen y escriben en la API de Kuulis con un token de servicio de rol
  `marketing` (sin acceso a datos personales de usuarios), nunca directo a la base de datos.
- **Aprobación:** el paquete del día llega al hilo de marketing del proyecto con botones de decisión
  (aprobar, cambiar, descartar), y queda también en el panel. Lo aprobado cambia de estado en el registro y
  pasa al publicador.
- **Generación de IA (decidido, 2026-10-18):** Carlos se suscribe a Higgsfield y Buzzy **cuando todo lo demás
  esté montado** y conecta las cuentas para que los agentes generen directamente.
  - **Higgsfield** tiene un **MCP oficial** (servidor alojado en `mcp.higgsfield.ai`, entra con OAuth y gasta
    los créditos del plan, sin clave) y además una API REST con clave (`api.higgsfield.ai`, claves desde
    `cloud.higgsfield.ai`) y un CLI oficial. Se conecta el MCP como conector de Claude: Carlos inicia sesión
    una vez y no hace falta pasar contraseñas. La API con clave queda para tareas programadas del servidor.
    Hay servidores MCP «comunitarios» que usan tokens de sesión del navegador: no se usan.
  - **Buzzy** también tiene **MCP oficial** (<https://www.buzzy.now/es/mcp>, servidor `https://mcp.buzzy.now/mcp`):
    se añade en Claude como conector personalizado y Carlos inicia sesión una vez con su cuenta de Buzzy. Genera
    imágenes, videos, storyboards, anuncios, animaciones y proyectos completos con sus modelos (Seedance, Kling,
    Veo, Midjourney, Nano Banana, etc.). Su página no dice qué planes lo incluyen ni cuántos créditos gasta
    cada llamada: se verifica con el plan Basic el primer día de MK3.
  - En F3 se puede pasar a APIs de pago por uso (Veo, Kling, GPT Image) para automatizar del todo.
- **Credenciales:** **nunca se pegan en el chat ni en el repo.** OAuth para los MCP (Higgsfield, Meta, Google);
  las claves que haga falta guardar (API de Higgsfield, TikTok, almacenamiento) van a las variables de entorno
  de Coolify o a los secretos del entorno de Claude, que Carlos carga directamente.

## 5. Cómo aprende el sistema
1. Cada pieza se registra con sus **atributos**: pilar, formato, gancho (tipo y texto), duración, personaje
   sí/no, real o IA, herramienta, hora, día, audio, plataforma.
2. El analista guarda métricas a las 24 h, 72 h y 7 días.
3. El recomendador compara grupos de piezas por atributo (por ejemplo, «gancho de número que duele» contra
   «POV») usando la mediana de la cuenta como referencia, y solo declara un aprendizaje cuando hay al menos
   5 piezas por grupo y la diferencia se mantiene en dos semanas.
4. Los aprendizajes confirmados actualizan los pesos del calendario, los playbooks y las instrucciones de los
   agentes (con un PR al repo, para que quede la historia de por qué cambió algo).
5. Cada semana se proponen **1 o 2 experimentos** controlados (mismo guion con dos ganchos, misma pieza en dos
   horarios) para responder preguntas concretas.

## 6. Qué decide siempre una persona
- Publicar cualquier pieza (hasta que Carlos diga lo contrario por escrito).
- Gastar dinero: suscripciones, créditos extra, pauta.
- Responder a crisis, quejas de seguridad o prensa.
- Cambiar el personaje, el tono o los hechos permitidos.
