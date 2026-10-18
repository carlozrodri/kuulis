# Contrato de API · Marketing en redes (MK5)

Base `/api/v1`, mismo sobre de errores (`{"error": {"code", "message", "details"}}`). Todo vive en
`/admin/marketing` y pide sesión del panel (staff o admin). Montos como texto con dos decimales (`"19.00"`), en USD.
Plan y modelo de datos en [`docs/marketing/09`](../marketing/09-registro-datos-y-medicion.md).

## Permisos y roles

| Permiso | Para qué |
| --- | --- |
| `marketing.view` | Ver piezas, rendimiento, aprendizajes, gasto y cuentas |
| `marketing.manage` | Crear y editar piezas, archivos, versiones por red, métricas, aprendizajes, gasto y cuentas |
| `marketing.approve` | Aprobar o pedir cambios (por defecto solo los admin: Carlos) |
| `marketing.publish` | Ver las tarjetas del día y marcar publicado |

La migración crea dos roles: **Marketing** (`view`, `manage`, `publish`) y **Publicador** (`publish`, solo la
página Publicar). Los admin tienen todo. MK6 añade **Agentes de marketing** (`view`, `manage`, `publish`,
`approve`) para la cuenta del token de servicio de los agentes; solo registra la aprobación que Carlos da en el hilo.

## Ciclo de una pieza

```
idea → guion → revisado → producido → aprobado → publicado → archivado
  (descartado desde cualquier paso antes de publicar; descartado → idea la revive)
```

- `aprobado` solo con `POST …/approve` (`marketing.approve`). Exige al menos una versión por red y que **cada
  una** tenga su archivo final subido (`asset_id`) y su hora (`scheduled_at`). Si falta algo: 409
  `marketing_not_ready` con `details.missing = [{platform, field}]`.
- `publicado` solo lo pone el sistema cuando la persona marcó publicadas todas las versiones.
- **Editar una pieza aprobada** (texto, versión, archivo) la devuelve a `producido` y borra la aprobación: nada
  llega al teléfono sin aprobar.
- Publicada, archivada o descartada: no se edita (409 `marketing_content_locked`); sí se le pueden subir fuentes
  y cargar métricas.
- `code`: `K-AAAA-MM-DD-X` con la fecha planificada (`scheduled_for`, o hoy en Caracas), letras A…Z, AA… No cambia
  después. Nombra la carpeta en S3, el `utm_content` y los archivos descargados.

## Archivos (bucket `kuulis-marketing`)

Subida en dos pasos, para que el archivo nunca pase por la API:

1. `POST /admin/marketing/contents/{id}/assets` con
   `{filename, content_type, size, role, source, model?, prompt?, credits_used?, cost_usd?, rights?, width?, height?, duration_s?}`
   → 201 `{asset, upload_url, method: "PUT", headers}`.
   - `role`: `original` (lo que devolvió la herramienta) · `final` (listo para una red) · `portada` · `fuente`.
   - `content_type`: `video/mp4`, `video/quicktime`, `image/jpeg|png|webp`, `audio/mpeg|mp4|wav`. Hasta
     `MARKETING_MAX_UPLOAD_MB` (500).
2. `PUT upload_url` con los bytes y los `headers` indicados (enlace válido 15 min).
3. `POST …/assets/{asset_id}/confirm` → el archivo queda `uploaded_at` (400 `marketing_asset_not_uploaded` si no
   está en S3).

Clave: `marketing/<entorno>/<año>/<mes>/<código>/<original|final|portada|fuentes>/<8 hex>-<nombre>`. Nada se
sobrescribe ni se borra: los descartes quedan para comparar herramientas. Sin bucket configurado: 503
`marketing_storage_disabled`.

Ejemplo con curl (lo que hará el agente productor en MK6):

```bash
R=$(curl -s -X POST "$API/admin/marketing/contents/$ID/assets" -H "Authorization: Bearer $TOKEN" \
  -H 'Content-Type: application/json' \
  -d '{"filename":"01-subtitulos-tiktok.mp4","content_type":"video/mp4","size":'"$(stat -c%s f.mp4)"',"role":"final","source":"remotion"}')
curl -s -X PUT "$(jq -r .upload_url <<<"$R")" -H 'Content-Type: video/mp4' --data-binary @f.mp4
curl -s -X POST "$API/admin/marketing/contents/$ID/assets/$(jq -r .asset.id <<<"$R")/confirm" -H "Authorization: Bearer $TOKEN"
```

## Endpoints

