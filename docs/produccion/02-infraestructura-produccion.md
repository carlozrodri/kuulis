# 02 · Infraestructura de producción

**Prioridad:** P0 · **Área:** Infra · **Depende de:** 01

## Objetivo
Dejar producción lista para encender: servicios propios para mapas, Redis y Postgres configurados para no
perder datos, recursos dimensionados y una lista de verificación para encender y para cada despliegue.
Todo autoalojado en el Coolify de Carlos, a costo bajo.

## Estado actual
- Producción está **apagada** (2026-10-09, pedido de Carlos) con auto-deploy y backup pausados.
- Rutas con OSRM y búsqueda con Photon apuntan a los **servidores públicos de demostración**
  (`OSRM_URL`, `PHOTON_URL`); su uso en producción no está permitido y no tienen garantías.
- Redis guarda refresh tokens, ubicaciones (GEO), cola de tareas (Streams), el set de despacho y rate limits.
  No está documentado si tiene persistencia (AOF); si se reinicia sin ella, todos los usuarios pierden la
  sesión y se pierden tareas en cola.
- Dominio `kuulis-prod.top8.uk` (subdominio de un dominio personal).
- Un solo servidor (homelab) detrás de Nginx Proxy Manager y Cloudflare.

## Alcance
### Incluye
1. **OSRM propio** (perfil `bicycle` o `car` ajustado a moto) con el extracto de Venezuela de Geofabrik,
   preprocesado con MLD. Servicio en Coolify `kuulis-osrm` sin puerto público, compartido por QA y producción.
   Actualización mensual del mapa (tarea manual documentada o contenedor que reconstruye).
2. **Photon propio** con el índice de Venezuela (o Nominatim si Photon pesa demasiado). Servicio
   `kuulis-photon` interno. Medir RAM y disco antes de decidir.
3. **Redis**: activar `appendonly yes` con `appendfsync everysec`, `maxmemory` definido y política
   `noeviction` (las colas y tokens no se pueden desalojar). Documentar el uso de memoria esperado.
4. **Postgres**: parámetros para el servidor (`shared_buffers`, `work_mem`, `max_connections`), extensión
   `pg_stat_statements` activada para ver consultas lentas, `log_min_duration_statement = 500ms`.
5. **Límites de recursos** por contenedor en Coolify (CPU y RAM) para que el compilador de APK o un pico de
   OSRM no tumbe la API.
6. **Dominio de marca**: decidir si producción usa `kuulis-prod.top8.uk` o un dominio propio (por ejemplo
   `kuulis.app` o `.com.ve`). Afecta enlaces de emails, web pública (08), enlaces de compartir viaje (11) y la
   descarga del APK (09).
7. **Lista de encendido de producción** en `docs/deployment.md`: orden de arranque, variables obligatorias por
   servicio, primer admin, configuración inicial (`service_areas` solo Caracas, tarifas, tramos), Binance,
   backup activado, smoke E2E (01) en verde.
8. **Lista de cada despliegue**: migraciones compatibles hacia atrás, smoke tras desplegar, cómo hacer
   rollback. Incluir el caso conocido de Coolify dejando el contenedor viejo sirviendo junto al nuevo
   (verificar con `/api/health/live` que la versión es la nueva; exponer `version`/`commit` en ese endpoint).
9. **Plan de contingencia del homelab**: qué pasa si se va la luz o internet en casa de Carlos. Como mínimo,
   página de estado externa (03) y procedimiento para levantar en un VPS barato desde los backups (04).

### Fuera
- Kubernetes, multi-región o alta disponibilidad real (ver 18 para cuándo hace falta un segundo servidor).

## App móvil
Sin cambios, salvo que la URL de la API cambie si se adopta un dominio de marca (variable de build).

## Admin
- La página de configuración muestra la versión y el commit de la API y del admin (pie de página).

## API y datos
- `GET /api/health/live` y `/ready` agregan `{version, commit, env}` (desde variables de build).
- `/ready` comprueba también OSRM y Photon (sin fallar si solo ellos caen: responde `degraded`).
- Si OSRM no responde, la cotización ya usa la línea recta × 1,3; registrar una métrica/alerta cuando ocurra.

## Criterios de aceptación
- QA usa OSRM y Photon propios y una ruta de 5 km en Caracas cotiza en menos de 300 ms.
- Reiniciar el contenedor de Redis no cierra la sesión de nadie ni pierde tareas encoladas.
- La lista de encendido está probada: se enciende producción, el smoke E2E pasa y se apaga si Carlos lo pide.
- `/api/health/live` muestra el commit desplegado.

## Dependencias
01 (para que los cambios de infraestructura pasen por CI). Necesita conocer la RAM y el disco libres del
servidor de Carlos.

## Preguntas para Carlos
1. ¿Dominio de marca para producción o seguimos con `kuulis-prod.top8.uk`? Recomendado: dominio propio corto
   antes de lanzar, porque se imprime en enlaces y en el APK.
2. ¿Cuánta RAM y disco libres hay en el servidor? OSRM de Venezuela necesita aprox. 2–4 GB y Photon 2–8 GB.
3. ¿Se acepta un VPS de respaldo pagado (≈5–10 USD/mes) para contingencia? Recomendado: tenerlo preparado
   pero apagado.
