# 12 · Verificación continua de motorizados

**Prioridad:** P0 · **Área:** Mobile · API · Admin · **Depende de:** 06

## Objetivo
Que quien maneja sea siempre la persona aprobada, con documentos vigentes y la moto registrada. La aprobación
inicial ya existe; falta mantenerla en el tiempo y hacer la revisión más rápida y consistente.

## Estado actual
- Onboarding en 4 pasos con documentos (`id_card`, `rif`, `drivers_license`, `medical_certificate`,
  `vehicle_registration`, `selfie`, `vehicle_photo`), estado por documento y rechazo con motivo.
- Estados del perfil: borrador, en revisión, aprobado, rechazado, suspendido. Aprobación manual.
- `national_id` y `plate` son únicos.
- **Sin fecha de vencimiento** de licencia, certificado médico ni carnet de circulación.
- **Sin comprobación posterior** de que quien está conectado es el titular (cuentas prestadas o vendidas).
- Un motorizado aprobado no tiene flujo para cambiar de moto.

## Alcance
### Incluye
1. **Vencimientos**: el motorizado indica la fecha de vencimiento de licencia, certificado médico y carnet de
   circulación (el verificador la confirma). Avisos a 30, 7 y 1 día; al vencer, no puede conectarse hasta
   subir el documento nuevo y que se apruebe (sin perder el resto de la aprobación).
2. **Selfie de verificación periódica**: al conectarse, con probabilidad configurable (por ejemplo 1 de cada 10
   conexiones o una vez al día al azar), se pide una selfie en vivo (cámara frontal, sin galería). Revisión:
   - Manual en el admin comparando con la selfie y la cédula aprobadas (costo cero).
   - Opcional más adelante: comparación facial autoalojada (modelo abierto) como ayuda, nunca automática sola.
   - Mientras está pendiente puede trabajar; si se rechaza, se suspende el perfil y se abre un reporte.
3. **Cambio de moto**: flujo para registrar una moto nueva (datos + carnet + fotos) que pasa por revisión; sigue
   trabajando con la anterior hasta la aprobación.
4. **Revisión más rápida**: checklist por tipo de documento (legible, coincide nombre, coincide número, vigente,
   foto clara), motivos de rechazo predefinidos con texto para el motorizado, atajos de teclado, zoom y rotación
   de imágenes, comparación lado a lado de selfie y cédula, asignación de la solicitud a un verificador.
5. **Duplicados y riesgos**: alerta si la misma cédula, RIF, placa, teléfono, Binance Pay ID o dispositivo
   aparecen en otra cuenta (incluidas cuentas eliminadas o suspendidas, por hash).
6. **Reverificación por reportes**: N reportes de `vehicle_mismatch` en 30 días fuerzan una selfie y fotos de
   la moto nuevas.
7. **Entrevista o inducción** (opcional por configuración): marcar en el admin "inducción completada" como
   requisito para aprobar (por ejemplo, una charla presencial o un video con preguntas).

### Fuera
- Verificación de antecedentes penales con terceros (no hay proveedor práctico en Venezuela; se puede pedir el
  certificado de antecedentes como documento opcional configurable).

## App móvil
### Motorizado
- Documentos: fecha de vencimiento en los que aplica; insignia "Vence en 12 días" y botón "Actualizar".
- Banner y bloqueo al conectarse si un documento está vencido, con acceso directo a subirlo.
- Pantalla de selfie en vivo con guía de encuadre y buena luz; estado "En revisión".
- Perfil → Mi moto → "Cambiar de moto".

## Admin
- Cola de **reverificaciones** (selfies, documentos renovados, cambios de moto) separada de la de nuevos.
- Vista de revisión con checklist, motivos predefinidos, comparación lado a lado y atajos.
- Ficha del motorizado: línea de tiempo de verificaciones, documentos con vencimiento y alertas de duplicados.
- Portada: contadores de documentos por vencer esta semana y reverificaciones pendientes.
- Configuración: documentos que vencen, frecuencia de selfie, inducción obligatoria.

## API y datos
- `driver_documents.expires_on` (date, nullable) y `superseded_by_id`.
- `driver_checks` (`driver_id`, `kind` selfie|vehicle_change|document_renewal, `status`, `file_keys`,
  `requested_at`, `reviewed_by_id`, `reviewed_at`, `result_reason`).
- `vehicles.status` (active|pending|retired) para permitir una moto pendiente mientras otra está activa.
- `POST /drivers/me/online` responde 403 `document_expired` (con `details.kinds`) o `selfie_required`.
- `POST /drivers/me/checks/selfie` (presign + confirmación), `POST /drivers/me/vehicles` (cambio de moto).
- Tarea diaria `drivers.expirations` (avisos y bloqueos) con lock.
- Huellas de dispositivo (`device_id` de la app) guardadas por sesión para detectar duplicados (ver 16).

## Criterios de aceptación
- Un motorizado con licencia vencida no puede conectarse y recibe avisos los días previos.
- Una selfie solicitada al azar aparece en la cola y su rechazo suspende el perfil con reporte.
- Un cambio de moto aprobado reemplaza la moto en las ofertas y en el viaje compartido.
- Registrar la misma placa o cédula en otra cuenta muestra la alerta en ambas fichas.
- Revisar una solicitud completa con atajos toma menos de 2 minutos (medido con un verificador).

