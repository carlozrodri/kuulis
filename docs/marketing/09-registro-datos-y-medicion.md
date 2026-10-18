# 09 · Registro, datos y medición

Todo lo que se crea y se publica queda registrado, para que los agentes (y Carlos) puedan saber en cualquier
momento qué se publicó, dónde, con qué herramienta, cuánto costó y qué resultado dio.

## 1. Qué se guarda y dónde
| Qué | Dónde | Por qué ahí |
| --- | --- | --- |
| Biblia de marca, hechos permitidos, personaje, playbooks, definiciones de agentes | Repo (`marketing/`, `.claude/agents/`) | Versionado: se ve quién cambió qué y por qué |
| Plantillas de video (Remotion) | Repo (`marketing/studio/`) | Es código |
| Piezas, versiones, publicaciones, métricas, aprendizajes, experimentos, gasto | Base de datos de la API (`api/apps/marketing`) | Consultable, alimenta el panel y los agentes |
| Videos, imágenes, audios (todo lo generado, también lo descartado) | S3: MinIO del homelab, bucket propio (ver §1.1) | Pesan demasiado para git; decidido que todo se guarda |
| Informes semanales | Panel + resumen en el hilo de marketing del proyecto | Lectura rápida |

### 1.1 Almacenamiento de archivos (decidido, 2026-10-18)
**Todo el contenido que se genere se guarda en S3**, incluidas las versiones descartadas (sirven para comparar
herramientas y para no pagar dos veces por lo mismo).

- **Principal: MinIO del homelab**, el mismo servicio S3 que ya usa la API (`AWS_*`), pero en un **bucket
  propio `kuulis-marketing`** con una clave de acceso solo para ese bucket, para no mezclarlo con documentos
  de motorizados ni con su política de borrado.
- **Si MinIO no sirve** (espacio, ancho de banda para descargar videos desde el teléfono en Caracas):
  **Cloudflare R2**, que no cobra la salida de datos, en un bucket distinto al de backups.
- **Copia fuera de casa:** lo publicado y lo aprobado se copia también a R2 cada noche, como ya se hace con los
  backups, para no perder el archivo de marca si falla el homelab. (Supuesto: los descartes no se copian.)
- **Estructura:** `marketing/{entorno}/{año}/{mes}/{código-de-pieza}/` con `original/` (lo que devolvió la
  herramienta), `final/{red}.mp4`, `portada.jpg` y `fuentes/` (audio, imágenes intermedias). Los nombres
  llevan el código de la pieza para encontrarlos desde el registro.
- **Acceso:** la persona que publica descarga con enlaces temporales firmados; nada es público.
- **Tamaño estimado:** ~2 piezas al día × 3 redes × ~20 MB + originales ≈ 5–8 GB al mes. Se revisa al mes 1.

## 2. Modelo de datos (implementado en MK5)
Implementado el 2026-10-18 en `api/apps/marketing`; el contrato está en [`docs/api/marketing.md`](../api/marketing.md).
Diferencias con la propuesta de abajo: la versión por red apunta a sus archivos por id (`asset_id`,
`cover_asset_id`) en vez de guardar la clave de S3; la hora de publicación va en cada versión (`scheduled_at`) y
la pieza guarda solo el día (`scheduled_for`); el enlace con UTM se calcula al leer (no se guarda); el alcance de
un aprendizaje son tres columnas (`platform`, `pillar`, `format`); y `marketing_experiment` queda para MK9, cuando
haya datos que comparar.

Sigue las convenciones de la API: una app por dominio, migraciones con Alembic, lógica en `services.py`,
tareas lentas en `tasks.py`.

| Tabla | Campos principales |
| --- | --- |
| `marketing_content` | `id`, `code` legible (`K-2026-11-04-A`), `title`, `pillar`, `format`, `audience` (motorizado/pasajero/ambos), `status` (idea → guion → revisado → producido → aprobado → publicado → archivado / descartado), `script` (JSONB: ganchos, texto en pantalla, subtítulos, CTA), `uses_character`, `production` (real/ia/mixto), `scheduled_for`, `approved_by`, `approved_at`, `created_by_agent` |
| `marketing_variant` | Versión por plataforma: `content_id`, `platform` (tiktok/instagram/youtube/whatsapp/facebook), `hook_index`, `caption`, `hashtags`, `duration_s`, `asset_key` (S3), `cover_key`, `utm_url`, `ai_label` (bool) |
| `marketing_asset` | Cada archivo generado o grabado: `content_id`, `kind` (video/imagen/audio), `source` (higgsfield/remotion/telefono/gpt-image/voz…), `model`, `prompt`, `credits_used`, `cost_usd`, `rights` (licencia / autorización de imagen), `s3_key` |
| `marketing_publication` | `variant_id`, `platform`, `external_id`, `url`, `published_at`, `published_by` (persona o API), `account` |
| `marketing_metric_snapshot` | `publication_id`, `taken_at`, `age_h` (24/72/168…), `views`, `reach`, `avg_watch_s`, `completion_rate`, `likes`, `comments`, `shares`, `saves`, `follows`, `profile_visits`, `link_clicks`, `source` (api/manual) |
| `marketing_learning` | `statement`, `evidence` (ids de piezas y números), `status` (hipótesis/probado/descartado), `scope` (plataforma, pilar, formato), `created_at`, `reviewed_at` |
| `marketing_experiment` | `question`, `variant_a`, `variant_b`, `metric`, `result`, `decision` |
| `marketing_spend` | `date`, `tool`, `concept` (suscripción/créditos/pauta), `amount_usd`, `notes` |
| `marketing_account` | Cuentas por red y su conexión (sin guardar tokens en claro; los tokens van en el gestor de secretos) |

