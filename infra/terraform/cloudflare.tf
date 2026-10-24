# Cloudflare (cuenta de Carlos): zona kuulis.com, los registros de top8.uk que usa Kuulis, el dominio de la web
# pública en Workers, el bucket R2 de backups y Web Analytics. Leído en solo lectura el 2026-10-24.
#
# Fuera de Terraform a propósito:
#  - El código del Worker `kuulis`: lo despliega Workers Builds con `npx wrangler deploy` (web/wrangler.jsonc).
#    Sus variables NUXT_* viven en el panel (keep_vars) y se documentan en docs/infra.
#  - Los AAAA 100:: de kuulis.com y www: los crea y borra el dominio personalizado del Worker (solo lectura).
#  - El resto de top8.uk (otros proyectos del homelab, correo personal, Vercel).

locals {
  cloudflare = {
    zones = {
      kuulis_com = "85897612bc9480dfb69b72c2095fbe73"
      top8_uk    = "083bc15fa415dc4556ba154e188dc7c4"
    }
    homelab_ip             = "81.202.2.12" # IP pública de casa de Carlos (Nginx Proxy Manager)
    web_analytics_site_tag = "1c49d9f5228344d98da5f7e1e1879738"
  }

  dns_kuulis_com = {
    wildcard = { id = "3fbdf32dcfdeed2d2923b851db72a5a6", type = "A", name = "*.kuulis.com", content = local.cloudflare.homelab_ip, proxied = true, priority = null }
    # Correo de IONOS (buzones @kuulis.com).
    mx00          = { id = "547494e265520a85522d24110b1bd777", type = "MX", name = "kuulis.com", content = "mx00.ionos.es", proxied = false, priority = 10 }
    mx01          = { id = "ca9887e7e63f614a0f282c769cd3fbdf", type = "MX", name = "kuulis.com", content = "mx01.ionos.es", proxied = false, priority = 10 }
    spf           = { id = "78e8e56cd33c08a6e8901f2d9e3aaea8", type = "TXT", name = "kuulis.com", content = "\"v=spf1 include:_spf-eu.ionos.com ~all\"", proxied = false, priority = null }
    dmarc         = { id = "5dbfb79a93261c0d07918274d9f4365d", type = "CNAME", name = "_dmarc.kuulis.com", content = "dmarc.ionos.es", proxied = true, priority = null }
    autodiscover  = { id = "52dca61013a0206af1dde293a1a4a9b6", type = "CNAME", name = "autodiscover.kuulis.com", content = "adsredir.ionos.info", proxied = true, priority = null }
    domainconnect = { id = "836406bce04f0c713843e512b2ac0253", type = "CNAME", name = "_domainconnect.kuulis.com", content = "_domainconnect.ionos.com", proxied = true, priority = null }
  }

  # Dominio de envío de Resend (no-reply@email.top8.uk).
  dns_top8_email = {
    resend_dkim = { id = "157f8da98f3ad9a02097e184bf53f949", type = "TXT", name = "resend._domainkey.email.top8.uk", content = "\"p=MIGfMA0GCSqGSIb3DQEBAQUAA4GNADCBiQKBgQDHvNlSvHRSH2+pkkTb7k2/NTFBOEk5/tdnU2xDWlo3g9oK2GVAqtBp4+VSUJblI4EAKS1Lpc+CjiOZq7e7rCASn5+holj7QSMe0zygc8Asfkbnczps/yJpKGOkyOYL0aBtujx3amGw2WbG34t3hz+A9Fcmc6qd6hijhdUlNzTEmwIDAQAB\"", ttl = 3600, priority = null }
    send_mx     = { id = "3a7bf15d81d7b4ba68c137d123a29729", type = "MX", name = "send.email.top8.uk", content = "feedback-smtp.eu-west-1.amazonses.com", ttl = 3600, priority = 10 }
    send_spf    = { id = "40f21b8483bdc9f232e47409f1cbebef", type = "TXT", name = "send.email.top8.uk", content = "\"v=spf1 include:amazonses.com ~all\"", ttl = 3600, priority = null }
  }

  # Comodín del homelab: sirve kuulis-qa, admin, kuulis, kuulis-expo, s3, glitchtip, kuulis-carga… y también
  # los demás proyectos de Carlos. Solo se adopta con manage_shared_dns = true.
  dns_top8_shared = {
    wildcard = { id = "2dade6f493605dc563cb7c4a3850ef7a", type = "A", name = "*.top8.uk", content = local.cloudflare.homelab_ip, comment = "wildcard" }
  }

  worker_domains = {
    apex = { id = "f693a58d84e5e63619c1cd37ece34520a4f30e04", hostname = "kuulis.com" }
    www  = { id = "a7b4dcd67f07cd0549ded0fdd7ce257f9732e081", hostname = "www.kuulis.com" }
  }

  # Ajustes de la zona kuulis.com tal como están hoy (ver docs/infra → hallazgos para los que convendría subir).
  zone_settings = {
    ssl                      = "full"
    always_use_https         = "off"
    min_tls_version          = "1.0"
    tls_1_3                  = "on"
    automatic_https_rewrites = "on"
    http3                    = "on"
    websockets               = "on"
    brotli                   = "on"
    security_level           = "medium"
    browser_check            = "on"
  }
}

