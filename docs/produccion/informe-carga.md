# Informe de prueba de carga (doc 18)

Fecha: 12-10-2026. Entorno: QA (`kuulis-qa.top8.uk`), con datos sintéticos que se borraron al terminar.
Generador de carga: k6 1.3 en "pc grande" (6 núcleos, 48 GB). Código en `loadtest/`, comandos
`manage.py loadtest-seed | loadtest-report | loadtest-clean | loadtest-pgstats` (`api/apps/loadtest`).

## Resumen

- **Con 600 motorizados, 150 viajes simultáneos, 1500 pasajeros abriendo la app y 5 admins (~2250 usuarios
  conectados, ~220 req/s), QA cumple todos los objetivos de latencia, despacho y errores** (prueba 8): p95
  180 ms, 0 errores 5xx en 148 619 peticiones, 917 de 917 viajes, oferta al motorizado p95 85 ms, asignación
  p95 2,8 s, 0 sockets cortados.
- Eso es **~4–9 veces el pico estimado** en `docs/scaling.md` (500 usuarios simultáneos, 25–50 req/s, ~500
  WebSockets). Se cumple el objetivo de 3 veces el pico.
- **No se cumple "CPU < 70 %"**: en el tramo estable la CPU va al ~75 % de media con picos de 99 %. El límite
  real es la CPU: el servidor de QA solo tiene **8 de los 20 hilos** del i7-12700T. Postgres, Redis y el disco
  están lejos de su límite.
- La API, el worker y Redis se pueden reiniciar con carga sin dejar viajes sin oferta más de 30 s.
- Se encontraron y arreglaron 5 problemas de la app (abajo). El más caro era Argon2 (cada login costaba
  ~230 ms de CPU).

## Escenario

| Pieza | Qué hace |
| --- | --- |
| 600 motorizados | Sesión propia, `POST /drivers/me/online`, un WebSocket real, ubicación cada 4 s, aceptan ofertas y hacen el viaje completo (llegar ~20 s, chat, viaje ~60 s, calificar). Reconectan con backoff como la app. |
| 150 viajes simultáneos | Pasajeros que cotizan, piden, siguen el viaje por WebSocket (ubicación del motorizado, chat) y califican. Reintentan sin parar con cuentas propias. |
| 1500 pasajeros | Abren la app: perfil, tasas, configuración, viaje activo, notificaciones, historial. |
| 5 admins | Viajes en vivo, motorizados en línea y métricas, con 2FA. |
| Campaña de push | 5000 push al minuto 15 (pruebas 1 y 9), a un servidor falso de Expo en el runner. |
| Datos | 5000 pasajeros, 600 motorizados aprobados, 7 admins y 100 000 viajes históricos (`loadtest-seed`, ~15 s). |

Diferencias con la realidad: todo sale de una sola IP por la LAN (sin 4G ni CGNAT real), todos en primer
plano, el 100 % acepta ofertas y los viajes están comprimidos (más eventos por minuto que en la vida real).
Detalle en `/mnt/project-files/kuulis-carga/auditoria-600-motorizados.md` del proyecto.

Medición: k6 (latencias por endpoint, métricas propias de despacho y sockets), node-exporter del servidor de QA
cada 5 s (limitado a los 8 hilos asignados), `cpu.stat` del cgroup de cada contenedor, `pg_stat_activity` y
`pg_stat_statements`, y `loadtest-report` (tiempos de despacho leídos de la base).

## Resultados

