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

## Preguntas para Carlos
1. ¿2FA obligatorio para todo el equipo del admin? Recomendado: sí.
2. ¿Rotaste ya el token de Expo del bloqueo 8?
