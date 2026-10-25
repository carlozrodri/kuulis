# Terraform de Kuulis

Describe en código lo que Kuulis tiene en **Coolify** y **Cloudflare**, adoptando lo que ya existe con bloques
`import` (nada se crea de cero). El mapa completo de la infraestructura, incluido lo que no tiene proveedor de
Terraform (Expo, Firebase, Google Cloud, Play, Resend, MinIO, Nginx Proxy Manager…), está en
[`docs/infra/`](../../docs/infra/README.md).

> **Regla:** aquí solo se corre `init`, `validate`, `plan` y `output`. Un `terraform apply` cambia Coolify o
> Cloudflare de verdad y necesita el OK de Carlos cada vez.

## Qué cubre

| Archivo | Contenido |
| --- | --- |
| `locals.tf` | Inventario de Coolify: proyecto, entornos, 13 apps, Postgres, Redis, backups, volúmenes, servicios y las variables de entorno de cada app **por nombre** |
| `coolify.tf` | Recursos de Coolify (`coolify-terraform/coolify`) y data sources de solo lectura para servidores y servicios |
| `cloudflare.tf` | Zona `kuulis.com`, sus DNS, los DNS de Resend en `top8.uk`, dominios del Worker `kuulis`, bucket R2 `kuulis-backups`, ajustes de zona y Web Analytics |
| `imports.tf` | Un bloque `import` por recurso (ids reales leídos el 2026-10-24) |
| `outputs.tf` | `terraform output` imprime el inventario (apps, dominios, ramas, variables por nombre) |

Todo recurso lleva `prevent_destroy = true`: si un plan intenta borrar o reemplazar algo, falla.

**No gestiona** (a propósito): valores de variables y contraseñas, el código del Worker (lo despliega Workers
Builds), los servidores de Coolify (compartidos con otros proyectos), el comodín `*.top8.uk` (opt-in con
`manage_shared_dns`), las reglas de retención de R2 (opt-in con `manage_r2_lifecycle`, el proveedor no las importa)
y nada de los proyectos NDS ni bidding-market.

## Credenciales

Solo variables de entorno, nunca en archivos del repo:

```sh
export COOLIFY_ENDPOINT="https://<coolify>"       # sin /api/v1
export COOLIFY_TOKEN="<token de Coolify>"         # Coolify → Keys & Tokens → API tokens (basta lectura para plan)
export CLOUDFLARE_API_TOKEN="<token de Cloudflare>"  # permisos de lectura: Zone, DNS, Workers, R2, Analytics
```

Para un plan basta un token de **solo lectura** en ambos. Usar uno con escritura solo el día que se haga un
apply aprobado.

## Uso

```sh
cd infra/terraform
terraform init
terraform validate
terraform plan        # debe decir "N to import, 0 to add, 0 to destroy"
terraform output      # inventario legible
```

### Resultado del plan del 2026-10-24 (solo la parte de Coolify)

`Plan: 22 to import, 0 to add, 7 to change, 0 to destroy.` Los 7 cambios no lo son de verdad: el proveedor no lee
al importar `health_check_port` (API, admin, Expo), `custom_network_aliases` ni `limits_memory` (OSRM, Photon), y
propone escribir el mismo valor que ya tienen. La parte de Cloudflare se validó (`terraform validate`) pero no se
planificó porque esta sesión no tenía un token de API de Cloudflare.

## Dónde guardar el estado

Hoy el estado es local y git lo ignora (`.gitignore`). El estado guarda datos sensibles (por ejemplo la URL
interna de las bases con su contraseña), así que **nunca** se sube al repo. Si se empieza a aplicar con
Terraform, moverlo a un backend remoto cifrado; recomendado: el bucket R2 con un backend `s3`
(`use_lockfile = true`) en un bucket propio, p. ej. `kuulis-tfstate`, con token limitado a ese bucket.

## Cuando cambie la infraestructura

1. Cambiar en Coolify o Cloudflare como siempre (o aquí, con OK de Carlos).
2. Actualizar `locals.tf` / `cloudflare.tf` y la tabla de `docs/infra/README.md`.
3. `terraform plan` debe quedar sin cambios reales.

Para una app nueva de Coolify: añadirla a `local.applications` con su uuid; el `import` sale solo del mapa.
