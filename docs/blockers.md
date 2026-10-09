# Bloqueos

| # | Bloqueo | Quién | Qué hay que hacer | Impacto |
| --- | --- | --- | --- | --- |
| 1 | Dominios en Nginx Proxy Manager | Carlos | Crear `kuulis-qa.top8.uk` y `kuulis-prod.top8.uk` como los demás hosts que ya funcionan (p. ej. `testqa.top8.uk`) apuntando al Traefik de Coolify, con **Websockets Support** activado. Hoy `kuulis-qa` responde 404 de Traefik y `kuulis-prod` error 525 de Cloudflare. | Sin esto no se puede abrir QA ni prod desde fuera |
| 2 | S3 en los backups de Postgres | Carlos | En Coolify → `kuulis-postgres-qa` y `kuulis-postgres-production` → Backups → activar "Save to S3" y elegir el S3 del homelab. La API de Coolify 4.1.2 no devuelve el identificador del S3, así que no se pudo hacer por API. | Los backups hoy solo quedan en el servidor |
| 3 | Cuenta Apple Developer | Carlos | Crear la cuenta (99 USD/año). | No hay builds de iOS para TestFlight/App Store ni push en iOS |
| 4 | Cuenta Google Play Console | Carlos | Crear la cuenta (25 USD pago único). | No hay publicación en Android |
| 5 | Proyecto EAS (Expo) | Carlos + Claude | `npx eas-cli init` con la cuenta de Expo de Carlos y guardar el `projectId` (`EAS_PROJECT_ID`). | Sin projectId no se generan tokens push |
| 6 | Definición del producto | Carlos | Explicar qué hace la app para empezar la Fase 1. | Las apps de dominio aún no existen |
