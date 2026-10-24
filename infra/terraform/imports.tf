# Adopta lo que ya existe (terraform plan muestra "will be imported", nunca "will be created").
# Formato compuesto de Coolify: <project>:<server>:<entorno>:<uuid> (rellena project/server/entorno en el estado).

import {
  to = coolify_project.kuulis
  id = local.coolify.project_uuid
}

import {
  for_each = local.coolify.environments
  to       = coolify_environment.this[each.key]
  id       = "${local.coolify.project_uuid}:${each.value.name}"
}

import {
  for_each = local.applications
  to       = coolify_application_github_app.this[each.key]
  id       = "${local.coolify.project_uuid}:${local.coolify.servers[each.value.server]}:${local.coolify.environments[each.value.env].name}:${each.value.uuid}"
}

import {
  for_each = local.postgres
  to       = coolify_database_postgresql.this[each.key]
  id       = "${local.coolify.project_uuid}:${local.coolify.servers.localhost}:${local.coolify.environments[each.value.env].name}:${each.value.uuid}"
}

import {
  for_each = local.redis
  to       = coolify_database_redis.this[each.key]
  id       = "${local.coolify.project_uuid}:${local.coolify.servers.localhost}:${local.coolify.environments[each.value.env].name}:${each.value.uuid}"
}

import {
  for_each = local.postgres_backups
  to       = coolify_database_backup.postgres[each.key]
  id       = "${local.postgres[each.value.db].uuid}:${each.value.id}"
}

# ---------- Cloudflare ----------

import {
  to = cloudflare_zone.kuulis_com
  id = local.cloudflare.zones.kuulis_com
}

import {
  for_each = local.dns_kuulis_com
  to       = cloudflare_dns_record.kuulis_com[each.key]
  id       = "${local.cloudflare.zones.kuulis_com}/${each.value.id}"
}

import {
  for_each = local.dns_top8_email
  to       = cloudflare_dns_record.top8_email[each.key]
  id       = "${local.cloudflare.zones.top8_uk}/${each.value.id}"
}

import {
  for_each = var.manage_shared_dns ? local.dns_top8_shared : {}
  to       = cloudflare_dns_record.top8_shared[each.key]
  id       = "${local.cloudflare.zones.top8_uk}/${each.value.id}"
}

import {
  for_each = local.worker_domains
  to       = cloudflare_workers_custom_domain.web[each.key]
  id       = "${var.cloudflare_account_id}/${each.value.id}"
}

import {
  to = cloudflare_r2_bucket.backups
  id = "${var.cloudflare_account_id}/kuulis-backups/default"
}

# cloudflare_r2_bucket_lifecycle no admite import: ver var.manage_r2_lifecycle.

import {
  for_each = local.zone_settings
  to       = cloudflare_zone_setting.kuulis_com[each.key]
  id       = "${local.cloudflare.zones.kuulis_com}/${each.key}"
}

import {
  to = cloudflare_web_analytics_site.kuulis_com
  id = "${var.cloudflare_account_id}/${local.cloudflare.web_analytics_site_tag}"
}
