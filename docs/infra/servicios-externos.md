# Servicios externos y piezas sin Terraform

Lo que Kuulis usa fuera de Coolify y Cloudflare, o que no se gestiona con Terraform. Solo nombres de secretos;
los valores están en la cuenta de cada servicio, en Coolify o en el gestor de contraseñas de Carlos.
Mapa general: [README.md](README.md).

| Servicio | Para qué | Dónde se configura | Secretos (nombre → dónde) | Qué hace Carlos a mano |
| --- | --- | --- | --- | --- |
| **GitHub** `carlozrodri/kuulis` | Código, PRs, CI (`.github/workflows/ci.yml`, check `ci`) | github.com | GitHub App de Coolify (instalada en el repo) | Protección de ramas `qa`/`main` (pendiente) |
| **Expo / EAS** | Builds Android (en el servidor con `eas build --local`), credenciales, variables de build | expo.dev, proyecto `91bc2a11-022d-4f60-81bf-32eeba5384ba`, slug `kuulis`, perfiles en `mobile/eas.json` (`qa`, `qa-dev`, `production`, `play`) | `EXPO_TOKEN`, `EXPO_OWNER` → Coolify (expo-qa, builders); keystores de `uk.top8.kuulis.qa` y `com.kuulis.app` → EAS | Variables de los entornos de EAS (p. ej. `GOOGLE_MAPS_ANDROID_API_KEY`, `EXPO_PUBLIC_GOOGLE_WEB_CLIENT_ID`), copia del keystore, **rotar el token** pegado en un chat |
| **Expo Push** | Envío de push (el worker llama al servicio de Expo, que entrega por FCM) | — | — | — |
| **Firebase** `kuulis-f06c0` | FCM para Android | console.firebase.google.com; `mobile/google-services.qa.json` y `google-services.production.json` (públicos, van en el APK) | — | Añadir huellas SHA-1 de nuevos builds |
| **Google Cloud** proyecto `kuulis` | OAuth (Google Sign-In), Maps SDK Android, cuenta de servicio de Play | console.cloud.google.com | Cliente OAuth Web/Android (ids → `GOOGLE_CLIENT_IDS` en API y EAS); clave de Maps → EAS; JSON de `kuulis-play@kuulis.iam.gserviceaccount.com` → `GOOGLE_PLAY_SERVICE_ACCOUNT_JSON` en `kuulis-builder-play` | Crear clientes y restringir claves por SHA-1; **rotar** el secreto del cliente Web y la clave JSON (se pegaron en un chat) |
| **Google Play Console** | Distribución de `com.kuulis.app` (cuenta personal) | play.google.com/console; pistas interna (versión 6) y cerrada «Kuulis QA» (borrador) | Firma de apps de Google (SHA-1 en Google Cloud y Firebase) | Subir el `.aab`, enviar la prueba cerrada a revisión, invitar 12 testers, ficha, data safety |
| **Apple** | iOS, Sign in with Apple | — | `APPLE_CLIENT_IDS` (ids públicos) en API/worker | Crear cuenta Apple Developer (bloqueo 3) |
| **Resend** | Email transaccional (verificación, contraseña, invitaciones, alertas) desde `no-reply@email.top8.uk` | resend.com; DNS en Cloudflare (DKIM, MX y SPF de `send.email.top8.uk`, en Terraform) | `RESEND_API_KEY` → API y worker (misma en QA y prod) | Rotar la clave |
| **MinIO** del homelab (`s3.top8.uk`, `192.168.0.210:9000`) | Archivos de la app (documentos, avatares, APK, OTA, marketing) y backups de Coolify | Consola de MinIO; proxy host en NPM con **Cache Assets apagado** | `AWS_*` y `STORAGE_PREFIX` → API, worker, builders (misma clave en QA y prod, pendiente separarla); `MARKETING_S3_*` → API QA; credenciales del S3 de Coolify → Coolify | Buckets, claves por entorno |
| **Cloudflare R2** `kuulis-backups` | Copia fuera de casa: dumps cada 15 min, libro contable, archivos | En Terraform (bucket); token en el panel | `BACKUP_S3_*`, `BACKUP_PASSPHRASE` → worker QA (y gestor de contraseñas) | Reglas de bloqueo y de `production/`, token de prod |
| **Nginx Proxy Manager** (192.168.0.148, IP pública 81.202.2.12) | TLS público y entrada a Traefik | UI de NPM en el homelab | — | Un proxy host por dominio con Websockets: `kuulis-qa`, `kuulis-prod`, `admin`, `kuulis`, `www.kuulis`, `kuulis-expo`, `kuulis-carga`, `glitchtip`, `s3` (`.top8.uk`) |
| **Traefik** (proxy de Coolify) | Enruta por dominio a cada contenedor | Coolify → Servers → localhost → Proxy | — | Si se regenera la configuración, volver a poner `trustedIPs=192.168.0.148/32` en `http` y `https` |
| **GlitchTip** (Coolify) | Errores tipo Sentry | `glitchtip.top8.uk` | `SENTRY_DSN` → API y worker; `SENTRY_ENABLED` | Activarlo por entorno |
| **Telegram** `@Kuulis_bot` | Alertas del monitoreo | BotFather | `ALERT_TELEGRAM_BOT_TOKEN` (opcional `ALERT_TELEGRAM_CHAT_ID`) → API y worker | `/revoke` si se filtra |
| **UptimeRobot** | Monitor externo de `/api/health/live` de QA | uptimerobot.com | — | Añadir producción al encenderla |
| **Binance Pay** | Recargas de billetera (confirmación manual + lectura de la API) | binance.com | `BINANCE_API_KEY`, `BINANCE_API_SECRET` (solo lectura) → API y worker QA | Cuenta de producción |
| **IONOS** | Registrador de `kuulis.com` y buzones `@kuulis.com` | ionos.es | — | Renovación del dominio |
| **Vercel / Railway / MailerSend** | Otros proyectos de Carlos en `top8.uk`, no Kuulis | — | — | — |

## Claves de firma de la app

| Clave | Dónde | Notas |
| --- | --- | --- |
| Keystore de `uk.top8.kuulis.qa` | EAS | SHA-1 en Firebase y Google Cloud |
| Llave de subida de `com.kuulis.app` | EAS (la creó el primer build en la nube) | Google firma con su propia clave (Play App Signing) |
| Firma de OTA | Certificado en `mobile/certs/updates-<entorno>.pem` (repo); privada `UPDATES_SIGNING_KEY` en la API QA y en el gestor de Carlos | Producción aún sin clave |

## Ideas para más adelante

- Un contenedor en Coolify que corra `terraform plan` cada noche y avise por Telegram si la infraestructura se
  aleja de lo documentado. No hace falta hoy: Carlos pidió primero solo código y documentación.
- Proveedores que existen pero no compensan aún: GitHub (`integrations/github`, para protección de ramas) y
  Google (`hashicorp/google`, para claves y cuentas de servicio). Se pueden añadir cuando haya producción.
