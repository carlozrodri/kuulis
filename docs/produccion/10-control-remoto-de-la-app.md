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
