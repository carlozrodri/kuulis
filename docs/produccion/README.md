# Camino a producción

Análisis del 2026-10-11 sobre la rama `qa` (fases 1A a 1E hechas: cuentas, motorizados, viajes, tasas,
promociones, billetera, suscripción, reportes, suspensiones, finanzas y métricas). Aquí está lo que **falta**
para operar Kuulis en producción con al menos **5000 usuarios activos**, sin contar la publicación en App
Store ni Google Play (fuera de alcance por ahora).

Cada documento es autocontenido: objetivo, estado actual, alcance, app móvil (pasajero y motorizado), admin,
API y datos, criterios de aceptación y dependencias. Se implementan **uno a uno, en el orden de la tabla**.
Convención de siempre: lo que dijo Carlos es **Decidido**; el resto es **Supuesto** y se valida antes de
construir. Las preguntas de cada documento están en su sección final.

## Prioridades
- **P0**: bloquea el lanzamiento en Caracas. No se abre al público sin esto.
- **P1**: necesario en las primeras semanas con usuarios reales (o antes si hay tiempo).
- **P2**: crecimiento y eficiencia; cuando la operación esté estable.
- **P3**: opcional, a evaluar con datos.

## Orden de ejecución

| # | Documento | Prioridad | Área | Depende de |
| --- | --- | --- | --- | --- |
| 01 | [CI y calidad del código](01-ci-y-calidad.md) | P0 | Infra | — |
| 02 | [Infraestructura de producción](02-infraestructura-produccion.md) | P0 | Infra | 01 |
| 03 | [Observabilidad y alertas](03-observabilidad-y-alertas.md) | P0 | Infra · Admin | 02 |
| 04 | [Backups y recuperación](04-backups-y-recuperacion.md) | P0 | Infra | 02 |
| 05 | [Seguridad de la plataforma](05-seguridad-plataforma.md) | P0 | API · Admin · Mobile | 01 |
| 06 | [Auditoría y permisos del admin](06-auditoria-y-permisos-admin.md) | P0 | API · Admin | 05 |
| 07 | [Legal y privacidad](07-legal-y-privacidad.md) | P0 | API · Mobile · Admin | 08 (en paralelo) |
| 08 | [Web pública](08-web-publica.md) | P0 | Web | 02 |
| 09 | [Distribución y actualizaciones sin tiendas](09-distribucion-y-actualizaciones.md) | P0 | Mobile · Infra | 08 |
| 10 | [Control remoto de la app](10-control-remoto-de-la-app.md) | P0 | API · Mobile · Admin | 09 |
| 11 | [Seguridad en el viaje](11-seguridad-en-el-viaje.md) | P0 | Mobile · API · Admin | 08 |
| 12 | [Verificación continua de motorizados](12-verificacion-continua-motorizados.md) | P0 | Mobile · API · Admin | 06 |
| 13 | [Soporte y centro de ayuda](13-soporte-y-ayuda.md) | P0 | Mobile · API · Admin | 06 |
| 14 | [Notificaciones completas](14-notificaciones.md) | P1 | Mobile · API · Admin | 10 |
| 15 | [Reglas de cancelación y calidad del servicio](15-cancelaciones-y-calidad.md) | P1 | API · Mobile · Admin | — |
| 16 | [Antifraude](16-antifraude.md) | P1 | API · Mobile · Admin | 11, 15 |
| 17 | [Pagos y suscripción: endurecimiento](17-pagos-y-suscripcion.md) | P1 | API · Mobile · Admin | 03, 06 |
| 18 | [Escalabilidad y pruebas de carga](18-escalabilidad-y-carga.md) | P1 | Infra · API | 02, 03 |
| 19 | [Analítica de producto](19-analitica-de-producto.md) | P1 | API · Mobile · Admin | 07 |
| 20 | [Calidad de la app móvil](20-calidad-app-movil.md) | P1 | Mobile | 01 |
| 21 | [Zonas y demanda](21-zonas-y-demanda.md) | P2 | API · Mobile · Admin | 18, 19 |
| 22 | [Referidos](22-referidos.md) | P2 | API · Mobile · Admin | 16, 17 |
| 23 | [Mejoras para el pasajero](23-mejoras-pasajero.md) | P2 | Mobile · API | — |
| 24 | [Admin: herramientas de operación (CRM)](24-admin-crm.md) | P2 | Admin · API | 06, 13 |
| 25 | [Moderación de contenido](25-moderacion-de-contenido.md) | P2 | API · Admin | 13 |
| 26 | [Llamadas dentro de la app](26-llamadas-voip.md) | P3 | Mobile · API · Infra | 02 |

