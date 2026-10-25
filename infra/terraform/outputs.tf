# Resumen legible del inventario: `terraform output` (no incluye secretos).

output "coolify_applications" {
  description = "Apps de Kuulis en Coolify: entorno, rama, dominios, carpeta y variables por nombre."
  value = {
    for k, v in local.applications : v.name => {
      uuid        = v.uuid
      entorno     = local.coolify.environments[v.env].name
      rama        = local.coolify.environments[v.env].branch
      dominios    = v.domains
      carpeta     = v.base_dir
      watch_paths = v.watch_paths
      auto_deploy = v.auto_deploy
      variables   = sort(distinct(v.env_names))
    }
  }
}

output "coolify_databases" {
  description = "Bases de datos de Kuulis en Coolify."
  value = merge(
    { for k, v in local.postgres : v.name => { uuid = v.uuid, tipo = "postgres:17-alpine", entorno = local.coolify.environments[v.env].name } },
    { for k, v in local.redis : v.name => { uuid = v.uuid, tipo = "redis:7.4-alpine", entorno = local.coolify.environments[v.env].name } },
  )
}

output "coolify_services" {
  description = "Servicios de un clic (solo lectura)."
  value       = { for k, v in data.coolify_service.this : v.name => { uuid = v.uuid, estado = v.status, para = local.services[k].purpose } }
}

output "volumes" {
  value = local.volumes
}
