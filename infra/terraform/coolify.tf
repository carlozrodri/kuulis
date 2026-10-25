# Kuulis en Coolify: proyecto, entornos, apps, bases, backups.
#
# Todo lleva `prevent_destroy`: un plan que quiera borrar o reemplazar algo falla en vez de ejecutarse.
# Las contraseñas de las bases y los valores de las variables de entorno NO se gestionan desde aquí.

data "coolify_server" "this" {
  for_each = { for k, v in local.coolify.servers : k => v if k != "dest_local" }
  uuid     = each.value
}

data "coolify_service" "this" {
  for_each = local.services
  uuid     = each.value.uuid
}

resource "coolify_project" "kuulis" {
  name        = "kuulis"
  description = "Kuulis monorepo - API, admin, Postgres, Redis"

  lifecycle {
    prevent_destroy = true
  }
}

resource "coolify_environment" "this" {
  for_each     = local.coolify.environments
  project_uuid = coolify_project.kuulis.uuid
  name         = each.value.name

  lifecycle {
    prevent_destroy = true
  }
}

resource "coolify_application_github_app" "this" {
  for_each = local.applications

  name             = each.value.name
  description      = each.value.description
  project_uuid     = local.coolify.project_uuid
  server_uuid      = local.coolify.servers[each.value.server]
  environment_name = local.coolify.environments[each.value.env].name
  github_app_uuid  = local.coolify.github_app_uuid
  git_repository   = "https://github.com/${local.coolify.repository}"
  git_branch       = local.coolify.environments[each.value.env].branch

  build_pack          = "dockerfile"
  base_directory      = each.value.base_dir
  dockerfile_location = each.value.dockerfile
  ports_exposes       = each.value.port
  domains             = each.value.domains
  autogenerate_domain = false
  watch_paths         = each.value.watch_paths

  is_auto_deploy_enabled = each.value.auto_deploy
  is_force_https_enabled = true
  redirect               = "both"

  health_check_enabled = each.value.health_path != null
  health_check_path    = coalesce(each.value.health_path, "/")
  health_check_port    = each.value.health_port
  # Valores actuales de Coolify (el proveedor tiene otros por defecto y propondría cambiarlos).
  health_check_interval     = each.value.health.interval
  health_check_retries      = each.value.health.retries
  health_check_start_period = each.value.health.start

  limits_memory          = each.value.limits_memory
  custom_network_aliases = each.value.aliases

  lifecycle {
    prevent_destroy = true
    # Valores que Coolify no devuelve o que solo existen al crear.
    ignore_changes = [autogenerate_domain, github_app_uuid]
  }
}

resource "coolify_database_postgresql" "this" {
  for_each = local.postgres

  name             = each.value.name
  description      = each.value.description
  project_uuid     = local.coolify.project_uuid
  server_uuid      = local.coolify.servers.localhost
  environment_name = local.coolify.environments[each.value.env].name
  image            = "postgres:17-alpine"
  postgres_db      = "kuulis"
  postgres_user    = "kuulis"
  limits_memory    = each.value.limits_memory
  is_public        = each.value.is_public
  public_port      = each.value.public_port

  lifecycle {
    prevent_destroy = true
    # postgresql.conf ajustado (docs/deployment.md) y contraseña: se cambian en Coolify, no aquí.
    ignore_changes = [postgres_conf, postgres_password]
  }
}

resource "coolify_database_redis" "this" {
  for_each = local.redis

  name             = each.value.name
  description      = each.value.description
  project_uuid     = local.coolify.project_uuid
  server_uuid      = local.coolify.servers.localhost
  environment_name = local.coolify.environments[each.value.env].name
  image            = "redis:7.4-alpine"
  limits_memory    = each.value.limits_memory

  lifecycle {
    prevent_destroy = true
    ignore_changes  = [redis_conf, redis_password]
  }
}

resource "coolify_database_backup" "postgres" {
  for_each = local.postgres_backups

  database_uuid       = local.postgres[each.value.db].uuid
  enabled             = each.value.enabled
  frequency           = each.value.frequency
  databases_to_backup = "kuulis"
  save_s3             = true
  s3_storage_uuid     = local.coolify.s3_storage_uuid
  retain_days_locally = each.value.days
  timeout             = 3600

  lifecycle {
    prevent_destroy = true
  }
}