## 3. Cómo llegan las métricas
| Red | Fuente | Requisito |
| --- | --- | --- |
| Instagram | Insights de la Graph API (alcance, reproducciones, guardados, compartidos, visitas al perfil) | Cuenta Business o Creator vinculada a una página de Facebook; app de Meta en modo desarrollo vale para la cuenta propia |
| TikTok | Display API (vistas, likes, comentarios, compartidos por video) y API for Business para cuentas empresa (más métricas) | App en TikTok for Developers; la lectura de métricas propias no exige la auditoría de publicación |
| YouTube | YouTube Analytics API (vistas, retención, tiempo visto, fuentes de tráfico) | Proyecto en Google Cloud con OAuth del canal |
| Cualquiera | **Carga manual** en el panel (o captura de pantalla de las estadísticas que el agente lee) | Respaldo para F1 o si una API falla |

El analista toma instantáneas a las 24 h, 72 h y 7 días de cada publicación. Las métricas de la cuenta
(seguidores, alcance total) se guardan a diario.

## 4. De la red al registro y al viaje (atribución)
La parte difícil: saber qué pieza trajo un motorizado o un pasajero. Se combina:
1. **Enlaces con UTM** por publicación: `…/descargar?utm_source=tiktok&utm_medium=social&utm_campaign=f1&utm_content=K-2026-11-04-A`.
   La web guarda la visita con su UTM (evento propio, sin datos personales) y lo cuenta en el panel.
2. **Códigos de campaña** en la app: el programa de referidos ya maneja códigos personales
   (`api/apps/referrals`, doc [`produccion/22`](../produccion/22-referidos.md)). Se añaden códigos de campaña por red o por serie (por ejemplo, `KUUTT` para TikTok,
   `KUUIG` para Instagram) que el personaje menciona en los videos. Dan un premio pequeño ya previsto por las
   promociones y dicen de dónde vino cada registro.
3. **Pregunta «¿Cómo nos conociste?»** opcional en el registro (TikTok, Instagram, YouTube, WhatsApp,
   un motorizado, un amigo, otro). Barata y muy útil.
4. **Correlación temporal:** picos de registros e instalaciones en las horas siguientes a una pieza que se
   hace viral.

Como la app se instala por APK desde la web (no por tienda), no hay referrer de Google Play; por eso los
puntos 2 y 3 son importantes. Los cambios en la app y en el evento de la web se planifican como trabajo
técnico aparte cuando se aprueben (ver [11](11-hoja-de-ruta.md)).

## 5. Privacidad
- El sistema de marketing **no guarda datos personales de usuarios**; cruza solo conteos agregados (registros
  por código o por UTM y día).
- Los comentarios y DMs que lee el agente de comunidad no se copian a la base de datos más allá de lo
  necesario para responder; las preguntas frecuentes se guardan anonimizadas.
- Las autorizaciones de imagen de personas reales grabadas se guardan como archivo junto a la pieza
  (`marketing_asset.rights`).

## 6. Panel de marketing (admin)
Pestañas: **Calendario** (lo que sale cada día y su estado), **Aprobar** (cola con vista previa),
**Rendimiento** (tabla de piezas con métricas y filtros por pilar, formato, gancho y red), **Aprendizajes**
(lo probado y lo que está en prueba), **Gasto** (créditos y suscripciones del mes) y **Cuentas** (estado de
la conexión con cada red).

## 7. Informe semanal (domingo)
Una página, en el hilo de marketing:
1. Lo que pasó: piezas publicadas, vistas totales, mejor y peor pieza con su motivo probable.
2. Lo que trajo: visitas con UTM, registros por código, solicitudes de motorizado.
3. Lo aprendido (con evidencia) y lo que se descarta.
4. Calendario propuesto de la semana siguiente.
5. Gasto del mes y créditos que quedan.
6. Decisiones que necesita Carlos (si hay).
