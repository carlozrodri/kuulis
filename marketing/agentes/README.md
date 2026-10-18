# marketing/agentes · Flujo diario de los agentes (MK6)

Los agentes de contenido de Kuulis viven en [`.claude/agents/marketing-*.md`](../../.claude/agents/). Este
archivo es el **guion del orquestador**: la sesión de Claude del hilo de marketing del proyecto lo sigue cuando
se dispara la tarea programada, llama a cada agente en orden y deja el paquete del día en el hilo para que Carlos
lo apruebe. Arquitectura y razones en [`docs/marketing/08`](../../docs/marketing/08-arquitectura-de-agentes.md).

## Piezas del sistema

| Pieza | Dónde | Para qué |
| --- | --- | --- |
| Agentes | `.claude/agents/marketing-{estratega,guionista,revisor,productor,publicador,analista,recomendador,comunidad}.md` | Un trabajo cada uno, con sus reglas |
| Cliente del registro | [`mk.py`](mk.py) | Lo único que usan los agentes para leer y escribir en la API (`/admin/marketing`) |
| Registro | API MK5 ([contrato](../../docs/api/marketing.md)) y panel `/marketing` | Fuente de verdad: piezas, versiones, archivos, métricas, aprendizajes |
| Plantillas | [`../studio/`](../studio/README.md) | Renders de Remotion (dato, carrusel, subtítulos, portada) |
| Archivos | Bucket S3 `kuulis-marketing` | Todo lo generado; nunca en git |

Nada se guarda en git en el día a día: el calendario son piezas en estado `idea` con fecha, los guiones viven en
el campo `script` de cada pieza y los archivos en S3. En git solo cambian los agentes, la marca y los playbooks,
siempre por PR.

## Acceso a la API

- `KUULIS_API`: `https://kuulis-qa.top8.uk/api/v1` mientras producción esté apagada; luego la de producción.
- `KUULIS_MK_TOKEN`: **token de servicio** creado en el panel (Administración › Tokens de servicio) para una cuenta de
  staff con el rol **Agentes de marketing** (lo crea la migración). Permisos: `marketing.view`, `marketing.manage`, `marketing.publish` y
  `marketing.approve` (este último solo para registrar la decisión que Carlos toma en el hilo).
- El token va en los **secretos del entorno de Claude** (configuración del entorno), nunca en el chat ni en el
  repo. Si falta, el flujo se detiene en el paso 0 y avisa una sola vez.

```bash
python3 marketing/agentes/mk.py site            # valores vivos de cuota, meses gratis, pagos (sin token)
python3 marketing/agentes/mk.py list --status idea --desde 2026-11-03 --hasta 2026-11-09
python3 marketing/agentes/mk.py show K-2026-11-04-A
python3 marketing/agentes/mk.py --help          # todos los comandos
```

## Forma del guion (`script` de la pieza)

Todos los agentes leen y escriben esta forma; los campos que un agente no toca se conservan tal cual.

```json
{
  "idea": "Qué entiende quien lo ve, en una frase",
  "hechos": ["H3", "H4"],
  "ganchos": [{"tipo": "G1", "texto": "…"}, {"tipo": "G3", "texto": "…"}, {"tipo": "G7", "texto": "…"}],
  "gancho_elegido": 0,
  "duracion_s": 25,
  "escenas": [{"desde_s": 0, "hasta_s": 2, "plano": "…", "voz": "…", "texto": "…"}],
  "cta": "Link en la bio para descargar (Android).",
  "textos": {
    "tiktok": {"caption": "…", "hashtags": ["Kuulis", "Caracas", "Motorizados"]},
    "instagram": {"caption": "…", "hashtags": ["…"]},
    "youtube": {"title": "…", "caption": "…", "hashtags": ["…"]},
    "whatsapp": {"caption": "…"}
  },
  "prompts": [{"herramienta": "higgsfield", "plano": "0–2 s", "prompt": "…"}],
  "studio": {"codigo": "K-…", "salidas": []},
  "revision": {"veredicto": "aprobado | cambios | rechazado", "hechos_verificados": ["H4: /public/site fee_tiers"], "riesgos": [], "ia_label": true, "notas": "…"},
  "produccion": {"estado": "hecho | espera_mk3", "archivos": ["tiktok.mp4"], "notas": "…"}
}
```

