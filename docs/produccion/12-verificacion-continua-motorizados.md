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
1. ¿Frecuencia de la selfie al azar? Recomendado: una vez por semana por motorizado, al conectarse.
2. ¿Pedir certificado de antecedentes penales como documento opcional? Recomendado: opcional al lanzar.
