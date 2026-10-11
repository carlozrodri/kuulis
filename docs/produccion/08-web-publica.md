# 08 · Web pública

**Prioridad:** P0 · **Área:** Web · **Depende de:** 02 (dominio)

## Objetivo
Un sitio público, rápido y bonito, que sea la casa de Kuulis fuera de la app: presenta el producto, permite
**descargar la app** (no hay tiendas), aloja los textos legales, resuelve los enlaces de los emails y muestra el
**viaje compartido en vivo**.

## Estado actual
- Los emails de verificación y de cambio de contraseña enlazan a `FRONTEND_URL/verify-email?token=` y
  `/reset-password?token=`; **esas páginas no existen** (en `docs/pending.md`).
- El dominio raíz sirve el **admin** (`/`) y la API está en `/api`.
- No hay página para descargar el APK, ni términos, ni privacidad, ni página de viaje compartido.

## Alcance
### Incluye
1. **App `web/`** en el monorepo: Nuxt 4 en modo estático/SSR ligero, con la marca Verde Ávila y Plus Jakarta
   Sans, es/en, pensada para teléfonos Android de gama baja y datos lentos (página principal < 200 KB).
2. **Reorganizar dominios** (supuesto): web pública en el dominio principal, admin en `admin.<dominio>` y API en
   `api.<dominio>` o seguir en `/api`. Esto requiere CORS para el admin si la API cambia de origen; la opción
   más barata es dejar la API en `/api` del dominio de la web y mover solo el admin a su subdominio.
3. Páginas:
   - **Inicio**: qué es Kuulis, beneficios para pasajeros y para motorizados ("sin comisión por viaje, 3 meses
     gratis"), cómo funciona, ciudades, preguntas frecuentes, botón **Descargar para Android** y acceso web
     para iPhone (09).
   - **Motorizados**: requisitos (desde la configuración de la API: edad, año de moto, documentos), tramos de la
     cuota (desde `fee_schedules`), cómo registrarse.
   - **Descargar**: APK más reciente con versión, tamaño, fecha, huella SHA-256 y pasos para instalar desde
     fuera de la tienda (con capturas). Detecta Android/iPhone.
   - **Legal**: términos, privacidad, normas (desde la API de 07), con versión e historial.
   - **Verificar email** y **Cambiar contraseña**: consumen los endpoints existentes; si el teléfono tiene la app,
     el enlace la abre (deep link, ver 09), si no, se completa en la web.
   - **Viaje compartido** `/v/{token}`: mapa con la posición en vivo, estado, nombre y foto del motorizado,
     moto y placa, origen y destino, hora estimada. Sin datos del pasajero más allá del nombre. Caduca al
     terminar el viaje (ver 11).
   - **Ayuda**: centro de ayuda público (artículos de 13) y formulario de contacto para quien no tiene cuenta.
   - **Estado**: enlace a la página de estado del monitor externo (03).
4. SEO básico (meta, Open Graph para compartir en WhatsApp con imagen), `sitemap.xml`, `robots.txt`.
5. Analítica web sin cookies y autoalojada (Umami o Plausible CE) para medir descargas (ver 19).

### Fuera
- Blog y CMS completo (los textos salen de la API o de archivos Markdown en el repo).

## App móvil
- Los enlaces de compartir viaje (11) y de invitación (22) apuntan a la web, que abre la app si está instalada.

## Admin
- Se mueve a su subdominio (si Carlos lo aprueba). Sin cambios funcionales.

## API y datos
- `GET /public/config` (sin auth, cacheado): ciudades, requisitos del motorizado, tramos vigentes, versión del APK
  más reciente (de 09), enlaces de soporte.
- `GET /public/rides/shared/{token}` y WebSocket público de solo lectura para la posición (o polling cada
  5 s si es más simple y barato). Ver 11 para el token.
- CORS solo para el origen de la web en las rutas `/public/*`.

## Criterios de aceptación
- Los enlaces de los emails de verificación y reset funcionan de punta a punta en QA y producción.
- La página de inicio carga en menos de 2 s en 3G simulado y obtiene ≥ 90 en Lighthouse móvil.
- La página Descargar ofrece el APK correcto y su huella coincide con el archivo.
- Un enlace de viaje compartido muestra la posición en vivo y deja de hacerlo al terminar el viaje.
- Coolify despliega `web/` con su propio `watch_paths`.

## Dependencias
02 (dominio definitivo). 07 aporta los textos legales y 09 el APK; la web puede salir antes con lo que exista.

## Preguntas para Carlos
1. ¿Movemos el admin a un subdominio (`admin.`) y dejamos el dominio principal para la web? Recomendado: sí.
2. ¿Tienes logo final? Si no, se usa el logotipo tipográfico actual.
