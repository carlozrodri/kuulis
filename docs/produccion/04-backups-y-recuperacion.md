# 04 · Backups y recuperación

**Prioridad:** P0 · **Área:** Infra · **Depende de:** 02

## Objetivo
Poder recuperar Kuulis ante la pérdida del servidor, un error humano o una migración mala, con objetivos
claros: **perder como máximo 15 minutos de datos (RPO)** y **volver a estar en línea en menos de 4 horas
(RTO)** (supuesto, a confirmar).

## Estado actual
- Backups de Postgres en Coolify con S3 activado (QA diario 7 días; producción cada 6 h, 14 días; pausado
  mientras producción está apagada).
- Pendiente en `docs/pending.md`: **nunca se probó una restauración**.
- Cada 6 h implica hasta 6 h de billeteras, cuotas y viajes perdidos.
- El S3 (`s3.top8.uk`) parece estar en el mismo homelab: si se pierde el sitio, se pierden datos y backups.
- Los documentos de los motorizados y avatares están en S3 sin copia externa documentada.

## Alcance
### Incluye
1. **Postgres con archivo continuo (WAL)**: `pgBackRest` o `wal-g` hacia S3, con backup completo diario y WAL
   continuo, para restaurar a un punto en el tiempo (PITR). Retención 14 días producción, 7 QA.
2. **Copia fuera del sitio**: replicar backups y el bucket de documentos a un almacenamiento externo barato
   (Backblaze B2, Cloudflare R2 o Wasabi) cifrado. Costo estimado < 2 USD/mes con los volúmenes actuales.
3. **Redis**: snapshot RDB diario al mismo destino (AOF está en 02). Se acepta perder Redis: se documenta qué
   se pierde (sesiones, ubicaciones) y cómo se reconstruye (las ofertas se re-programan por `reconcile`).
4. **Prueba de restauración mensual** automatizada en QA: restaura el último backup de producción en una base
   temporal, corre `alembic current`, cuenta filas de tablas clave y borra la base. Resultado en la página de
   Estado del sistema (03) y alerta si falla.
5. **Runbook de desastre** en `docs/deployment.md`: levantar todo en otro servidor desde cero (Coolify,
   variables, restaurar Postgres a un punto, apuntar DNS) con tiempos medidos en un simulacro.
6. **Protección contra borrados**: versionado o bloqueo de objetos en el bucket de backups (que un error o un
   atacante con las credenciales de la app no pueda borrar los backups). Credenciales separadas: la app no
   tiene permiso de borrar backups.
7. **Exportación diaria del libro contable** (`wallet_entries`, `subscription_charges`, `wallet_top_ups`) a CSV
   cifrado en el almacenamiento externo, como respaldo contable independiente de Postgres.

### Fuera
- Réplica en caliente de Postgres (ver 18).

## App móvil
Sin cambios.

## Admin
- La página Estado del sistema (03) muestra: último backup completo, último WAL archivado, última prueba de
  restauración y su resultado.

## API y datos
- Sin cambios de esquema. Tareas de infraestructura en Coolify (contenedores programados) y un script
  `scripts/restore_check.sh` versionado.

## Criterios de aceptación
- Simulacro documentado: se restaura producción (o una copia) a un minuto concreto y los saldos coinciden.
- Borrar por error una fila en QA y recuperarla con PITR, siguiendo el runbook, en menos de 1 hora.
- Los backups existen fuera del homelab y no se pueden borrar con las credenciales de la app.
- Alerta si el último backup tiene más de 26 h o si el archivo de WAL se detiene más de 15 min.

## Dependencias
02 (configuración de Postgres y Redis). 03 para las alertas.

## Preguntas para Carlos
1. ¿RPO de 15 min y RTO de 4 h te parecen bien? Recomendado: sí para el lanzamiento.
2. ¿Qué almacenamiento externo prefieres? Recomendado: Cloudflare R2 (ya usas Cloudflare, sin costo de salida).
