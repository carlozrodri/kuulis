# Bloqueos

| # | Bloqueo | Quién | Qué hay que hacer | Impacto |
| --- | --- | --- | --- | --- |
| 2 | S3 en los backups de Postgres | Carlos | En Coolify → `kuulis-postgres-qa` y `kuulis-postgres-production` → Backups → activar "Save to S3" y elegir el S3 del homelab. La API de Coolify 4.1.2 no devuelve el identificador del S3, así que no se pudo hacer por API. | Los backups hoy solo quedan en el servidor |
| 3 | Cuenta Apple Developer | Carlos | Crear la cuenta (99 USD/año). | No hay builds de iOS, push en iOS ni "Iniciar sesión con Apple" (solo se puede probar en Expo Go) |
| 4 | Cuenta Google Play Console | Carlos | Crear la cuenta (25 USD pago único). | No hay publicación en Android |
| 7 | Credenciales de Google Sign-In | Carlos + Claude | En Google Cloud Console crear un proyecto y clientes OAuth: Web, Android (con el SHA-1 del build) e iOS. El id Web va en `GOOGLE_CLIENT_IDS` de la API y en `EXPO_PUBLIC_GOOGLE_WEB_CLIENT_ID`; el de iOS en `EXPO_PUBLIC_GOOGLE_IOS_CLIENT_ID`. | El botón de Google queda oculto; además necesita una build instalada (no funciona en Expo Go) |
| 8 | Rotar el token de Expo | Carlos | Crear un token nuevo en expo.dev, ponerlo en Coolify (`kuulis-expo-qa` → `EXPO_TOKEN`) y borrar el anterior, que quedó en el chat. | Seguridad |
| 10 | Cuenta de Binance de Kuulis | Carlos | Crear (o elegir) la cuenta de Binance que recibe las recargas. En el admin → Ajustes poner su Binance Pay ID. Para que las recargas se acrediten solas: en Binance → Gestión de API crear una clave **solo de lectura** (sin retiros ni trading, idealmente restringida por IP al servidor) y ponerla en Coolify en `kuulis-api-qa` y `kuulis-worker-qa` como `BINANCE_API_KEY` y `BINANCE_API_SECRET`. | Sin el Pay ID no se puede recargar; sin la clave, cada recarga se confirma a mano en el admin |

## Resueltos
- 1 · Dominios en Nginx Proxy Manager (2026-10-09).
- 5 · Proyecto EAS y token en Coolify (2026-10-09).
- 6 · Definición del producto (2026-10-09, ver `docs/product/`).
- 9 · WebSockets en el proxy (2026-10-09): qa y expo responden 101; prod se comprueba al encenderlo.
