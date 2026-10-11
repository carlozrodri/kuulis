# Revisión de seguridad (OWASP ASVS 4, nivel 1)

**Fecha:** 2026-10-11 · **Alcance:** API (`api/`), admin (`admin/`) y app (`mobile/`) en el commit del PR de la
parte 3 del doc 05. Revisión de código, tests automáticos y comprobaciones en QA. No es un pentest externo.

**Resultado:** sin hallazgos altos. Dos de los tres medios y seis de los siete bajos quedaron corregidos; lo que sigue
abierto está abajo con su motivo.

## Hallazgos

| # | Severidad | Hallazgo | Estado |
| --- | --- | --- | --- |
| M1 | Media | Los correos (verificar, restablecer, bloqueo) metían el nombre del usuario sin escapar en HTML: alguien podía registrarse con el correo de otra persona y un nombre con un enlace, y Kuulis le mandaba ese enlace. | Corregido: nombre y enlace se escapan (`apps/users/tasks.py`). |
| M2 | Media | Cualquier motorizado podía registrar el Binance Pay ID de otro y quedarse con sus recargas automáticas. | Corregido: un Pay ID nuevo no acredita solo; el primer pago lo asigna el equipo y eso lo verifica. Cambiar el Pay ID vuelve a pedirlo. La app explica que la primera recarga se confirma a mano. |
| M3 | Media | Las credenciales del S3 de archivos son las mismas en QA y producción: si se filtra QA, se leen los archivos de producción. | **Abierto**: Carlos crea una clave por entorno limitada a su prefijo en el S3 del homelab (ver inventario de secretos en `docs/deployment.md`). |
| B1 | Baja | Confirmar o asignar recargas y perdonar cuotas no pedían código 2FA reciente, a diferencia de los ajustes de saldo. | Corregido: piden re-autenticación. |
| B2 | Baja | Los 5 intentos del código 2FA eran por reto; pidiendo retos nuevos se podía seguir probando. | Corregido: 10 fallos por cuenta en 15 min bloquean. |
| B3 | Baja | La búsqueda de destinatario aceptaba sufijos cortos de teléfono y devolvía motorizados cualesquiera. | Corregido: solo número completo o correo. |
| B4 | Baja | Cambiar la contraseña dejaba abiertas las demás sesiones. | Corregido: se cierran todas menos la actual. |
| B5 | Baja | `/client-errors` (sin sesión) escribía texto libre en los logs y permitía fingir líneas. | Corregido: cada línea del reporte va con sangría y prefijo. |
| B6 | Baja | Tokens y contraseña actual sin largo máximo. | Corregido: 2048 y 128 caracteres. |
| B7 | Baja | El tamaño de `/files/presign-upload` lo declara el cliente; la URL firmada no lo limita, así que alguien podría subir archivos grandes (costo de disco). Los documentos del motorizado sí se comprueban después de subir. | **Abierto**: pasar a `presigned POST` con `content-length-range` exige cambiar la subida en la app; se hace con 07/12. El quitado de EXIF ignora objetos más grandes que el máximo. |

Menores aceptados: el registro responde `email_taken` (necesario para la app; limitado a 20/min por IP);
`/config/public` muestra los umbrales de alerta de promociones (no dan acceso a nada). Un enlace de
restablecer contraseña sigue valiendo sus 30 minutos aunque se cambie la contraseña (quien lo tiene ya
controla el correo).

## Checklist ASVS nivel 1

| Capítulo | Estado | Evidencia |
| --- | --- | --- |
| V2 Autenticación | ✓ | Argon2, lista local de contraseñas comunes, bloqueo progresivo, 2FA obligatorio para el equipo con códigos de recuperación, sin enumeración en login y restablecer (`apps/auth`, `test_platform_security.py`, `test_admin_totp.py`). |
| V3 Sesiones | ✓ | Acceso de 15 min, refresh de un solo uso con detección de reutilización, sesiones con id visibles y revocables, cierre inmediato del token de acceso, cookies `Secure; SameSite=Strict` en el admin. |
| V4 Control de acceso | ✓ | Cada ruta de staff/admin usa `StaffUser`/`AdminUser`/`VerifiedAdminUser`; autorización por objeto probada en `apps/rides/tests/test_object_access.py`; archivos solo del dueño o del equipo (`apps/files/tests`). |
| V5 Validación | ✓ | Esquemas Pydantic con largos máximos, paginación con tope de 100, montos `Decimal` > 0 con 2 decimales, sin SQL armado con texto del usuario. Correos con HTML escapado. |
| V7 Errores y logs | ✓ | Formato de error único, sin tokens, contraseñas ni URLs firmadas en logs; Sentry/GlitchTip sin datos personales; IP real en cada línea. |
| V8 Datos | ✓ | Secretos de 2FA cifrados, fotos sin EXIF, enlaces de documentos de 5 min, backups cifrados. |
| V9 Comunicaciones | ✓ | HTTPS en NPM, HSTS, WebSocket por `wss` con el token en el primer mensaje (no en la URL). |
| V10 Código malicioso | ✓ | `pip-audit`, `pnpm audit` y `npm audit` en CI; escaneo de secretos en CI. |
| V11 Lógica de negocio | ✓ | Límites por usuario (cotizar, pedir, chat, reportes, transferencias), aceptación concurrente de viajes probada, tope mensual de transferencias con bloqueo de billeteras, Pay ID verificado. |
| V12 Archivos | Parcial | Tipo validado en el presign y en el registro de documentos; tamaño ver B7. |
| V13 API | ✓ | CORS por entorno, CSP `default-src 'none'` en la API, límites de tasa con 429 y `Retry-After`. |
| V14 Configuración | Parcial | Cabeceras de seguridad en API y admin, `SECRET_KEY` distinta por entorno; credenciales de S3 compartidas (M3). |

## Cómo repetirla
Antes de cada lanzamiento grande: correr la suite (`uv run pytest`), revisar rutas nuevas con su dependencia
de rol y un test de acceso ajeno en `test_object_access.py`, y actualizar esta tabla.