`studio` es el archivo de pieza de [`../studio/src/schema.ts`](../studio/src/schema.ts) (el que recibe
`pnpm render`).

## Flujo diario (tarea programada, ~07:45 hora de Caracas)

El orquestador trabaja sobre **mañana** (`D+1`): así Carlos aprueba hoy y la persona en Caracas publica mañana.

0. **Preparar.** `git pull` de `qa`; comprobar `KUULIS_MK_TOKEN` con `mk.py list --limit 1`. Si el studio no tiene
   `node_modules`, `pnpm install --frozen-lockfile` en `marketing/studio`. Leer `mk.py site` una vez (valores vivos).
1. **Analista** → informe corto: métricas que faltan cargar (24 h, 72 h, 7 d), lo mejor y lo peor de ayer.
2. **Recomendador** (modo diario) → ajustes del día y aprendizajes nuevos o actualizados, con evidencia.
3. **Guionista** → para cada idea de `D+1` (normalmente 2): guion completo, pasa a `guion`. Si no hay ideas para
   `D+1`, avisa al estratega para que cree 2 desde el calendario base.
4. **Revisor** → cada guion: `revisado` si pasa; si no, devuelve al guionista **una vez** con los cambios. Si
   vuelve a fallar, la pieza queda en `guion` y se reporta.
5. **Productor** → piezas `revisado`: render, subida a S3, versiones por red con hora, pasa a `producido`. Las que
   necesitan video de IA quedan con prompts listos y `produccion.estado = espera_mk3` hasta que Higgsfield o
   Buzzy estén conectados.
6. **Publicador** → revisa que lo de `D+1` esté completo (archivo, portada, hora, checklist) y lista lo que falta.
7. **Paquete en el hilo** (lo hace el orquestador, no un agente):
   - Una tarjeta de decisión por pieza `producido`: «Aprobar», «Pedir cambios», «Descartar», con el gancho, el
     enlace al panel (`/marketing/piezas/<id>`), el texto de TikTok y la hora.
   - Una sola respuesta corta con el resumen del analista y del recomendador, y lo que espera a MK3.
   - Al tocar Carlos una opción: «Aprobar» → `mk.py approve`; «Pedir cambios» → `mk.py changes` con su nota y
     vuelta al paso 3 para esa pieza; «Descartar» → `mk.py status … descartado`. Nunca se aprueba sin su toque o
     su palabra escrita.

## Flujo semanal (domingo ~17:45)

1. **Analista** (modo semanal): informe de la semana contra la mediana de la cuenta.
2. **Recomendador** (modo semanal): aprendizajes confirmados o descartados, pesos de pilares y formatos para la
   semana, 1–2 experimentos.
3. **Estratega**: calendario de la semana siguiente (14 piezas `idea` con fecha, pilar, formato, público y franja)
   y alerta si la reserva de piezas aprobadas baja de 5.
4. Paquete semanal en el hilo: informe y calendario, con una tarjeta para aprobar el calendario.

## A demanda

- **Comunidad**: cuando Carlos o la persona en Caracas pegan comentarios o DMs en el hilo, sugiere respuestas.
- Cualquier agente puede correrse suelto pidiéndoselo al hilo («corre el guionista para la idea X»).

## Reglas que valen para todos

- Solo se afirma lo que está en [`../brand/hechos.md`](../brand/hechos.md), con los valores vivos de `/public/site`.
- Nada se publica sin aprobación de Carlos. Ningún agente gasta dinero, crea cuentas ni cambia la marca.
- Los agentes no ven datos personales de usuarios: solo el registro de marketing y `/public/site`.
- Todo lo que un agente decide queda en el registro (campo `script`, `notes`, aprendizajes), no solo en el chat.
- Antes de MK3 (sin generador de IA conectado) se producen solo formatos de plantilla: `F-DATO`, `F-CARRUSEL` y
  videos de texto con `Subtitulos` sobre fondo de marca. Las piezas de IA se guionizan y quedan en reserva.