## Dependencias
06 (rol `verificador` y auditoría de cada acceso a documentos).

## Preguntas para Carlos
1. **Decidido (recomendado):** una selfie en vivo más o menos una vez por semana por motorizado, en un momento
   al azar entre 3,5 y 10,5 días, al conectarse. Se cambia en Ajustes → Verificación (`selfie_every_days`;
   0 la apaga).
2. **Decidido (recomendado):** el certificado de antecedentes penales es un documento opcional al lanzar
   (`verification.optional_documents`); se vuelve obligatorio agregándolo a los documentos requeridos.


## Cómo quedó (2026-10-13)
### API (`api/apps/drivers`: `verification.py`, `checks.py`, `tasks.py`)
- **Vencimientos:** `driver_documents.expires_on` y `expiry_confirmed` (el verificador confirma o corrige la
  fecha al aprobar). Vencen por defecto licencia, certificado médico y carnet de circulación
  (`verification.expiring_documents`). Un documento vencido hace que `POST /drivers/me/online` responda 403
  `document_expired` (`details.kinds`) hasta que se apruebe el nuevo. Los aprobados antes de este cambio sin
  fecha no bloquean: la app le pide al motorizado que la indique (`PATCH /drivers/me/documents/{id}`).
- **Renovaciones:** un motorizado aprobado o suspendido sube el documento nuevo por el mismo camino del
  registro (con fecha obligatoria). El viejo sigue en uso; el nuevo entra a la cola como `document_renewal` y al
  aprobarse reemplaza al anterior (`superseded_by_id`, queda como historial en el admin).
- **Avisos:** tarea diaria a las 08:00 de Caracas con lock (`driver_expirations`, latido en Sistema): avisos a
  30, 7 y 1 día y el día que vence (una vez por paso); al vencer lo desconecta si no está en un viaje.
- **Selfie en vivo:** `driver_profiles.selfie_due_at` se fija al azar alrededor de `selfie_every_days` (7). Al
  conectarse después de esa hora se crea la verificación y responde 403 `selfie_required` (`details.check_id`);
  la app manda la selfie (`POST /drivers/me/checks/presign` y `/checks/{id}/submit`) y puede trabajar mientras
  espera revisión. Rechazarla suspende el perfil y abre un reporte urgente.
- **Reverificación por reportes:** `mismatch_reports` (2) reportes `vehicle_mismatch` en `report_window_days`
  (30) piden selfie y fotos nuevas de la moto; el equipo también puede pedirla desde la ficha.
- **Cambio de moto:** `vehicles.status` (`active`, `pending`, `retired`); `POST /drivers/me/vehicles` con datos,
  carnet (con vencimiento) y fotos. Sigue con la moto actual hasta la aprobación; al aprobar, la nueva pasa a
  usarse en ofertas y viajes y la vieja queda retirada (su placa se puede registrar de nuevo por otra persona).
- **Duplicados:** tabla `identity_marks` con un hash con clave (HMAC con `SECRET_KEY`) de cédula, RIF, placa,
  teléfono, Binance Pay ID y dispositivo (`X-Device-Id` de la app). Se conserva al borrar la cuenta, así que una
  cuenta nueva con los mismos datos aparece en la ficha de ambas. La migración carga los datos existentes.
- **Inducción:** con `induction_required` no se puede aprobar sin marcar "Inducción completada".
- Certificado de antecedentes penales (`criminal_record`) como documento opcional.
- Auditoría nueva: `driver.check_view`, `driver.check_review`, `driver.check_assign`, `driver.assign`,
  `driver.induction`, `driver.reverify`.

### Admin
- **Reverificaciones** (Motorizados → Reverificaciones): cola separada, la más vieja primero, con filtros y
  "Tomar". Revisión con lo enviado al lado de la selfie y la cédula aprobadas (o el documento en uso, o la moto
  actual), zoom y rotación, checklist por tipo que debe estar completo para aprobar, motivos predefinidos,
  fecha de vencimiento y atajos (1-9 marcar, A aprobar, R rechazar, +/- zoom, O rotar, ←/→ imagen, N siguiente).
- **Ficha del motorizado:** alerta de duplicados, vencimientos con insignias, historial de documentos
  reemplazados, línea de tiempo de verificaciones, asignar verificador, inducción y "Pedir reverificación".
- **Portada:** reverificaciones pendientes y documentos que vencen esta semana. **Ajustes → Verificación de
  motorizados** con todo lo configurable.

### App
- Registro: fecha de vencimiento al subir licencia, certificado médico y carnet; antecedentes como opcional.
- **Mis documentos** (Perfil y aviso del inicio): insignias "Vence en N días", "Vencido", "Falta la fecha",
  "En revisión" y botón "Actualizar".
- Aviso en el inicio del motorizado y, si no lo deja conectarse, una hoja con el paso directo (actualizar el
  documento o tomar la selfie) en vez de un error.
- **Selfie en vivo** con guía de encuadre y luz, solo cámara frontal; en la reverificación también fotos de la
  moto. **Perfil → Tu moto → Cambiar de moto** con estado "En revisión" y opción de cancelar.
- Todo va como OTA (sin dependencias nativas nuevas).

### Pendiente
- Medir con un verificador real que una revisión completa toma menos de 2 minutos.
- La comparación facial automática queda para más adelante (opcional en el documento).
