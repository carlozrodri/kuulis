# 10 · Control remoto de la app

**Prioridad:** P0 · **Área:** API · Mobile · Admin · **Depende de:** 09

## Objetivo
Poder reaccionar sin publicar código: poner la app en mantenimiento, apagar una función que falla, avisar a
todos con un banner y activar funciones poco a poco.

## Estado actual
- `AppConfig` en `app_settings` ya permite cambiar tarifas, ciudades, métodos de pago, tiempos de despacho,
  requisitos del motorizado, etc., desde el admin.
- No hay modo mantenimiento, ni banners, ni interruptores de funciones, ni lanzamiento progresivo.

## Alcance
### Incluye
1. **Modo mantenimiento** (global o por ciudad): bloquea pedir viajes y conectarse como motorizado, con mensaje
   y hora estimada; los viajes en curso continúan. El admin y la API de health siguen funcionando.
2. **Pausa de pedidos por ciudad** (por ejemplo, lluvia fuerte, protestas, toque de queda): igual que
   mantenimiento pero con mensaje propio y sin afectar al resto.
3. **Interruptores de funciones** (feature flags) con valor por defecto, por plataforma, por versión mínima,
   por ciudad, por rol y por porcentaje de usuarios (hash estable del id). Ejemplos iniciales: `chat`,
   `promotions`, `transfers`, `binance_auto`, `share_live_link`, `pwa_passengers`.
4. **Banners y anuncios** en la app: título, texto, enlace o pantalla destino, fechas, audiencia (pasajeros,
   motorizados, ciudad), estilo (info, aviso, promoción) y si se puede cerrar.
5. **Configuración remota de la app**: textos de soporte (WhatsApp/email de soporte), número de emergencias,
   enlaces legales, intervalos de envío de ubicación, para no depender de una OTA.

### Fuera
- Experimentos A/B con estadística (se evalúa con 19).

## App móvil
### Pasajero y motorizado
- Al abrir y cada 5 min (o por evento WebSocket `config.updated`) se lee `GET /app/bootstrap`.
- Pantalla de mantenimiento con ilustración, mensaje y hora estimada; reintenta sola.
- Banner en la parte superior de la pantalla principal; los banners cerrados no vuelven.
- Las funciones apagadas desaparecen de la interfaz (no muestran errores).
### Pasajero
- Si la ciudad está en pausa: el buscador muestra el motivo en vez de dejar cotizar.
### Motorizado
- Si la ciudad está en pausa: no puede conectarse y ve el motivo; si estaba conectado, recibe aviso y queda
  desconectado al terminar el viaje actual.

## Admin
- **Operación → Estado de la app**: interruptor de mantenimiento global y por ciudad con mensaje es/en y hora
  estimada (con confirmación y auditoría de 06).
- **Funciones**: lista de flags con reglas y vista previa de a quién aplica.
- **Anuncios**: crear, programar, ver alcance y cuántos lo cerraron.

## API y datos
- Claves nuevas en `AppConfig`: `maintenance` (`{enabled, message: {es, en}, eta, areas: []}`),
  `app_links` (soporte, emergencias, legales), `location_intervals`.
- Tabla `feature_flags` (`key`, `enabled`, `rules` JSONB, `updated_by`, `updated_at`).
- Tabla `announcements` (`title`, `body` es/en, `target` JSONB, `cta`, `starts_at`, `ends_at`, `dismissible`,
  `style`).
- `GET /app/bootstrap` → `{maintenance, paused_areas, flags: {key: bool}, announcements, links, min_version}`
  evaluado para el usuario (cacheado 30 s por combinación de audiencia).
- Error `service_paused` (503) con `details: {message, eta, area}` al cotizar, pedir o conectarse.
- Evento WebSocket `config.updated` cuando cambia algo, para que las apps relean.

## Criterios de aceptación
- Activar mantenimiento en Caracas impide pedir viajes en menos de 30 s, sin afectar viajes en curso.
- Apagar `chat` oculta el botón de chat en todas las apps abiertas en menos de 1 min.
- Un flag al 20 % aplica de forma estable al mismo usuario en cada apertura.
- Un banner programado aparece y desaparece en las fechas configuradas.

## Dependencias
09 (versión mínima y `X-App-Version`). 06 audita cada cambio.

## Preguntas para Carlos
Ninguna bloqueante.