| # | Duración | Configuración | req/s estable | p95 | 5xx | Viajes completados | Asignación p95 | Hallazgo |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | 30 min | 4 workers, pool 10+5 | ~200 | 3 s | 1889 | 6 % | — | Refresh limitado a 30/min por IP → 6900 logins con contraseña |
| 2 | 40 min | 4 workers | ~200 | — | pocos | 7 % | — | El simulador no reconectaba sockets (PR #30) |
| 3 | 10 min (parada) | 4 workers | — | — | — | — | — | Postgres casi ocioso: 69 conexiones, ≤ 2 activas |
| 4 | 15 min | 8 workers, pool 8+1 | ~195 | 150–660 ms por minuto | ~1950 en la subida | 84 % | — | La CPU (8 hilos) es el límite; 2255 logins Argon2 en 3 min la saturan |
| 5 | 15 min | + sesiones ya iniciadas | ~220 | 1,0 s | 2 | 99,6 % | 5,4 s | 22 logins/s; refresh 600/min por IP → 512 logins |
| 6 | 15 min | + Argon2 OWASP | ~220 | 351 ms | 1 | 100 % | 3,4 s | 104 logins/s |
| 7 | 15 min | igual | ~220 | 658 ms | 1 | 100 % | — | CPU: API ~3,6 núcleos, worker ~0,35, resto ~1,6 |
| **8** | 15 min | + max-requests 200k | ~220 | **180 ms** | **0** | **100 %** | **2,8 s** | **Cumple todo** salvo CPU < 70 % |
| 9 | 40 min (30 a plena carga) | igual + campaña | 215–237 | 254 ms (86–230 ms por minuto) | 4440, todos en una caída de ~40 s | 97 % | 2,9 s | Caída del servidor entero sin despliegue; la campaña no afectó al despacho |
| 10 | 20 min, caos | reinicio de API, worker y Redis | ~220 | 1,1 s | 779 | 98 % | 3,7 s (base) | 0 viajes sin oferta > 30 s |
| 11 | 20 min, caos | + PR #35 y #36 | CHAOS2 | | | | | |

Prueba 8 en detalle (la de referencia): 148 619 peticiones, p50 24 ms, p95 180 ms, p99 499 ms; oferta p95
85 ms; asignación p95 2,8 s; ~150 ubicaciones/s; 18 592 aperturas de socket con 0 cierres inesperados;
CPU ~75 % de media (picos 99 %), RAM 51 % de 24 GB, iowait máximo 1 %.

Logins con contraseña (fase previa, 16 a la vez, todas las cuentas): **22/s** con el Argon2 anterior y
**~104/s** con los parámetros OWASP.

### Prueba 9 (40 min)

Estable ~30 min a 215–237 req/s con p95 por minuto de 86 a 230 ms (un minuto llegó a 527 ms). Se completaron
2194 de 2266 viajes, la oferta tuvo p95 55 ms y la asignación p95 2,9 s. La campaña de 5000 push se aprobó y
encoló en 4,7 s y no movió el tiempo de despacho. Hacia las 18:32 UTC el servidor entero dejó de responder
~40 s (node-exporter tampoco respondía, los contenedores se reiniciaron, sin despliegue en Coolify; Carlos no
reinició nada, posible corte de red o del host): ahí salieron los 4440 errores. Se recuperó solo en menos de
un minuto. Dejó ver dos fallos, ya arreglados: el simulador moría con páginas HTML del proxy (PR #34) y un
refresh reintentado cerraba todas las sesiones del usuario (PR #35).

### Pruebas de caos (10 y 11)

Reinicios por la API de Coolify con la prueba a plena carga: API al minuto ~12, worker al ~15 y Redis al ~18.

| Reinicio | Efecto (prueba 10) |
| --- | --- |
| API | ~40 s de 502/504 (681 errores) y 1602 sockets cortados; reconectaron solos. ~18 motorizados del simulador quedaron sin socket (arreglado en el simulador, PR #36). |
| Worker | Sin errores. La asignación subió a p95 ~10 s durante 2 min mientras el worker arrancaba y volvió a ~2,7 s. |
| Redis | 97 errores 500 durante unos segundos y 26 sockets cortados; se recuperó solo. |

`loadtest-report` de la prueba 10: 1332 viajes, primera oferta p50 19 ms, p95 172 ms, máximo 3,1 s;
asignación p50 1,9 s, p95 3,7 s, máximo 37 s; **0 viajes en `searching` sin oferta más de 30 s** (criterio de
aceptación). 21 viajes quedaron a medias porque el simulador abandonaba el viaje si un paso daba 5xx; ahora
reintenta como la app (PR #36).

CHAOS2_DETAIL

## Cuellos de botella encontrados y cambios aplicados

| Problema | Efecto | Cambio |
| --- | --- | --- |
| Argon2 dentro del bucle de eventos | Cada login congelaba todo su proceso | Hash en un pool de 2 hilos por proceso. PR #29 |
| Argon2 con parámetros caros (~230 ms de CPU por login) | 22 logins/s; una oleada de logins tumbaba la API | Argon2id OWASP (19 MiB, 2 pasadas, 1 hilo, ~30 ms). Los hashes antiguos se actualizan al iniciar sesión. PR #32 |
| Renovar sesión limitado por IP (30 y luego 600/min) | Con CGNAT, usuarios reales forzados a iniciar sesión con contraseña | `RATE_LIMIT_REFRESH` 3000/min por IP. PR #29 y #32 |
| gunicorn reciclaba cada proceso cada 10 000 peticiones | Cada pocos minutos ~280 sockets cortados y algún 502 | `--max-requests` 200 000 ± 20 000; sin access log duplicado. PR #33 |
| Refresh reintentado tras perder la respuesta = "token robado" | Tras un corte, usuarios desconectados de todos sus dispositivos | Reintento en 30 s recibe los mismos tokens si la sesión no rotó otra vez (aprobado por Carlos). PR #35 |
| CPU del servidor de QA: 8 de 20 hilos | Límite real de capacidad | Pendiente de Carlos (dar más hilos al LXC/VM) |
| Simulador | No reconectaba, moría con HTML, abandonaba viajes | PR #30, #31, #34, #36 |

Lo que **no** hizo falta: PgBouncer (Postgres nunca pasó de unas pocas conexiones activas; máximo configurado
8 × (8+1) + worker = 92 de 150), índices nuevos (`pg_stat_statements` sin consultas lentas relevantes), disco.

## Configuración recomendada para producción

| Pieza | Valor | Por qué |
| --- | --- | --- |
| `WEB_CONCURRENCY` | 8 con 8 hilos (≈ 1 por hilo) | Con 4 procesos solo se usaba media máquina. |
| `DB_POOL_SIZE` / `DB_MAX_OVERFLOW` | 8 / 1 | 8 × 9 + worker 20 = 92 conexiones < 150. |
| `RATE_LIMIT_AUTH` | 20/min por IP (no subir; en QA se subió solo para la prueba) | Protege contra fuerza bruta. |
| `RATE_LIMIT_REFRESH` | 3000/min por IP | CGNAT. |
| Hilos de CPU | Más de 8 si el host lo permite | Es el límite medido. |

## Pendiente (partes 2 y 3 del doc 18)

- Bajar la CPU por petición (~25 ms): cache de las comprobaciones por petición (usuario, suspensiones,
  aceptaciones legales) y de `AppConfig`.
- Colas separadas en Taskiq (`realtime`, `default`, `bulk`); hoy la campaña no afectó, pero el worker
  reiniciado sí retrasa la asignación ~2 min.
- Métricas que faltan (ver auditoría): sockets totales por rol, ubicaciones recibidas por segundo,
  motorizados con GPS reciente, exporters de Redis y Postgres.
- App móvil: frecuencia de ubicación adaptativa (4 s en movimiento, 15 s quieto) y backoff con jitter.
- Retención/particionado de `ride_offers`, `ride_messages` y `audit_log`; `daily_metrics` para el admin.
- Investigar la caída de ~40 s del 12-10 a las 18:32 UTC (host o red; no fue un despliegue).
