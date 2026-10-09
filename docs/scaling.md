# Escalabilidad (objetivo inicial: 5000 usuarios activos)

## Estimación
5000 usuarios activos al día con un pico de ~10% concurrentes son ~500 usuarios simultáneos. Con una
petición cada 10–20 s por usuario activo son 25–50 req/s en pico, más ~500 WebSockets abiertos. Un solo
contenedor de API con 4 workers async aguanta esto con margen (cada worker atiende cientos de peticiones
concurrentes mientras espera I/O).

## Configuración actual por entorno

| Pieza | Valor | Dónde se cambia |
| --- | --- | --- |
| Workers gunicorn por contenedor API | 4 (`WEB_CONCURRENCY`) | env en Coolify |
| Pool Postgres por worker API | 10 + 5 overflow (prod) | `DB_POOL_SIZE`, `DB_MAX_OVERFLOW` |
| Procesos worker Taskiq | 2 (`WORKER_CONCURRENCY`), pool 5 + 5 | env del worker |
| Tareas async por proceso worker | 100 | `WORKER_MAX_ASYNC_TASKS` |
| Conexiones Postgres máximas usadas | 4×15 + 2×10 = 80 (< 100 por defecto) | — |
| Rate limit general | 120/min por IP | `RATE_LIMIT_DEFAULT` |
| Rate limit login/registro | 10/min por IP | `RATE_LIMIT_AUTH` |

Además: `pool_pre_ping`, reciclado de conexiones cada 30 min, `max-requests` con jitter en gunicorn para
evitar fugas de memoria, gzip, índices en email, rol, `user_id` y `(user_id, created_at)` de notificaciones,
paginación con límite máximo de 100, broadcast de notificaciones en lotes de 500 por keyset.

## Cómo crecer (en orden)
1. Subir `WEB_CONCURRENCY` (≈ 2 × CPUs del servidor) y ajustar el pool para no pasar de `max_connections`.
2. Añadir un segundo servidor en Coolify y repartir API/worker; Redis pub/sub y Redis rate limit ya lo permiten.
3. Poner **PgBouncer** delante de Postgres cuando haya más de ~150 conexiones, o subir `max_connections`.
4. Separar el worker de push/broadcast en su propia cola si los envíos masivos compiten con emails.
5. Réplica de lectura de Postgres para el panel de métricas cuando crezca.
6. CDN delante de S3 para archivos públicos.

## Pendiente para medir
- Prueba de carga con k6 o Locust contra QA (ver `pending.md`).
- Activar Sentry (errores y trazas al 5%) cuando se quiera observabilidad.
