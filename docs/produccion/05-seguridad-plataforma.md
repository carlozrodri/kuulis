# 05 · Seguridad de la plataforma

**Prioridad:** P0 · **Área:** API · Admin · Mobile · **Depende de:** 01

## Objetivo
Cerrar los huecos técnicos de seguridad antes de exponer Kuulis al público: límites de uso justos con CGNAT,
cuentas del equipo protegidas con segundo factor, sesiones visibles y revocables, secretos rotados y una
revisión de seguridad documentada.

## Estado actual
- Auth sólida: Argon2, JWT de 15 min, refresh rotativo con detección de reutilización, "cerrar sesión en todos
  lados" en la app, cookies `SameSite=Strict; Secure` en el admin, `X-Frame-Options: DENY`.
- **Rate limit por IP tomando la primera IP de `X-Forwarded-For`** (`api/kuulis/core/rate_limit.py`) con
  `--forwarded-allow-ips "*"`: un atacante puede inventar la IP y saltarse el límite; y con CGNAT de las
  operadoras venezolanas muchos usuarios legítimos comparten IP (120/min puede bloquearlos).
- El login del admin no tiene segundo factor.
- Contraseña mínima de 8 caracteres sin comprobar contraseñas filtradas.
- Token de Expo expuesto en un chat (bloqueo 8, pendiente de rotar).
- Sin política de seguridad de contenido (CSP) en el admin.

## Alcance
### Incluye
1. **Rate limit correcto**:
   - Tomar la IP real desde la cadena de proxies confiables (la IP que añadió NPM, contando desde la derecha
     según el número de saltos conocidos), no la primera de `X-Forwarded-For`. Limitar
     `--forwarded-allow-ips` a la red interna de Coolify.
   - Peticiones autenticadas: límite **por usuario** (id del JWT), no por IP.
   - Peticiones anónimas (login, registro, reset): límite por IP **y** por email/identificador.
   - Límites específicos: cotizar 30/min por usuario, pedir viaje 6/min, mensajes de chat 30/min, reportes
     10/h, presign de archivos 30/h, transferencias 10/h.
2. **Bloqueo progresivo de login**: tras 5 fallos para un email, espera creciente (1, 5, 15 min) y aviso por
   email al dueño de la cuenta.
3. **Segundo factor (TOTP) obligatorio para staff y admin**: alta con QR (Google Authenticator, Aegis),
   códigos de recuperación de un solo uso, re-autenticación para acciones sensibles (cambiar roles, ajustes
   de saldo, ver documentos en bloque).
4. **Sesiones visibles**: lista de sesiones activas (dispositivo, plataforma, última actividad, ciudad
   aproximada por IP opcional) en la app y en el admin, con cierre individual. Hoy solo existe cerrar todas.
5. **Contraseñas**: rechazar contraseñas comunes o filtradas (lista local de las 100 000 más comunes, sin
   llamar a servicios externos). Mínimo 8 se mantiene.
6. **Cabeceras y CSP** en el admin (CSP estricta, `Referrer-Policy`, `Permissions-Policy`, HSTS) y en la API.
7. **Documentos privados**: URLs firmadas de lectura con TTL corto (≤ 5 min) solo para staff, nunca en logs;
   tipos de archivo y tamaño validados en el presign; quitar metadatos EXIF (ubicación) de selfies y fotos.
8. **Secretos**: rotar el token de Expo (bloqueo 8), `SECRET_KEY` distinta por entorno (verificar), clave de
   Binance de solo lectura con IP restringida si Binance lo permite, inventario de secretos en
   `docs/deployment.md` (nombres, no valores) con fecha de última rotación.
9. **Revisión de seguridad** antes del lanzamiento: checklist OWASP ASVS nivel 1 sobre la API (autorización
   por objeto en cada endpoint `/{id}`, IDOR en viajes, reportes, billetera; validación de entradas; tamaños
   máximos), y `/security-review` sobre el código. Resultado en `docs/produccion/revision-seguridad.md`.
10. **WebSocket**: límite de mensajes por segundo por conexión, tamaño máximo de mensaje y cierre de conexiones
    con token vencido.

### Fuera
- Pentest externo pagado (se puede evaluar más adelante).
- 2FA para pasajeros y motorizados (el login social y el email bastan; se puede ofrecer como opcional).

## App móvil
### Pasajero y motorizado
- Perfil → Seguridad → **Sesiones activas**: lista con este dispositivo marcado y botón "Cerrar" por sesión.
- Mensaje claro si el login queda bloqueado temporalmente ("Demasiados intentos. Intenta en 5 minutos").
- Registro y cambio de contraseña: error traducido si la contraseña es demasiado común.

## Admin
- Alta de TOTP obligatoria en el primer login de cada staff (pantalla con QR y códigos de recuperación).
- Paso de verificación de código en el login y para acciones sensibles.
- Mi perfil → Sesiones activas.
- Un admin puede reiniciar el TOTP de un staff (queda en la auditoría de 06).

## API y datos
- Tabla `user_totp` (`user_id`, `secret` cifrado con clave de la app, `confirmed_at`, `recovery_codes` con hash).
- Sesiones: guardar en Redis metadatos por refresh token (`device`, `platform`, `ip`, `created_at`,
  `last_used_at`). `GET /auth/sessions`, `DELETE /auth/sessions/{id}`.
