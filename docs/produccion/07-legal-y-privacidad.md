# 07 · Legal y privacidad

**Prioridad:** P0 · **Área:** API · Mobile · Admin · **Depende de:** 08 (páginas públicas para los textos)

## Objetivo
Que cada usuario acepte términos y política de privacidad reales y versionados, que pueda borrar su cuenta de
verdad y descargar sus datos, y que Kuulis guarde los datos solo el tiempo necesario. Reduce el riesgo personal
de Carlos al operar sin empresa registrada.

## Estado actual
- El registro dice "Al crear tu cuenta aceptas los términos y la política de privacidad de Kuulis", pero **no
  hay textos ni enlaces** y no se guarda la aceptación.
- `DELETE /users/me` solo pone `is_active = false`: nombre, email, documentos, chats y ubicaciones quedan.
- No hay política de retención (chats, documentos, crashes con datos, ubicaciones).
- `docs/product/open-questions.md` lista como riesgos: operar sin empresa, custodia de saldos y regulación de
  mototaxis; la mitigación propuesta es "términos claros (Kuulis conecta, no transporta)" y asesoría legal.

## Alcance
### Incluye
1. **Documentos legales** (redactados como borrador por Claude y **revisados por un abogado venezolano**):
   - Términos y condiciones para pasajeros y para motorizados (Kuulis es una plataforma de intermediación; el
     pago es entre las partes; responsabilidades; conducta; suspensión; limitación de responsabilidad).
   - Condiciones de la billetera: crédito prepago no reembolsable, no retirable, transferible con límite.
   - Política de privacidad: qué datos, para qué, cuánto tiempo, con quién se comparten (proveedores: Resend,
     Expo, Binance, Google, Apple, S3), derechos del usuario.
   - Normas de la comunidad (conducta, seguridad, objetos prohibidos, uso de casco).
   Publicados en la web pública (08) en es/en, con versión y fecha.
2. **Aceptación versionada**: al registrarse y cada vez que cambia una versión mayor, la app pide aceptar
   (pantalla bloqueante con resumen de cambios). Se guarda versión, fecha, IP y plataforma.
3. **Edad mínima del pasajero**: casilla "Soy mayor de 18 años" (supuesto). El motorizado ya exige 21.
4. **Eliminación real de cuenta**:
   - Desde la app (Perfil → Seguridad → Eliminar cuenta) con confirmación y espera de 14 días (se puede
     cancelar entrando de nuevo).
   - Bloqueos: no se elimina con viaje activo, reportes abiertos en su contra o cuota pendiente.
   - Al ejecutarse: se anonimizan nombre, email, teléfono, avatar; se borran documentos del motorizado, tokens
     push y sesiones; los viajes, movimientos de billetera y reportes se conservan **anonimizados** para
     contabilidad y seguridad. El saldo de la billetera se pierde (aviso explícito).
   - El email queda en una lista de hashes para evitar reabrir cuentas suspendidas (ver 16).
5. **Descarga de mis datos**: genera un JSON/ZIP con perfil, viajes, calificaciones recibidas (sin autor),
   movimientos de billetera y reportes propios, enviado por email con enlace firmado de 24 h.
6. **Retención** (tarea diaria):
   - Mensajes de chat: 180 días.
   - Recorrido del viaje (11): 180 días, salvo si hay un reporte asociado.
   - Documentos de motorizados rechazados o eliminados: 30 días.
   - Notificaciones de la bandeja: 90 días (ya en `docs/pending.md`).
   - Logs y crashes: 14–30 días.
   - Auditoría (06) y libro contable: 5 años (supuesto, a validar con el abogado).
7. **Consentimientos explícitos** del motorizado para compartir ubicación en segundo plano (Android lo exige con
   una pantalla previa) y del pasajero para compartir su viaje (11).

### Fuera
- Constituir la empresa y temas fiscales (decisión de Carlos, fuera del software).

## App móvil
### Pasajero y motorizado
- Registro: enlaces a Términos y Privacidad (abren la web en el navegador interno), casilla obligatoria de
  aceptación y de mayoría de edad.