## Avance
- **01** hecho (2026-10-11).
- **02** hecho en QA (2026-10-11): OSRM y Photon propios, Redis con AOF, Postgres ajustado, commit en `/health`,
  listas de encendido y de despliegue. Pendiente para producción: dominio propio y VPS de contingencia.
- **04** hecho en código (2026-10-11): backups cifrados a R2 cada 15 min, libro contable, copia de archivos y
  prueba de restauración semanal. Activo en QA desde el 2026-10-11.
- **03** hecho en código (2026-10-11); faltan el bot de Telegram, GlitchTip y UptimeRobot de parte de Carlos.
- **05** hecho (2026-10-11): límites de uso con la IP real, bloqueo de login, 2FA del equipo, sesiones visibles,
  fotos sin EXIF y revisión de seguridad sin hallazgos altos (`revision-seguridad.md`).
- **06** hecho (2026-10-11): registro de auditoría de toda acción del admin y de las lecturas sensibles,
  permisos por rol (Soporte, Verificador, Finanzas, Operaciones), gestión del equipo con invitaciones y doble
  aprobación (ajustes de más de 20 USD, tarifas y tramos, notificaciones masivas).
- **07** hecho (2026-10-11): términos, privacidad, normas, términos de motorizado y billetera como borradores
  versionados (pendientes de abogado) con aceptación obligatoria; eliminación de cuenta que no deja datos
  personales en ninguna tabla, descarga de mis datos por email, limpieza diaria de datos viejos, aviso de
  ubicación del motorizado y página Privacidad en el admin.
- **08** parte 1 hecha (2026-10-11): web pública `web/` (inicio, motorizados, descargar, legal, verificar email
  y cambiar contraseña, Open Graph, sitemap) en el dominio principal; el admin pasa a `admin.<dominio>`. Faltan
  viaje compartido (11), ayuda (13), analítica (19) y enlace de estado (03), que se suman con esos documentos.
- **09** partes 1 y 2 hechas (2026-10-11/12): versiones del APK publicadas desde el admin, aviso y
  actualización dentro de la app, versión mínima obligatoria (426 en acciones de viaje), página Descargar con
  el APK real y OTA firmadas desde la propia API con porcentaje y reversión. La PWA para iPhone (parte 3)
  queda pospuesta por decisión de Carlos (2026-10-12).
- **10** hecho (2026-10-12): mantenimiento global o por ciudad, pausas por ciudad, interruptores de funciones con
  reglas y porcentaje, banners programados y configuración remota (soporte, emergencias, enlaces legales,
  intervalo de ubicación), todo desde el admin y aplicado en la app sin publicar código.
- **11** hecho (2026-10-13): PIN de inicio (siempre en Caracas), enlace en vivo `/v/{token}`, hasta 5
  contactos de confianza con compartir automático, SOS con ubicación cada 5 s,
  recorrido guardado, detección de paradas, desvíos y demoras con "¿Todo bien?", centro de seguridad en el
  admin y consejos. Sin guardia por ahora (decisión de Carlos): el SOS va al 911 y a los contactos.
- **12** hecho (2026-10-13): vencimientos con avisos y bloqueo, renovaciones, selfie en vivo al azar (semanal),
  reverificación por reportes, cambio de moto con revisión, duplicados por hash (incluye cuentas borradas),
  cola de reverificaciones con revisión rápida en el admin e inducción opcional. Antecedentes penales opcional.
- **13** hecho (2026-10-13): conversación en cada reporte con fotos, push y CSAT; tiempos de respuesta con
  alerta y cierre automático; respuestas guardadas, etiquetas y métricas; centro de ayuda en app y web;
  objeto perdido con chat temporal; contacto sin cuenta desde la web. Abierto: quién atiende y en qué horario.
- **14** hecho (2026-10-13): cada push abre su pantalla, canales de Android por tipo, preferencias y horario
  silencioso, campañas segmentadas y programadas con resultados, emails con la marca y limpieza diaria.
  Pendiente: sonido propio de la oferta (necesita APK) y Web Push (espera a la PWA).
