# Pruebas de carga (doc 18)

Generador de carga para medir cuántos usuarios aguanta Kuulis. Corre en su propio servidor
("pc grande" en Coolify) para no quitarle CPU a la API que se mide.

| Pieza | Qué hace |
| --- | --- |
| `k6/kuulis.js` | Escenarios: motorizados conectados enviando ubicación por WebSocket, pasajeros haciendo viajes completos con chat, pasajeros abriendo la app y cotizando, admins con viajes en vivo y métricas. |
| `runner/app.py` | API pequeña con token para lanzar y seguir pruebas, inicia sesión con los admins sintéticos (2FA), mide CPU y RAM del servidor de la API (node-exporter), envía la campaña de push a mitad de prueba e imita el push de Expo (`/expo/push/send`). |
| `api/apps/loadtest` | `manage.py loadtest-seed`, `loadtest-report` y `loadtest-clean`: datos sintéticos, tiempos de despacho medidos en la base y limpieza. Se niegan a correr en producción. |

## Datos sintéticos

Cuentas `lt-p00001…lt-p05000` (pasajeros), `lt-d00001…lt-d00600` (motorizados aprobados con moto)
y `lt-a00001…lt-a00007` (admins con 2FA) en `@loadtest.example.com`, marcadas como cuentas de
prueba. Todas usan la contraseña `LOADTEST_PASSWORD`; el secreto TOTP de cada admin se deriva de
ella (el runner hace lo mismo). Además, 100 000 viajes terminados de los últimos 180 días con el
perfil por hora de `by_hour`, un dispositivo de push por usuario y las aceptaciones legales
vigentes.

```sh
LOADTEST_PASSWORD=... python manage.py loadtest-seed      # ~15 s en local
python manage.py loadtest-report --since 2026-10-12T22:00:00+00:00
python manage.py loadtest-clean                            # borra todo lo sintético
```

En QA se ejecutan dentro del contenedor de la API con una tarea programada de Coolify (la API ya
tiene acceso a la base). `loadtest-clean` también borra de las bandejas de cuentas reales la
notificación de la campaña ("Prueba de carga Kuulis (ignorar)").

## Montaje en Coolify

1. **App `kuulis-loadtest`** en el servidor "pc grande": repositorio `carlozrodri/kuulis`, rama
   `qa`, build pack Dockerfile, base directory `/loadtest`, puerto 8080, volumen persistente en
   `/data`, dominio (por ejemplo `kuulis-carga.top8.uk`). Variables:
   - `RUNNER_TOKEN`: token largo aleatorio para la API del runner.
   - `LOADTEST_PASSWORD`: la misma que en api-qa.
   - `BASE_URL=https://kuulis-qa.top8.uk`
   - `TARGET_IP=192.168.0.148` (opcional): entra por el Nginx Proxy Manager de la LAN sin depender
     del DNS público.
   - `NODE_EXPORTER_URL=http://<ip-del-servidor-de-la-api>:9100/metrics` (opcional).
   - `NODE_CPUS` (opcional): CPUs que el servidor de la API puede usar, por ejemplo `0,4,6,8,10,11,15,19`
     (`python -c "import os; print(os.sched_getaffinity(0))"` dentro de la API). node-exporter ve todos
     los hilos de la máquina física; sin esto un LXC o VM con 8 de 20 hilos marca 40 % cuando está al 100 %.
   - `PUSH_LATENCY_MS=150`: lo que tarda Expo en responder.
2. **node-exporter** en el servidor de la API (imagen `prom/node-exporter`, red del host, puerto
   9100) para medir CPU y RAM durante la prueba.
3. **Durante la prueba**, en api-qa y worker-qa: `LOADTEST_PASSWORD`, `RATE_LIMIT_AUTH` alto (todas
   las sesiones salen de una sola IP), `EXPO_PUSH_URL=https://<dominio-del-runner>/expo/push/send`
   y los valores de producción (`WEB_CONCURRENCY=4`, pool 10+5). Al terminar se vuelven a dejar
   como estaban.

## Correr una prueba

```sh
curl -X POST https://kuulis-carga.top8.uk/api/runs -H "Authorization: Bearer $RUNNER_TOKEN" \
  -H 'Content-Type: application/json' \
  -d '{"env": {"DURATION": "30m", "RAMP": "5m", "SCALE": 1}, "admins": 5, "campaign_at": "15m"}'
curl https://kuulis-carga.top8.uk/api/runs/<id> -H "Authorization: Bearer $RUNNER_TOKEN"
curl -X POST https://kuulis-carga.top8.uk/api/runs/<id>/stop -H "Authorization: Bearer $RUNNER_TOKEN"
```

Antes de lanzar k6 el runner inicia sesión con todas las cuentas sintéticas (16 a la vez) y le pasa
los refresh tokens: como en la vida real, los usuarios abren la app con la sesión ya iniciada (un
refresh) en lugar de miles de logins con contraseña en la subida. Esa fase mide además cuántos logins
por segundo aguanta la API (`prelogin` en `meta.json`). Opciones: `"prelogin": false` para no hacerlo,
`"prelogin_workers"` para cambiar la concurrencia. Los tokens se borran al terminar.

Los sockets de motorizados y de viajes se reconectan solos como en la app (1 s, duplicando hasta 30 s),
y el viaje se vuelve a leer tras reconectar; `ws_reconnects` cuenta las reconexiones.
Si mientras la API se reinicia el proxy responde con una página HTML (aunque sea un 200), el script la
trata como un fallo y sigue; `http_not_json` cuenta esas respuestas.

Opciones (`env`): `SCENARIOS` (`drivers,riders,browsers,admins`), `SCALE` (multiplica motorizados,
viajes y pasajeros), `DRIVERS` (600), `RIDES` (150 viajes simultáneos), `BROWSERS` (1500),
`DURATION`, `RAMP`, `LOCATION_S` (4), `ARRIVE_S` (20), `TRIP_S` (60), `SEARCH` (`0` quita las búsquedas
de direcciones: antes de cada cotización se hace un `/geo/reverse` y 2–3 `/geo/search`, como al escribir en la
app; necesitan photon encendido), `APP_MODEL` (`app`, por defecto: los pasajeros que abren la app piden
lo mismo que la app móvil, con `/app/bootstrap` y las cachés de React Query; `legacy`: la mezcla de las pruebas de
octubre, seis peticiones en cada apertura), `P_ACCOUNTS` / `D_ACCOUNTS`
(cuentas sembradas). Cada prueba guarda en `/data/runs/<id>/`: `summary.json` de k6,
`metrics.csv.gz` (cada petición), `node.jsonl` (CPU y RAM cada 5 s), `push.jsonl` y
`campaign.jsonl`.

Umbrales (doc 18): p95 de API < 300 ms, 0 errores 5xx, oferta entregada al motorizado < 2 s,
viajes completados > 95 %. El tiempo desde el pedido hasta la primera oferta se mide además en la
base con `loadtest-report`.

## Probar en local

Con la API y el worker corriendo (`EXPO_PUSH_URL=http://127.0.0.1:8090/expo/push/send`):

```sh
LOADTEST_PASSWORD=... uv run python manage.py loadtest-seed --passengers 60 --drivers 10
k6 run -e PASSWORD=... -e DRIVERS=4 -e RIDES=2 -e BROWSERS=3 -e P_ACCOUNTS=60 -e D_ACCOUNTS=10 \
  -e DURATION=60s -e RAMP=2s -e ARRIVE_S=5 -e TRIP_S=10 loadtest/k6/kuulis.js
```