- `POST /auth/admin/login` responde `{totp_required: true, challenge}`; `POST /auth/admin/totp` completa.
- Códigos nuevos: `login_locked` (con `details.retry_after`), `password_too_common`, `totp_required`,
  `totp_invalid`.

## Criterios de aceptación
- Enviar `X-Forwarded-For: 1.2.3.4` falso no cambia el contador de rate limit.
- 200 usuarios distintos desde la misma IP pueden usar la app sin recibir 429.
- Ningún staff entra al admin sin TOTP.
- Un pasajero no puede leer un viaje, reporte o billetera ajenos (tests de autorización por objeto).
- Checklist de revisión de seguridad completo y sin hallazgos altos abiertos.

## Dependencias
01 (los tests de autorización corren en CI). Se coordina con 06 (las acciones sensibles se auditan).

## Decidido (2026-10-11)
1. 2FA obligatorio para todo el equipo del admin.
2. El token de Expo del bloqueo 8: Carlos lo rota (no se puede hacer desde aquí); queda en el inventario de
   secretos.
3. Se entrega en tres partes: (1) límites, bloqueo de login, contraseñas, cabeceras y WebSocket; (2) 2FA del
   admin y sesiones visibles; (3) documentos privados, inventario de secretos y revisión de seguridad.

## Cómo quedó
### Parte 1 (2026-10-11)
- IP real: uvicorn confía en `X-Forwarded-For` solo desde redes privadas (`FORWARDED_ALLOW_IPS`), así que
  una IP inventada no cambia el contador. La IP sale en cada línea del log.
- Límite por usuario con sesión y por IP sin sesión; límites propios para cotizar, pedir viaje, chat,
  reportes, subir archivos y transferencias (`docs/deployment.md` → Límites de uso). El 429 usa el mismo
  formato de error (`rate_limited`, `retry_after`).
- Bloqueo progresivo del login por correo (1, 5, 15 min) con aviso por email; también para correos que no
  existen, para no revelar cuáles están registrados.
- Contraseñas: lista local de 46 000 contraseñas comunes de 8 o más caracteres (NCSC top 100 000 y algunas
  locales); `password_too_common` en registro, cambio, restablecer y altas del admin.
- Cabeceras: HSTS, `Permissions-Policy`, `Cross-Origin-Opener-Policy` y CSP en la API (`default-src 'none'`)
  y en el admin (solo su origen; los iconos van en el paquete, sin pedirlos a iconify).
- WebSocket: mensajes de hasta 4 KB, 10 por segundo, y la conexión se cierra (4001) si el token vence sin
  renovarse. La app renueva el token al recibir `auth.expiring`.
- App y admin traducen `login_locked` (con los minutos), `password_too_common` y `rate_limited`.
- Pendiente de Carlos: que Traefik confíe en NPM (`192.168.0.148`), porque hoy reemplaza la cabecera y la API
  ve a todos los anónimos con la IP de NPM (`docs/deployment.md` → Límites de uso).

### Parte 2 (2026-10-11)
- 2FA (TOTP) obligatorio para staff y admin: QR la primera vez, 10 códigos de recuperación de un solo uso,
  un código no se acepta dos veces y el reto se anula tras 5 intentos. Tabla `user_totp` con la clave cifrada.
- Los tokens del admin llevan la marca de 2FA de la sesión; un staff que entra desde la app no tiene permisos
  de admin (`admin_mfa_required`).
- Código nuevo para cambiar roles, crear usuarios, ajustar saldos y reiniciar el 2FA de otro
  (`reauth_required`; el admin lo pide en una ventana y reintenta). No existe una vista de documentos en
  bloque, así que no hubo que protegerla.
- Un admin reinicia el 2FA de un miembro del equipo desde su ficha.
- Sesiones con id: la app (Perfil → Sesiones activas) y el admin (Mi perfil) muestran dispositivo, IP y
  último uso, con cierre por sesión. Cerrar una sesión invalida su token de acceso al instante y no se
  confunde con un robo de token (no cierra las demás).

### Parte 3 (2026-10-11)
- Fotos: al registrar un documento del motorizado o un avatar, el worker baja la imagen, la endereza y la
  vuelve a guardar sin EXIF (ubicación, teléfono, fecha). PDF y HEIC se quedan como están.
- Archivos ajenos: solo el dueño o el equipo con sesión de admin; el equipo recibe enlaces de 5 minutos.
- Tests de autorización por objeto: otro usuario u otro motorizado no puede leer ni tocar viajes, chat,
  calificaciones, reportes, lugares guardados, notificaciones ni sesiones ajenas.
- Secretos: inventario en `docs/deployment.md`; `SECRET_KEY` distinta en QA y producción (comparado por huella,
  sin leer valores).
- Revisión de seguridad (OWASP ASVS nivel 1) en `revision-seguridad.md`: sin hallazgos altos; se corrigieron
  dos de los tres medios y casi todos los bajos (correos con HTML inyectado, Pay ID de Binance sin verificar, 2FA para
  confirmar recargas, intentos de 2FA por cuenta, búsqueda de destinatarios, sesiones al cambiar contraseña,
  logs de errores de la app y largos máximos). Queda abierto separar la clave del S3 de QA y producción.
- Traefik ya confía en NPM y la API ve la IP real de cada cliente (verificado en los logs de QA).

## Preguntas para Carlos
1. ¿2FA obligatorio para todo el equipo del admin? Recomendado: sí.
2. ¿Rotaste ya el token de Expo del bloqueo 8?