- **15** hecho (2026-10-13): motivos de cancelación, espera de 5 min y "no se presentó", reasignación automática
  cuando el motorizado cancela, tasas por persona, avisos, pausas cortas y prioridad en el despacho, sin cobrar
  dinero. Página Calidad en el admin y "Mi calidad" en la app del motorizado.
- **16** hecho (2026-10-14): huella del teléfono, GPS simulado, viajes sospechosos, puntuación de riesgo,
  créditos de promoción y transferencias retenidas hasta revisión (la primera transferencia espera 24 h),
  vetados que no pueden volver a registrarse y calificaciones entre parejas sospechosas fuera del promedio.
  Página Riesgo en el admin.
- **17** hecho (2026-10-14): recibos no fiscales con número correlativo, estado de cuenta mensual en la app y por
  correo, cierres mensuales con hash encadenado y conciliación con el CSV de Binance Pay, invariantes diarios
  del libro con alerta, disputas de recarga en Soporte, paso automático a confirmación manual si Binance falla,
  exonerar o bajar cuotas con doble aprobación y simulador de tramos. Pendiente: la recarga real de prueba
  (necesita la cuenta de Carlos) y el [plan de Binance Merchant](binance-merchant.md) cuando exista empresa.
- **19** hecho (2026-10-14): eventos de producto propios con exclusión en Perfil, embudos de pasajero y
  motorizado, retención por cohortes, mapa de oferta y demanda por hora, promociones, economía del motorizado
  y exportación a CSV. Página Analítica en el admin. El 18 se canceló.
- Hecho en paralelo por otro hilo (2026-10-11, commit `da5bb1e`): lugares guardados, un contacto de confianza,
  invitaciones entre motorizados (un mes gratis al que invita cuando el invitado completa su primer viaje) y
  eliminación de cuenta con 30 días de gracia y borrado de datos personales. Al implementar 07, 11, 22 y 23 hay
  que partir de eso y no rehacerlo.

## Etapas sugeridas
1. **Bases (01–06):** que nada se rompa sin que lo sepamos y que se pueda recuperar. Sin pantallas nuevas
   para el usuario.
2. **Abrir al público (07–13):** lo mínimo legal, cómo se instala y actualiza la app sin tiendas, y la
   confianza (seguridad en el viaje, verificación, soporte). Al terminar esta etapa se puede lanzar en Caracas.
3. **Primeras semanas (14–20):** calidad del servicio, fraude, pagos robustos, carga real y medición.
4. **Crecimiento (21–26):** cuando haya datos.

## Lo que ya existe y no se repite aquí
Auth con Google/Apple y JWT con rotación, modo pasajero/motorizado, onboarding y aprobación de motorizados,
cotización y despacho con ofertas de 15 s, viaje en vivo por WebSocket, chat y calificación obligatoria,
ubicación en segundo plano (Android), tasas BCV/Binance, promociones con alertas de abuso, billetera con
recargas Binance Pay conciliadas, transferencias con límite, cuota mensual por tramos, reportes con bandeja,
suspensiones, finanzas con CSV, métricas, portada operativa, reporte de crashes a los logs, compartir el viaje
como texto y botón de llamar al 911.

## Hallazgos del análisis que conviene saber ya
- **Rate limit por IP** con la primera IP de `X-Forwarded-For` (`api/kuulis/core/rate_limit.py`): el cliente
  puede falsificarla, y en Venezuela las operadoras móviles usan CGNAT (muchos usuarios con la misma IP), así
  que 120/min por IP puede bloquear a usuarios legítimos. Ver 05.
- ~~`DELETE /users/me` solo desactiva la cuenta~~: resuelto en `da5bb1e` (borrado a los 30 días). Ver 07.
- ~~No hay CI~~: resuelto en 01.
- ~~OSRM y Photon usan los servidores públicos de demostración~~: resuelto en 02.
- ~~Los enlaces de los emails apuntan a páginas que no existen~~: resuelto en 08 (web pública).
- **No se guarda el recorrido del viaje**: ante un reporte de seguridad no hay ruta real para revisar. Ver 11.
- ~~Sin tiendas no hay forma de que los usuarios reciban una versión nueva~~: la app ya se actualiza sola con APKs (09 parte 1); y recibe OTA firmadas (parte 2).
- **Los documentos del motorizado no tienen fecha de vencimiento** (licencia, certificado médico). Ver 12.
- **Los reportes no tienen conversación**: el usuario solo recibe la resolución final. Ver 13.
- **Acciones del admin sin auditoría** y solo dos roles (`staff`, `admin`). Ver 06.
