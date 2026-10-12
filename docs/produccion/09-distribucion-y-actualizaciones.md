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

## Decidido (2026-10-11)
1. La PWA para iPhone entra en el lanzamiento, solo para pasajeros (recomendado).
2. La copia del keystore de producción va al gestor de contraseñas de Carlos (recomendado).
3. Se entrega por partes: (1) versiones publicadas, aviso y actualización del APK dentro de la app,
   versión mínima obligatoria y página Versiones; (2) actualizaciones OTA con servidor propio y firma;
   (3) PWA para iPhone; el perfil de producción y su keystore quedan listos en la parte 1 pero no se compila
   producción mientras seguimos en desarrollo.
4. La versión mínima no es un número aparte: es la última versión **obligatoria** publicada en el canal.
   Marcar una versión como obligatoria bloquea los viajes de las anteriores; retirarla deshace el bloqueo.
5. (2026-10-12) Carlos decidió dejar la PWA para iPhone fuera por ahora: la parte 3 queda pospuesta y el
   doc 09 se cierra con las partes 1 y 2.

## Cómo quedó
### Parte 1 (2026-10-11)
- El compilador (`mobile/builder`) sube cada APK con un archivo de datos al lado: versión, número de build
  (`versionCode`), tamaño, SHA-256 y MD5. El perfil `qa` sube el número de build en cada compilación
  (`autoIncrement`); el perfil `production` ahora genera APK.
- API (`apps/releases`): tabla `app_releases`; `GET /app/version` (sin sesión) dice cuál es el APK más
  reciente del canal, la build mínima y si hay que actualizar; `GET /app/download` redirige al APK más
  reciente (lo usa la web). Pedir viaje, aceptar viaje y conectarse responden **426
  `app_update_required`** si la build de la app es menor que la mínima; el resto de la app sigue
  funcionando. La app manda `X-App-Platform`, `X-App-Version`, `X-App-Build` y `X-App-Channel` en cada
  petición, y `GET /users/me` cuenta cuántas personas usan cada build (últimos 7 días, en Redis).
- Admin: página **Versiones** (permisos `releases.view` y `releases.manage`): compilaciones disponibles,
  publicar una en un canal con notas y si es obligatoria, retirar (vuelve a ofrecerse la anterior) y uso por
  build.
- App: aviso «Hay una versión nueva», pantalla bloqueante «Necesitas actualizar» (no interrumpe un viaje en
  curso), descarga del APK con progreso, comprobación del tamaño y del MD5 antes de abrir el instalador de
  Android, y **Perfil → Acerca de** con versión, build, canal y «Buscar actualizaciones».
- Web: la página Descargar muestra el APK publicado con su versión, tamaño, fecha y huella SHA-256.
- El primer APK con este código hay que instalarlo a mano (las versiones anteriores no saben actualizarse).

### Parte 2 (2026-10-12)
- El servidor de actualizaciones es la propia API (no un servicio aparte): `GET /api/v1/updates/manifest`
  implementa el protocolo Expo Updates v1 y firma cada manifiesto (RSA SHA-256) con `UPDATES_SIGNING_KEY`.
  La app lleva el certificado (`mobile/certs/updates-<entorno>.pem`) y rechaza lo que no venga firmado con esa
  clave. Los archivos se sirven con enlaces firmados de S3.
- `runtimeVersion` con la política `fingerprint`: una OTA solo llega a APKs con el mismo código nativo. El
  compilador calcula esa huella; si ya hay un APK con ella, exporta una OTA en vez de compilar.
- Tabla `app_updates` (aparte de `app_releases`): canal, runtime, porcentaje, retirada y de qué reversión
  viene. Admin **Versiones → Actualizaciones de JS**: publicar una candidata en un canal con porcentaje,
  pausar, ampliar, cambiar el porcentaje, revertir, y cuántos usuarios usan cada OTA (cabecera
  `X-App-Update`).
- Porcentaje estable por teléfono (id de instalación de `expo-updates` mezclado con el id de la OTA).
  Revertir publica una copia más nueva de la anterior o, si no hay, manda a las apps al código del APK
  (`rollBackToEmbedded`).
- App: busca OTA al abrir y la aplica al volver a abrir; nunca se reinicia sola. «Hay una mejora lista ·
  Reiniciar» y el botón de **Acerca de** solo funcionan sin viaje activo y con el motorizado desconectado.
  Acerca de muestra la actualización en uso (id corto y fecha, o «Incluida en la app»).
- Producción queda sin OTA hasta crear su clave (sin certificado la app compila con las OTA apagadas).
- Las apps instaladas antes de esta parte necesitan el APK nuevo para recibir OTA.