resource "cloudflare_zone" "kuulis_com" {
  account = { id = var.cloudflare_account_id }
  name    = "kuulis.com"
  type    = "full"

  lifecycle {
    prevent_destroy = true
  }
}

resource "cloudflare_dns_record" "kuulis_com" {
  for_each = local.dns_kuulis_com

  zone_id  = local.cloudflare.zones.kuulis_com
  type     = each.value.type
  name     = each.value.name
  content  = each.value.content
  proxied  = each.value.proxied
  priority = each.value.priority
  ttl      = 1

  lifecycle {
    prevent_destroy = true
  }
}

resource "cloudflare_dns_record" "top8_email" {
  for_each = local.dns_top8_email

  zone_id  = local.cloudflare.zones.top8_uk
  type     = each.value.type
  name     = each.value.name
  content  = each.value.content
  priority = each.value.priority
  proxied  = false
  ttl      = each.value.ttl

  lifecycle {
    prevent_destroy = true
  }
}

resource "cloudflare_dns_record" "top8_shared" {
  for_each = var.manage_shared_dns ? local.dns_top8_shared : {}

  zone_id = local.cloudflare.zones.top8_uk
  type    = each.value.type
  name    = each.value.name
  content = each.value.content
  comment = each.value.comment
  proxied = true
  ttl     = 1

  lifecycle {
    prevent_destroy = true
  }
}

resource "cloudflare_workers_custom_domain" "web" {
  for_each = local.worker_domains

  account_id = var.cloudflare_account_id
  zone_id    = local.cloudflare.zones.kuulis_com
  hostname   = each.value.hostname
  service    = "kuulis"

  lifecycle {
    prevent_destroy = true
  }
}

# Backups cifrados del worker (api/apps/backups): <entorno>/postgres/{recent,daily}/, ledger/, files/.
resource "cloudflare_r2_bucket" "backups" {
  account_id = var.cloudflare_account_id
  name       = "kuulis-backups"

  lifecycle {
    prevent_destroy = true
  }
}

# Sin import en el proveedor: crearlo reescribe las reglas (un PUT con las mismas). Opt-in.
resource "cloudflare_r2_bucket_lifecycle" "backups" {
  count = var.manage_r2_lifecycle ? 1 : 0

  account_id  = var.cloudflare_account_id
  bucket_name = cloudflare_r2_bucket.backups.name

  rules = [
    {
      id         = "Default Multipart Abort Rule"
      enabled    = true
      conditions = { prefix = "" }
      abort_multipart_uploads_transition = {
        condition = { type = "Age", max_age = 604800 } # 7 días
      }
    },
    {
      id         = "Ledger"
      enabled    = true
      conditions = { prefix = "qa/ledger/" }
      delete_objects_transition = {
        condition = { type = "Age", max_age = 7776000 } # 90 días
      }
    },
    {
      id         = "Postgres Daily"
      enabled    = true
      conditions = { prefix = "qa/postgres/daily/" }
      delete_objects_transition = {
        condition = { type = "Age", max_age = 1209600 } # 14 días
      }
    },
    {
      id         = "Postgres Recent"
      enabled    = true
      conditions = { prefix = "qa/postgres/recent/" }
      delete_objects_transition = {
        condition = { type = "Age", max_age = 172800 } # 2 días
      }
    },
  ]
}

resource "cloudflare_zone_setting" "kuulis_com" {
  for_each = local.zone_settings

  zone_id    = local.cloudflare.zones.kuulis_com
  setting_id = each.key
  value      = each.value
}

resource "cloudflare_web_analytics_site" "kuulis_com" {
  account_id   = var.cloudflare_account_id
  zone_tag     = local.cloudflare.zones.kuulis_com
  auto_install = true
}