- Pantalla bloqueante "Actualizamos nuestros términos" cuando cambia la versión.
- Perfil → Legal: Términos, Privacidad, Normas de la comunidad, Licencias de código abierto.
- Perfil → Seguridad → **Descargar mis datos** y **Eliminar mi cuenta** (con explicación de qué se borra y qué
  se conserva, y del saldo que se pierde).
### Motorizado
- Antes de pedir el permiso de ubicación en segundo plano: pantalla que explica para qué se usa (Android).
- Aceptación de los términos de motorizado al enviar la solicitud.

## Admin
- **Legal**: lista de documentos y versiones (texto en Markdown es/en), publicar una versión nueva y marcar si
  exige volver a aceptar.
- Ficha de usuario: versión aceptada y fecha; estado de eliminación programada.
- Solicitudes de eliminación y exportación: lista con estado (para soporte).

## API y datos
- `legal_documents` (`kind`, `version`, `locale`, `body_md`, `published_at`, `requires_reacceptance`).
- `legal_acceptances` (`user_id`, `kind`, `version`, `accepted_at`, `ip`, `platform`).
- `account_deletions` (`user_id`, `requested_at`, `scheduled_for`, `cancelled_at`, `completed_at`).
- `data_exports` (`user_id`, `status`, `file_key`, `expires_at`).
- `GET /legal/{kind}?locale` (público), `POST /legal/accept`, `GET /users/me` agrega
  `pending_legal: [kind]`. Middleware: si hay `pending_legal`, las acciones de viaje responden 409
  `legal_acceptance_required`.
- `POST /users/me/deletion`, `DELETE /users/me/deletion` (cancelar), `POST /users/me/export`.
- Tarea diaria `privacy.retention` con lock.
- `DELETE /users/me` actual pasa a ser la programación de la eliminación (compatibilidad).

## Criterios de aceptación
- Un usuario nuevo no puede completar el registro sin aceptar; la aceptación queda guardada con versión.
- Publicar una versión mayor obliga a todos a aceptar al abrir la app antes de pedir o aceptar viajes.
- Tras 14 días, una cuenta eliminada no tiene datos personales en ninguna tabla ni en S3 (test que lo verifica),
  y sus viajes siguen en las métricas.
- La exportación llega por email con un archivo legible.
- Las tareas de retención borran chats de más de 180 días que no estén ligados a un reporte.

## Dependencias
08 (dónde se publican los textos). Revisión de un abogado antes del lanzamiento (Carlos).

## Preguntas para Carlos
1. ¿Tienes un abogado venezolano que revise los textos? Claude prepara el borrador.
2. ¿Edad mínima del pasajero: 18? Recomendado: 18 (menores con un adulto, sin cuenta propia).
3. ¿Plazo de 14 días antes de eliminar? Recomendado: sí.

## Decidido (2026-10-11)
1. Claude redacta los borradores; la revisión del abogado queda pendiente (`docs/pending.md`).
2. Edad mínima del pasajero: 18 años.
3. Espera antes de borrar la cuenta: **30 días**, como ya estaba implementado (en lugar de los 14 del borrador).
4. Se entrega en dos partes: (1) textos legales versionados y su aceptación; (2) eliminación, descarga de
   datos, retención y consentimientos.

## Cómo quedó
### Parte 1 (2026-10-11)
- Borradores en español e inglés en `api/apps/legal/texts/`: términos y condiciones, política de privacidad,
  normas de la comunidad, términos para motorizados y condiciones de la billetera. Cada uno avisa que está
  pendiente de revisión legal y deja entre corchetes los datos que faltan. La migración los publica como
  versión 1.
- Tablas `legal_documents` (tipo, versión, idioma, título, texto en Markdown, qué cambió, si exige aceptar de
  nuevo, fecha) y `legal_acceptances` (usuario, tipo, versión, fecha, IP y plataforma).