## Cómo quedó (2026-10-12)
### API (`api/apps/control`)
- **Mantenimiento y pausas** viven en `AppConfig` (`maintenance`, `area_pauses`) pero solo se cambian con
  `PUT /admin/app/status` (permiso `app_status.manage`, auditado como `app_status.update`). Mientras aplican,
  cotizar, pedir y conectarse responden 503 `service_paused` con `details: {kind, area, message, eta}`. Los
  viajes ya pedidos o en curso siguen. El despachador desconecta cada 30 s a los motorizados conectados en una
  ciudad detenida que no tienen viaje ni oferta abierta (y lo hace al guardar el estado), y les envía el evento
  `driver.paused` con el motivo.
  Esas respuestas llevan `X-Planned-Outage: 1` y no cuentan como 5xx en el monitoreo (03), para que un
  mantenimiento no dispare alertas.
- **Interruptores** (`feature_flags`): las claves y su valor por defecto están en `apps/control/flags.py`
  (`chat`, `promotions`, `transfers`, `binance_auto`, `share_live_link`). Reglas: plataformas, build mínimo,
  ciudades, roles y porcentaje (hash estable de clave + id de cuenta, o del dispositivo antes de iniciar
  sesión). Lo que el servidor no sabe (sin cabeceras de la app o sin ubicación) no excluye. La API también
  rechaza lo apagado con 403 `feature_disabled`: mensajes del chat, transferencias y cotizar con código de
  promoción (sin código, simplemente no se aplica promoción); el worker deja de acreditar Binance Pay solo.
  `GET /admin/flags/{key}/check?email=` dice si una cuenta concreta lo recibe.
- **Anuncios** (`announcements`): título y texto es/en, audiencia (roles, ciudades), botón a una URL https o a
  una pantalla de la app, fechas, estilo y si se puede cerrar. Alcance y cierres se cuentan en Redis
  (HyperLogLog y un set por anuncio, 90 días después del fin).
- **Configuración remota**: `app_links` (WhatsApp y email de soporte, número de emergencias, términos y
  privacidad) y `location_intervals` se editan en Ajustes como cualquier otra clave.
- `GET /app/bootstrap?mode&lat&lng&client_id` (cuenta opcional) devuelve todo evaluado para quien pregunta:
  `area`, `maintenance` (global), `paused_areas`, `service` (lo que aplica en su ubicación), `flags`,
  `announcements`, `links`, `location_intervals`, `min_build` y `refresh_seconds`. Flags y anuncios se
  guardan 30 s en Redis; cualquier cambio (también en Ajustes) borra esa caché y emite `config.updated`
  por WebSocket para que las apps abiertas relean al instante.
- Permisos nuevos (grupo `app_control`): `app_status.view/manage`, `flags.view/manage`,
  `announcements.view/manage`. La migración se los da al rol Operaciones, salvo `flags.manage`.

### Admin
- **Estado de la app** (`/app-status`): mantenimiento global o por ciudades y pausas por ciudad, con mensaje
  es/en, hora estimada y confirmación antes de cada cambio; aviso rojo grande mientras hay mantenimiento.
- **Funciones** (`/flags`): interruptor y reglas por flag, resumen en palabras ("20 % de los motorizados en
  Caracas con build ≥ 7") y prueba por email de si una cuenta lo recibe.
- **Anuncios** (`/announcements`): crear, programar, duplicar y borrar, con vista previa del banner, estado
  (programado, activo, terminado), alcance y cuántos lo cerraron.
- **Ajustes**: tarjeta "Contacto y ubicación en la app" con `app_links` y `location_intervals`.

### App móvil (llega como OTA, sin APK nuevo)
- `<BootstrapSync/>` lee el bootstrap al abrir, cada `refresh_seconds` (30 s durante mantenimiento), al volver
  al frente, al cambiar de ciudad y con `config.updated`; guarda la última respuesta en el dispositivo y un
  fallo nunca bloquea la app.
- Pantalla de mantenimiento a pantalla completa que reintenta sola; viajes en curso, cuenta y billetera siguen
  accesibles. Con la ciudad en pausa, el pasajero ve el motivo en vez de cotizar y el motorizado no puede
  conectarse; `driver.paused` le avisa cuando el servidor lo desconecta.
- Banners arriba de la pantalla principal (máximo dos), con botón a URL o pantalla; los cerrados no vuelven.
- Flags apagados ocultan chat, código de promoción, transferencias y el texto de recarga automática.
- El número de emergencias, el soporte (WhatsApp/email), los enlaces legales y el intervalo de ubicación del
  motorizado salen de la configuración remota.

### Decidido
- `pwa_passengers` no se creó: la PWA está pospuesta (09, decisión 5).
