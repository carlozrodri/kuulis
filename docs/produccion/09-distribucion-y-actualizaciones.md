# 09 · Distribución y actualizaciones sin tiendas

**Prioridad:** P0 · **Área:** Mobile · Infra · **Depende de:** 08

## Objetivo
Que cualquier persona pueda instalar Kuulis **sin App Store ni Google Play**, que reciba actualizaciones de
forma segura y automática, y que podamos obligar a actualizar cuando una versión vieja ya no sirve. Incluye una
vía para los pasajeros con iPhone.

## Estado actual
- Builds de Android para QA: APK con EAS local en el servidor (`kuulis-builder-qa`, sube a S3) y build de
  desarrollo `qa-dev` que carga el JS del servidor Expo de QA.
- **No hay perfil de producción** en el compilador ni firma de producción documentada.
- **No hay `expo-updates`**: hoy no existe forma de entregar una versión nueva a usuarios que ya instalaron.
- No hay control de versión mínima.
- iOS no se puede instalar sin cuenta de Apple (bloqueo 3). La app ya compila para web (`RideMap.web.tsx`).

## Alcance
### Incluye
1. **APK de producción firmado**: perfil `production` en `eas.json` (APK, no AAB), keystore de producción
   guardado en EAS y con copia cifrada fuera de EAS (perderlo impide actualizar la app instalada). El
   compilador de Coolify gana un servicio de producción o un parámetro de perfil. Nombre del archivo con
   versión, publicado en S3/CDN con SHA-256.
2. **Actualizaciones OTA de JS** con `expo-updates` y un **servidor de actualizaciones propio** (protocolo de
   Expo Updates, implementación de referencia `custom-expo-updates-server`) en Coolify, con artefactos en S3.
   EAS Update gratis solo cubre ~1000 usuarios activos al mes, por eso autoalojado.
   - Firma de código de las actualizaciones (certificado propio) para que nadie pueda inyectar JS.
   - Canales `qa` y `production`; `runtimeVersion` por versión nativa para no mandar JS incompatible.
   - Despliegue progresivo (porcentaje) y rollback a la actualización anterior.
   - Script `scripts/publish_update.sh` y documentación en `docs/deployment.md`.
3. **Actualización nativa dentro de la app** (cuando cambia algo nativo): la app consulta la versión más
   reciente del APK; si hay una nueva, muestra un aviso con "Actualizar", descarga el APK y abre el instalador
   de Android (`REQUEST_INSTALL_PACKAGES`). Verifica la firma/huella antes de instalar.
4. **Versión mínima obligatoria**: si la versión instalada es menor que la mínima, pantalla bloqueante "Necesitas
   actualizar" (con excepción: un viaje activo se termina primero).
5. **Vía para iPhone**: la app web (Expo web) como **PWA para pasajeros** en `app.<dominio>`, instalable en la
   pantalla de inicio, con notificaciones Web Push (iOS 16.4+), sin modo motorizado (necesita ubicación en
   segundo plano). Revisar las pantallas que hoy usan APIs nativas (mapas, selector de archivos) y ofrecer
   equivalentes web (el mapa web ya existe).
6. **Avisos de seguridad de Android**: guía en la web (08) para "instalar apps desconocidas" y Play Protect.
   Riesgo a vigilar: Google anunció la verificación obligatoria de desarrolladores también para apps instaladas
   fuera de Play (por fases desde 2026); puede exigir una cuenta de desarrollador verificada aunque no se
   publique en la tienda.
7. **Canal de beta**: grupo de motorizados y pasajeros de confianza en el canal `beta` antes de producción.

### Fuera
- Publicación en App Store y Google Play (decidido: fuera de este plan).
- Tiendas alternativas (APKPure, Uptodown, F-Droid); se pueden evaluar después.

## App móvil
### Pasajero y motorizado
- Al abrir: comprueba OTA en segundo plano y aplica en el siguiente arranque (sin interrumpir un viaje).
- Aviso no bloqueante "Hay una versión nueva" y pantalla bloqueante si es obligatoria.
- Perfil → Acerca de: versión nativa, versión de la actualización (id corto), canal, botón "Buscar
  actualizaciones".
### Motorizado
- Nunca se reinicia la app por una OTA mientras está conectado o en un viaje.

## Admin
- **Versiones**: lista de APKs publicados y actualizaciones OTA por canal, con fecha, commit, porcentaje de
  despliegue, cuántos usuarios hay en cada versión (desde `X-App-Version` de las peticiones) y botones de
  pausar, ampliar al 100 % o revertir.
- Fijar la **versión mínima** por plataforma (Android, web) y el texto del aviso.

## API y datos
- Tabla `app_releases` (`platform`, `kind` apk|ota, `version`, `runtime_version`, `channel`, `file_key`,
  `sha256`, `rollout_percent`, `published_at`, `is_mandatory`).
- `GET /app/version?platform&version&channel` → `{latest, minimum, download_url, sha256, mandatory, notes}`.
- La app envía `X-App-Version` y `X-App-Platform` en cada petición (se guardan agregados para el admin).
- Servidor de actualizaciones: servicio separado `kuulis-updates` (manifiestos firmados, assets en S3).
- Si `X-App-Version` < mínima, la API responde 426 `app_update_required` en endpoints de viaje (el resto sigue).

## Criterios de aceptación
- Un usuario con el APK 1.0.0 recibe un cambio de texto por OTA al reabrir la app, sin reinstalar.
- Una OTA con firma inválida es rechazada por la app.
- Al subir la versión mínima, una app vieja muestra la pantalla de actualizar, descarga e instala el APK nuevo.
- Una OTA desplegada al 10 % llega a ~10 % de los dispositivos y se puede revertir desde el admin.
- Un pasajero con iPhone puede instalar la PWA, pedir un viaje y recibir una notificación de "motorizado
  asignado".

## Dependencias
08 (página de descarga). 10 reutiliza el control de versión mínima.

## Preguntas para Carlos
1. ¿La PWA para iPhone entra en el lanzamiento o después? Recomendado: en el lanzamiento, solo pasajeros.
2. ¿Dónde guardamos la copia del keystore de producción? Recomendado: gestor de contraseñas de Carlos.
