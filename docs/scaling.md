# Escalabilidad (objetivo inicial: 5000 usuarios activos)

## Estimación
5000 usuarios activos al día con un pico de ~10% concurrentes son ~500 usuarios simultáneos. Con una
petición cada 10–20 s por usuario activo son 25–50 req/s en pico, más ~500 WebSockets abiertos. Un solo
contenedor de API con 4 workers async aguanta esto con margen (cada worker atiende cientos de peticiones
concurrentes mientras espera I/O).

## Medido (prueba de carga del 12-10-2026, `docs/produccion/informe-carga.md`)
Servidor de QA con **8 hilos** (de un i7-12700T) y 24 GB, API con 8 workers:
- 600 motorizados con socket y GPS cada 4 s, 150 viajes simultáneos, 1500 pasajeros abriendo la app y 5 admins
  (~2250 usuarios conectados, **~220 req/s**): p95 180 ms, 0 errores, asignación p95 2,8 s, oferta p95 85 ms.
- Es ~4–9 veces la estimación de arriba. **El límite es la CPU** (~75 % de media, picos de 99 %): ~25 ms de
  CPU por petición. Postgres (≤ 2 conexiones activas), Redis y el disco van sobrados.
- Logins con contraseña: ~104/s (Argon2 OWASP). Renovar sesión es barato.
- Reiniciar API, worker o Redis con carga: ~40 s de errores (API), segundos (Redis), ningún viaje sin oferta
  más de 30 s.

## Configuración actual por entorno

| Pieza | Valor | Dónde se cambia |
| --- | --- | --- |
| Workers gunicorn por contenedor API | 4 (`WEB_CONCURRENCY`); recomendado 1 por hilo de CPU (8 con 8 hilos) | env en Coolify |
| Pool Postgres por worker API | 10 + 5 overflow (prod); con 8 workers, 8 + 1 | `DB_POOL_SIZE`, `DB_MAX_OVERFLOW` |
| Procesos worker Taskiq | 2 (`WORKER_CONCURRENCY`), pool 5 + 5 | env del worker |
| Tareas async por proceso worker | 100 | `WORKER_MAX_ASYNC_TASKS` |
| Conexiones Postgres máximas usadas | 4×15 + 2×10 = 80 (< 100 por defecto) | — |
| Rate limit general | 120/min por IP | `RATE_LIMIT_DEFAULT` |
| Rate limit login/registro | 20/min por IP | `RATE_LIMIT_AUTH` |
| Rate limit renovar sesión | 3000/min por IP (CGNAT: muchos usuarios por IP) | `RATE_LIMIT_REFRESH` |
| Hash de contraseñas | Argon2id 19 MiB, 2 pasadas, 1 hilo (OWASP; ~30 ms de CPU por login) | `kuulis/core/security.py` |

| Conexiones Redis por proceso API | 100; si se agotan la petición espera hasta 5 s en vez de fallar | `REDIS_MAX_CONNECTIONS`, `REDIS_POOL_TIMEOUT` |

Además: sin `pool_pre_ping` (costaba ~10 % de la CPU de una petición y no evita errores si Postgres se
reinicia; activable con `DB_POOL_PRE_PING`), totales HTTP de monitoreo escritos en Redis una vez por segundo
por proceso, reciclado de conexiones cada 30 min, `max-requests` alto (200k ± 20k por proceso: reciclar un worker corta sus WebSockets) para
evitar fugas de memoria, gzip, índices en email, rol, `user_id` y `(user_id, created_at)` de notificaciones,
paginación con límite máximo de 100, broadcast de notificaciones en lotes de 500 por keyset.

## Cómo crecer (en orden)
1. Subir `WEB_CONCURRENCY` (≈ 1 por hilo de CPU: más procesos que hilos no ayuda porque la API está limitada
   por CPU) y ajustar el pool para no pasar de `max_connections`. Dar más hilos al servidor es lo más barato:
   con 8 hilos aguanta ~220 req/s; la capacidad crece casi lineal con los hilos mientras Postgres siga ocioso.
2. Añadir un segundo servidor en Coolify y repartir API/worker; Redis pub/sub y Redis rate limit ya lo permiten.
3. Poner **PgBouncer** delante de Postgres cuando haya más de ~150 conexiones, o subir `max_connections`.
4. Separar el worker de push/broadcast en su propia cola si los envíos masivos compiten con emails.
5. Réplica de lectura de Postgres para el panel de métricas cuando crezca.
6. CDN delante de S3 para archivos públicos.

Cuándo pasar al siguiente paso: cuando la CPU media en hora pico supere el 70 % (con 8 hilos, a partir de unos
~200 req/s sostenidos, es decir unos 2000 usuarios conectados a la vez con el uso simulado).

## Pendiente para medir
- Repetir la prueba (`loadtest/README.md`) tras cambios grandes o antes de abrir una ciudad nueva.
- Métricas que faltan en producción: sockets totales por rol, ubicaciones por segundo, Redis y Postgres.
- Activar Sentry (errores y trazas al 5%) cuando se quiera observabilidad.