- `GET /legal` y `GET /legal/{kind}?locale=` públicos; `POST /legal/accept`; `GET /users/me` trae
  `pending_legal`. Pasajeros aceptan términos y privacidad; quien tiene ficha de motorizado también los términos
  de motorizado y la billetera. El equipo (staff y admin) no acepta nada.
- Pedir un viaje, aceptar un viaje y conectarse responden 409 `legal_acceptance_required` con
  `details.kinds` mientras falte aceptar algo.
- `POST /auth/register` acepta `accept_legal: true` y guarda la aceptación con IP y plataforma.
- App: casillas obligatorias en el registro (acepto términos y privacidad, con enlaces; soy mayor de 18),
  pantalla bloqueante «Antes de empezar» / «Actualizamos nuestros términos» (también tras entrar con Google o
  Apple), lector de textos dentro de la app y sección **Legal** en el perfil.
- Admin: página **Legal** (solo admin) con la versión vigente de cada texto, su historial, lectura en los dos
  idiomas y publicación de una versión nueva (con «qué cambió» y si exige aceptar de nuevo; queda en la
  auditoría como `legal.publish`). La ficha de cada usuario muestra qué versiones aceptó, cuándo y desde dónde.
- Las licencias de código abierto y la web pública (08) quedan para cuando se haga el doc 08.

### Parte 2 (2026-10-11)
- **Eliminar la cuenta** (Perfil → Seguridad → Eliminar mi cuenta) abre una pantalla que explica qué se borra, qué
  se conserva sin nombre, que el saldo de la billetera se pierde (muestra el monto) y los 30 días para arrepentirse.
  La API la rechaza con viaje activo (`account_ride_active`), con reportes abiertos en su contra
  (`account_open_reports`) o con una cuota pendiente (`account_fee_pending`).
- **Al borrar** (30 días después), además de lo que ya se hacía: se borran sus mensajes de chat, consentimientos,
  2FA y descargas (con sus archivos); los viajes que pidió quedan sin direcciones, con coordenadas redondeadas a
  ~1 km y sin recorrido; los que manejó quedan sin placa; sus comentarios en calificaciones, el nombre e ID de
  Binance de sus recargas y su ID de Binance Pay se borran; su nombre desaparece de las transferencias de la otra
  persona; la IP de sus aceptaciones legales se borra. El hash del email queda en `erased_emails` (con la marca de
  si tuvo suspensiones) para el doc 16. Una prueba recorre **todas** las tablas y verifica que no queda ningún dato
  personal del pasajero ni del motorizado, y que el viaje sigue contando.
- **Descargar mis datos** (Perfil → Seguridad): `POST /users/me/export` arma un JSON con perfil, ficha de
  motorizado, lugares, viajes, calificaciones recibidas (sin autor) y dadas, billetera, recargas, cuotas, reportes
  propios, aceptaciones legales y consentimientos; lo sube al almacenamiento privado y envía por email un enlace
  firmado de 24 h. Una por día (`export_too_soon`); si falla se puede reintentar enseguida.
- **Retención** (tarea diaria `privacy_retention` con lock, vigilada por el monitoreo): chats de más de 180 días y
  recorridos de más de 180 días salvo que el viaje tenga un reporte, documentos rechazados de más de 30 días (con
  su archivo), notificaciones de más de 90 días y archivos de descargas vencidos.
- **Consentimiento de ubicación** (Android): la primera vez que el motorizado se conecta, una hoja explica que su
  ubicación se usa también con la app minimizada mientras está conectado; al aceptar se guarda en
  `user_consents` (`PUT /users/me/consents`) y no se vuelve a preguntar. El consentimiento para compartir el viaje
  queda para el doc 11.
- **Admin → Privacidad** (permiso `users.view`): eliminaciones (programadas y ejecutadas, con la fecha de borrado) y
  descargas de datos con su estado. La ficha del usuario avisa si su eliminación está programada o ya se hizo.
- No se creó la tabla `account_deletions` del borrador: las fechas viven en el usuario
  (`deletion_requested_at`, `deleted_at`), como ya estaba.
