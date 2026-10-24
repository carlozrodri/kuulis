terraform {
  # 1.7+ por los bloques `import` con `for_each` (imports.tf).
  required_version = ">= 1.7.0"

  required_providers {
    # Proveedor de Coolify más completo y mantenido (59 recursos, publicado 2026-10-21). El de SierraJC no tiene
    # aplicaciones ni backups y no publica desde 2025-08. Versión fija: es 0.x y puede cambiar entre versiones.
    coolify = {
      source  = "coolify-terraform/coolify"
      version = "= 0.1.27"
    }
    cloudflare = {
      source  = "cloudflare/cloudflare"
      version = "~> 5.28"
    }
  }

  # Estado local (ignorado por git). Ver README → «Dónde guardar el estado» antes de usarlo en serio.
}