| Método | Ruta | Permiso | Qué hace |
| --- | --- | --- | --- |
| GET | `/admin/marketing/contents` | view | `?status&q&from&to&limit&offset` → `Page[ContentSummary]` (`from`/`to` filtran `scheduled_for`; `q` busca título o código) |
| POST | `/admin/marketing/contents` | manage | `{title, pillar?, format?, audience, script, uses_character, production: plantilla|ia|mixto|real, scheduled_for?, notes?, created_by_agent?, status: idea\|guion}` → `ContentRead` |
| GET | `/admin/marketing/contents/{id}` | view | `ContentRead`: la pieza con `variants` (cada una con `utm_url` y su `publication` con métricas), `assets` (con `download_url`) y `allowed_statuses` |
| PATCH | `/admin/marketing/contents/{id}` | manage | Campos de la pieza |
| POST | `/admin/marketing/contents/{id}/status` | manage | `{status}` según el ciclo (409 `marketing_invalid_transition`) |
| POST | `/admin/marketing/contents/{id}/approve` | approve | Aprueba (ver reglas) |
| POST | `/admin/marketing/contents/{id}/request-changes` | approve | `{note}` → vuelve a `revisado` con `review_note` |
| POST | `/admin/marketing/contents/{id}/assets` | manage | Registra un archivo y da el enlace de subida |
| POST | `/admin/marketing/contents/{id}/assets/{asset_id}/confirm` | manage | Confirma la subida |
| POST | `/admin/marketing/contents/{id}/variants` | manage | `{platform, account?, hook_index, title?, caption, hashtags, checklist, ai_label, duration_s?, asset_id?, cover_asset_id?, scheduled_at?}`; una por red (409 `marketing_variant_exists`) |
| PATCH / DELETE | `/admin/marketing/contents/{id}/variants/{variant_id}` | manage | Editar o quitar la versión |
| GET | `/admin/marketing/queue` | publish | `?day=AAAA-MM-DD` (hoy en Caracas por defecto) → `[PostingCard]` de piezas aprobadas, por hora |
| POST | `/admin/marketing/variants/{variant_id}/publish` | publish | `{url?, external_id?, published_at?}` → la publicación (409 `marketing_already_published`, `marketing_not_approved`) |
| PATCH | `/admin/marketing/publications/{id}` | publish | Añade el enlace o el id después |
| POST | `/admin/marketing/publications/{id}/metrics` | manage | Instantánea `{taken_at?, age_h?, views, reach, avg_watch_s, completion_rate (0–1), likes, comments, shares, saves, follows, profile_visits, link_clicks, source}`; sin `age_h` se calcula desde la publicación |
| GET | `/admin/marketing/performance` | view | `?platform&pillar&format&from&to` → una fila por publicación con su última instantánea (máx. 500) |
| GET / POST / PATCH | `/admin/marketing/learnings[/{id}]` | view / manage | `{statement, evidence?, status: hipotesis\|probado\|descartado, platform?, pillar?, format?}` |
| GET | `/admin/marketing/spend` | view | `?month=AAAA-MM` → `{month, total, by_tool, items}` |
| POST / DELETE | `/admin/marketing/spend[/{id}]` | manage | `{date, tool, concept: suscripcion\|creditos\|pauta\|otro, amount_usd, notes?}` |
| GET / POST / PATCH | `/admin/marketing/accounts[/{id}]` | view / manage | `{platform, handle, url?, status: pendiente\|activa\|suspendida, connection: manual\|api, notes?}`. Sin tokens |

Redes: `tiktok`, `instagram`, `youtube`, `whatsapp`, `facebook`. Hashtags se guardan sin `#` (se aceptan con él)
y salen con `#` en la tarjeta.

## Tarjeta de publicación

```
PostingCard = {
  variant_id, content_id, code, content_title, platform, account, scheduled_at,
  title, caption, hashtags: ["#Caracas", …],
  checklist: ["Etiqueta de contenido de IA: activar", "Ubicación: Caracas", …],  // fijos + los de la versión
  file_url, file_name: "K-2026-11-04-A-tiktok.mp4", file_kind, cover_url,      // enlaces firmados de 1 h
  publication_id, published_at, published_url
}
```

## Configuración

| Variable | Valor |
| --- | --- |
| `MARKETING_S3_BUCKET` | `kuulis-marketing` (vacío: almacenamiento apagado) |
| `MARKETING_S3_ACCESS_KEY_ID` / `MARKETING_S3_SECRET_ACCESS_KEY` | Clave de MinIO limitada a ese bucket (vacías: usa las `AWS_*`) |
| `MARKETING_MAX_UPLOAD_MB` | 500 |
| `MARKETING_DOWNLOAD_URL_SECONDS` | 3600 |

El endpoint es el mismo `AWS_S3_ENDPOINT`. El bucket necesita la **misma regla CORS** que el bucket principal
(PUT y GET desde el dominio del panel) para que el panel suba archivos desde el navegador.
