# Inventario de Kuulis en Coolify, leído de la API en solo lectura el 2026-10-24.
# Las variables de entorno se listan solo por NOMBRE: sus valores viven en Coolify y no se gestionan desde aquí.

locals {
  coolify = {
    project_uuid    = "cexs6860hwyfto1mwzjrsflw"
    github_app_uuid = "zkc08c4skokc4g80kww8oooc" # GitHub App privada de Carlos (acceso a carlozrodri/kuulis)
    repository      = "carlozrodri/kuulis"

    environments = {
      production = { name = "production", uuid = "g3jp0ktjp835d27ggn459ubo", branch = "main" }
      qa         = { name = "qa-env", uuid = "gnr61i6f23zj8obpqm2jj2z6", branch = "qa" } # Coolify no acepta nombres < 3 letras
    }

    # Servidores compartidos con otros proyectos del homelab: solo se leen (data sources), nunca se gestionan.
    servers = {
      localhost  = "rgs440ogg84kwcowo88cwkg8" # VM donde corre Coolify (8 núcleos, 10 GB RAM, 100 GB disco)
      pc_grande  = "dvartdzch1ddpiyfpizhqwvj" # 192.168.0.30, generador de carga (doc 18)
      node_1     = "e105cvf7llmr13mtdhvzbdcw" # 192.168.0.68, sin recursos de Kuulis
      dest_local = "h0c84k0gw8480co0cssk00og" # red Docker `coolify` del servidor localhost
    }

    # Almacenamiento S3 de Coolify para sus backups (MinIO del homelab, bucket `backups`). La API de Coolify no
    # lo expone para crear, así que se referencia por uuid.
    s3_storage_uuid = "k080sccg80wc4cwk4g0wg448"
  }

  # Variables comunes de API y worker (mismo Dockerfile, cambia PROCESS_TYPE).
  api_env_common = [
    "APP_ENV", "PROCESS_TYPE", "SECRET_KEY", "DATABASE_URL", "REDIS_URL", "RUN_MIGRATIONS",
    "AWS_ACCESS_KEY_ID", "AWS_SECRET_ACCESS_KEY", "AWS_S3_BUCKET", "AWS_S3_ENDPOINT", "STORAGE_PREFIX",
    "EMAIL_ENABLED", "EMAIL_FROM", "RESEND_API_KEY", "FRONTEND_URL", "PUBLIC_URL", "CORS_ORIGINS",
    "SENTRY_ENABLED",
  ]

  # Aplicaciones (build pack Dockerfile desde la GitHub App). Clave = nombre corto en Terraform.
  applications = {
    # ---------- QA (rama qa, entorno qa-env) ----------
    api_qa = {
      name          = "kuulis-api-qa"
      uuid          = "rayxgnveijwwq86tquloc3r8"
      description   = "Kuulis API (qa)"
      env           = "qa"
      server        = "localhost"
      base_dir      = "/api"
      dockerfile    = "/Dockerfile"
      port          = "8000"
      domains       = "https://kuulis-qa.top8.uk/api,https://admin.top8.uk/api,https://kuulis.top8.uk/api"
      watch_paths   = "api/**"
      auto_deploy   = true
      health_path   = "/health/live"
      health_port   = "8000"
      health        = { interval = 5, retries = 10, start = 30 }
      limits_memory = null
      aliases       = null
      env_names = concat(local.api_env_common, [
        "WEB_CONCURRENCY", "FIRST_SUPERUSER_EMAIL", "FIRST_SUPERUSER_PASSWORD", "OSRM_URL", "PHOTON_URL",
        "SENTRY_DSN", "ALERT_TELEGRAM_BOT_TOKEN", "BINANCE_API_KEY", "BINANCE_API_SECRET", "GOOGLE_CLIENT_IDS",
        "APPLE_CLIENT_IDS", "UPDATES_SIGNING_KEY", "MARKETING_S3_ACCESS_KEY_ID", "MARKETING_S3_BUCKET",
        "MARKETING_S3_SECRET_ACCESS_KEY", "SMOKE_ADMIN_EMAIL", "SMOKE_ADMIN_PASSWORD", "SMOKE_ADMIN_TOTP_SECRET",
        "LOG_FORWARDED_FOR",
      ])
    }
    worker_qa = {
      name          = "kuulis-worker-qa"
      uuid          = "i10vqipywxmdafk5sjaowzya"
      description   = "Kuulis background worker (qa)"
      env           = "qa"
      server        = "localhost"
      base_dir      = "/api"
      dockerfile    = "/Dockerfile"
      port          = "8000"
      domains       = "https://i10vqipywxmdafk5sjaowzya.top8.uk" # autogenerado por Coolify, no se usa
      watch_paths   = "api/**"
      auto_deploy   = true
      health_path   = null
      health_port   = null
      health        = { interval = 15, retries = 3, start = 30 }
      limits_memory = null
      aliases       = null
      env_names = concat(local.api_env_common, [
        "WORKER_CONCURRENCY", "DB_POOL_SIZE", "DB_MAX_OVERFLOW", "OSRM_URL", "PHOTON_URL", "SENTRY_DSN",
        "ALERT_TELEGRAM_BOT_TOKEN", "BINANCE_API_KEY", "BINANCE_API_SECRET", "GOOGLE_CLIENT_IDS",
        "APPLE_CLIENT_IDS", "BACKUP_ENABLED", "BACKUP_PASSPHRASE", "BACKUP_S3_ENDPOINT", "BACKUP_S3_BUCKET",
        "BACKUP_S3_ACCESS_KEY_ID", "BACKUP_S3_SECRET_ACCESS_KEY",
      ])
    }
    admin_qa = {
      name          = "kuulis-admin-qa"
      uuid          = "m37iqum9dy4n0o5281n0tvu5"
      description   = "Kuulis admin panel (qa)"
      env           = "qa"
      server        = "localhost"
      base_dir      = "/admin"
      dockerfile    = "/Dockerfile"
      port          = "3000"
      domains       = "https://kuulis-qa.top8.uk,https://admin.top8.uk"
      watch_paths   = "admin/**"
      auto_deploy   = true
      health_path   = "/"
      health_port   = "3000"
      health        = { interval = 5, retries = 10, start = 5 }
      limits_memory = null
      aliases       = null
      env_names     = ["NUXT_PUBLIC_API_BASE", "NUXT_PUBLIC_APP_ENV"]
    }
    web_qa = {
      name          = "Kuulis web"
      uuid          = "p4lpainpky5a5tf5oe9ggthm"
      description   = "Kuulis web publica"
      env           = "qa"
      server        = "localhost"
      base_dir      = "/web"
      dockerfile    = "/Dockerfile"
      port          = "3000"
      domains       = "https://kuulis.top8.uk,https://www.kuulis.top8.uk"
      watch_paths   = null # sin watch_paths: se redepliega con cualquier push a qa (ver docs/infra → hallazgos)
      auto_deploy   = true
      health_path   = null
      health_port   = null
      health        = { interval = 15, retries = 3, start = 20 }
      limits_memory = null
      aliases       = null
      env_names     = ["NUXT_PUBLIC_APP_ENV", "NUXT_PUBLIC_SITE_URL"]
    }
    expo_qa = {
      name          = "kuulis-expo-qa"
      uuid          = "d2gt6a6g8uan4kwghzrti478"
      description   = "Expo dev server for Expo Go (QA)"
      env           = "qa"
      server        = "localhost"
      base_dir      = "/mobile"
      dockerfile    = "/Dockerfile.expo"
      port          = "8081"
      domains       = "https://kuulis-expo.top8.uk"
      watch_paths   = "mobile/**"
      auto_deploy   = true
      health_path   = "/status"
      health_port   = "8081"
      health        = { interval = 5, retries = 10, start = 90 }
      limits_memory = null
      aliases       = null
      env_names     = ["EXPO_OWNER", "EXPO_TOKEN"]
    }
    builder_qa = {
      name          = "kuulis-builder-qa"
      uuid          = "txv8ffisp3r31rw819bjnxtk"
      description   = "Compila el APK de QA en el servidor y lo sube a S3 (builds/qa/)"
      env           = "qa"
      server        = "localhost"
      base_dir      = "/mobile"
      dockerfile    = "/builder/Dockerfile"
      port          = "8080"
      domains       = null # sin dominio público
      watch_paths   = "mobile/**"
      auto_deploy   = true
      health_path   = null
      health_port   = null
      health        = { interval = 30, retries = 3, start = 30 }
      limits_memory = null
      aliases       = null
      env_names     = ["EXPO_OWNER", "EXPO_TOKEN", "AWS_ACCESS_KEY_ID", "AWS_SECRET_ACCESS_KEY", "AWS_S3_BUCKET", "AWS_S3_ENDPOINT"]
    }
    builder_play = {
      name          = "kuulis-builder-play"
      uuid          = "77tord3ekdodttbsa7w04pfu"
      description   = null
      env           = "qa"
      server        = "localhost"
      base_dir      = "/mobile"
      dockerfile    = "/builder/Dockerfile"
      port          = "8080"
      domains       = null
      watch_paths   = "mobile/**"
      auto_deploy   = true
      health_path   = null
      health_port   = null
      health        = { interval = 30, retries = 3, start = 30 }
      limits_memory = null
      aliases       = null
      env_names = [
        "APP_ENV", "BUILD_PROFILE", "BUILD_NONCE", "EXPO_OWNER", "EXPO_TOKEN", "GOOGLE_PLAY_SERVICE_ACCOUNT_JSON",
        "AWS_ACCESS_KEY_ID", "AWS_SECRET_ACCESS_KEY", "AWS_S3_BUCKET", "AWS_S3_ENDPOINT",
      ]
    }
    osrm = {
      name          = "kuulis-osrm"
      uuid          = "nqbbvoaqqvzkthxeq6vts7zc"
      description   = null
      env           = "qa" # compartido por QA y producción (solo lectura, sin datos de usuarios)
      server        = "localhost"
      base_dir      = "/infra/osrm"
      dockerfile    = "/Dockerfile"
      port          = "5000"
      domains       = null
      watch_paths   = "infra/osrm/**"
      auto_deploy   = true
      health_path   = null
      health_port   = null
      health        = { interval = 30, retries = 3, start = 60 }
      limits_memory = "1536m"
      aliases       = "kuulis-osrm" # la API lo llama por este alias (el contenedor cambia de nombre al desplegar)
      env_names     = []
    }
    photon = {
      name          = "kuulis-photon"
      uuid          = "owcfbizidzhgftvwksyxqkis"
      description   = null
      env           = "qa"
      server        = "localhost"
      base_dir      = "/infra/photon"
      dockerfile    = "/Dockerfile"
      port          = "2322"
      domains       = null
      watch_paths   = "infra/photon/**"
      auto_deploy   = true
      health_path   = null
      health_port   = null
      health        = { interval = 30, retries = 3, start = 60 }
      limits_memory = "1g"
      aliases       = "kuulis-photon"
      env_names     = []
    }
    loadtest = {
      name          = "kuulis-loadtest"
      uuid          = "c86tdf34xkaz27ih1brik5ji"
      description   = "Generador de carga (doc 18)"
      env           = "qa"
      server        = "pc_grande" # el único recurso de Kuulis fuera del servidor localhost
      base_dir      = "/loadtest"
      dockerfile    = "/Dockerfile"
      port          = "8080"
      domains       = "https://kuulis-carga.top8.uk"
      watch_paths   = "loadtest/**"
      auto_deploy   = true
      health_path   = null
      health_port   = null
      health        = { interval = 30, retries = 10, start = 5 }
      limits_memory = null
      aliases       = null
      env_names     = ["BASE_URL", "TARGET_IP", "NODE_CPUS", "NODE_EXPORTER_URL", "PUSH_LATENCY_MS", "RUNNER_TOKEN", "LOADTEST_PASSWORD"]
    }

    # ---------- Producción (rama main, entorno production) — APAGADA desde 2026-10-09 ----------
    api_production = {
      name          = "kuulis-api-production"
      uuid          = "f14idkxf8c209b1hghrunmhb"
      description   = "Kuulis API (production)"
      env           = "production"
      server        = "localhost"
      base_dir      = "/api"
      dockerfile    = "/Dockerfile"
      port          = "8000"
      domains       = "https://kuulis-prod.top8.uk/api"
      watch_paths   = "api/**"
      auto_deploy   = false
      health_path   = "/health/live"
      health_port   = "8000"
      health        = { interval = 5, retries = 10, start = 30 }
      limits_memory = null
      aliases       = null
      env_names     = concat(local.api_env_common, ["WEB_CONCURRENCY", "FIRST_SUPERUSER_EMAIL", "FIRST_SUPERUSER_PASSWORD"])
    }
    worker_production = {
      name          = "kuulis-worker-production"
      uuid          = "f3eiht6l1r439xxp3401u2ur"
      description   = "Kuulis background worker (production)"
      env           = "production"
      server        = "localhost"
      base_dir      = "/api"
      dockerfile    = "/Dockerfile"
      port          = "8000"
      domains       = "https://f3eiht6l1r439xxp3401u2ur.top8.uk"
      watch_paths   = "api/**"
      auto_deploy   = false
      health_path   = null
      health_port   = null
      health        = { interval = 15, retries = 3, start = 30 }
      limits_memory = null
      aliases       = null
      env_names     = concat(local.api_env_common, ["WORKER_CONCURRENCY", "DB_POOL_SIZE", "DB_MAX_OVERFLOW"])
    }
    admin_production = {
      name          = "kuulis-admin-production"
      uuid          = "ru2e54bw4mn4igqvvdmkgrys"
      description   = "Kuulis admin panel (production)"
      env           = "production"
      server        = "localhost"
      base_dir      = "/admin"
      dockerfile    = "/Dockerfile"
      port          = "3000"
      domains       = "https://kuulis-prod.top8.uk"
      watch_paths   = "admin/**"
      auto_deploy   = false
      health_path   = "/"
      health_port   = "3000"
      health        = { interval = 5, retries = 10, start = 5 }
      limits_memory = null
      aliases       = null
      env_names     = ["NUXT_PUBLIC_API_BASE", "NUXT_PUBLIC_APP_ENV"]
    }
  }

  # Volúmenes persistentes (se documentan; los crea Coolify desde la app → Storages).
  volumes = {
    builder_qa   = { mount = "/cache", name = "txv8ffisp3r31rw819bjnxtk-kuulis-builder-cache", purpose = "caché de Gradle y npm" }
    builder_play = { mount = "/cache", name = "77tord3ekdodttbsa7w04pfu-77tord3ekdodttbsa7w04pfu-kuulis-builder-cache", purpose = "caché de Gradle y npm" }
  }

  postgres = {
    qa = {
      name          = "kuulis-postgres-qa"
      uuid          = "v12h71ber6ifhpgcugm6adth"
      description   = "Kuulis qa database"
      env           = "qa"
      limits_memory = "1536m"
      is_public     = true # puerto 3333 abierto en el servidor: ver docs/infra → hallazgos
      public_port   = 3333
    }
    production = {
      name          = "kuulis-postgres-production"
      uuid          = "pvx2gkfbo18zcld9x55t0tgp"
      description   = "Kuulis production database"
      env           = "production"
      limits_memory = "0"
      is_public     = false
      public_port   = null
    }
  }

  redis = {
    qa = {
      name          = "kuulis-redis-qa"
      uuid          = "miq3v8c99isk848ps719a7dn"
      description   = "Kuulis qa redis"
      env           = "qa"
      limits_memory = "768m"
    }
    production = {
      name          = "kuulis-redis-production"
      uuid          = "mgtsa16kwmktv0jl55belww8"
      description   = "Kuulis production redis"
      env           = "production"
      limits_memory = "0"
    }
  }

  # Backups programados de Coolify hacia el MinIO del homelab (además de los del worker hacia Cloudflare R2).
  postgres_backups = {
    qa         = { db = "qa", id = 4, uuid = "keypysvc878z535xi9j8g3e8", enabled = true, frequency = "0 3 * * *", days = 7 }
    production = { db = "production", id = 3, uuid = "jeqbjcit1tqutzu7abn8j020", enabled = false, frequency = "0 */6 * * *", days = 14 }
  }

  # Servicios de Coolify (plantillas de un clic) del entorno qa-env: solo lectura.
  services = {
    glitchtip     = { uuid = "ltics19o8wipo8ri1sxrkpog", purpose = "Errores (compatible con Sentry) en https://glitchtip.top8.uk" }
    node_exporter = { uuid = "adcd9mh42gvr11furlabnsl0", purpose = "Métricas del servidor para las pruebas de carga (doc 18)" }
  }
}
