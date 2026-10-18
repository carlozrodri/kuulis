# Análisis: migrar la infraestructura a Cloudflare

**Fecha:** 2026-10-18 · **Tipo:** análisis (no cambia código) · **Pedido por:** Carlos

Pregunta: ¿se puede mover la API, Photon y OSRM (y lo demás que corre en Coolify) a los servicios
serverless de Cloudflare (Workers, Containers, Durable Objects, D1, R2, Hyperdrive, Queues), con el objetivo
de **gastar lo mínimo** y que la API sea **rápida para usuarios en Caracas**?

## Resumen

- **Sí es técnicamente posible, pero no conviene hoy.** Lo único que encaja sin reescribir es meter los
  contenedores actuales en Cloudflare Containers, y eso **no resuelve Postgres ni Redis** (los contenedores no
  tienen disco persistente), así que habría que pagar además una base de datos y un Redis gestionados.
  Estimación: **~140–160 USD/mes** frente a **~5–10 USD/mes** de luz que cuesta hoy el homelab.
- **La latencia solo mejora si se mueve todo junto** (API + Postgres + Redis) cerca de Venezuela. Mover solo la
  API a Cloudflare y dejar la base de datos en Valencia (España) la haría **más lenta**: cada petición hace
  varias consultas y cada una cruzaría el Atlántico.
- **Cloudflare no tiene centro de datos en Venezuela.** Los más cercanos son Bogotá, Barranquilla, Medellín,
  Panamá, Puerto España y Miami.
- **La versión 100 % serverless** (reescribir la API en TypeScript sobre Workers + Durable Objects) sería la más
  barata en Cloudflare (~30–70 USD/mes con la base de datos), pero implica reescribir las 36 apps de la API.
  No compensa.
- **Recomendación:**
  1. Ahora: seguir en el homelab y aprovechar lo gratis de Cloudflare (Tunnel, proxy con caché para la web y
     archivos estáticos, R2 para archivos de usuarios).
  2. Cuando haya usuarios reales en Caracas y la latencia o la disponibilidad del homelab importen: mover el
     **mismo Coolify** a un VPS en la costa este de EE. UU. (Miami o Virginia). Es el mismo código, con la misma
     latencia que Cloudflare y a una fracción del costo.

## 1. Infraestructura actual (lo que habría que migrar)

Datos tomados del repo (rama `qa`) y de la memoria del proyecto.

| Pieza | Qué es | Recursos medidos | Estado |
| --- | --- | --- | --- |
| API | FastAPI + gunicorn/uvicorn, Python 3.13, **WebSockets** (`/api/v1/ws`) con fan-out por Redis pub/sub (`api/apps/realtime/manager.py`) | ~25 ms de CPU por petición; 220 req/s con 8 hilos (`docs/scaling.md`) | QA |
| Worker + scheduler | Taskiq (misma imagen, `PROCESS_TYPE=worker`), colas en Redis Streams, backups con `pg_dump` | bajo | QA |
| PostgreSQL 17 | base principal | ociosa en la prueba de carga (≤ 2 conexiones activas) | QA |
| Redis 7.4 | refresh tokens, ubicaciones GEO, cola de tareas, set de despacho, rate limits, pub/sub | bajo | QA |
| OSRM 6 | rutas (`infra/osrm`), Venezuela + Valencia, perfil car, MLD | ~1 GB RAM; build ~3 GB | compartido |
| Photon 1.0 | direcciones (`infra/photon`), Java, `-Xmx768m` | ~0,4 GB RAM en uso; build ~2 GB | compartido |
| Admin | Nuxt 4 (SSR, Node) | bajo | QA |
| Web pública | Nuxt (SSR, Node) en `kuulis.top8.uk` | bajo | QA |
| S3 de archivos | MinIO del homelab (`s3.top8.uk`): documentos de motorizados, fotos, recibos | — | QA |
| Backups | Cloudflare R2 (ya en uso) | — | QA |
| Otros | GlitchTip, builder de APK, runner de carga, Expo QA | — | homelab |

Servidor: LXC/VM en un i7-12700T con 8 hilos y 24 GB, en casa de Carlos en **Valencia, España**. Cadena:
cliente → Nginx Proxy Manager → Traefik de Coolify → API. Los dominios `kuulis-*.top8.uk` **no pasan hoy por el
proxy de Cloudflare** (verificado el 2026-10-11). Producción está apagada.

**Costo actual (inferido, no medido):** el hardware y la conexión ya los paga Carlos. El costo marginal es la luz:
un equipo así consume ~30–60 W, unos 25–45 kWh/mes, **~5–10 USD/mes**. R2 entra en la capa gratuita (10 GB).

## 2. Latencia desde Caracas

- Cloudflare no lista ningún centro de datos en Venezuela. Los más cercanos son Bogotá (BOG), Barranquilla
  (BAQ), Medellín (MDE), Panamá (PTY), Puerto España (POS) y Miami (MIA). Fuente: lista de componentes de
  `cloudflarestatus.com/api/v2/components.json`, consultada el 2026-10-18. A cuál llega cada usuario depende de
  su operador (CANTV, Movistar, Digitel, Inter…). Muchos operadores venezolanos salen por Miami (**inferido**).
- Ida y vuelta Caracas → España: ~130–170 ms. Caracas → Miami o Virginia: ~50–90 ms (**rangos típicos
  inferidos, no medidos**; conviene medirlos desde teléfonos reales en Caracas antes de decidir).
- **Lo que manda es dónde están los datos.** Una petición típica de la API hace varias consultas a Postgres y
  Redis. Si la API corre en Miami y Postgres en España, cada consulta suma ~100 ms o más. La API, Postgres y
  Redis deben estar en la misma región.
- Poner solo el proxy de Cloudflare delante (sin mover nada) termina el TLS cerca del usuario, lo que ahorra
  ida y vuelta al abrir conexiones nuevas, y sirve en caché la web y los archivos estáticos. Pero cada petición
  a la API sigue viajando hasta España. Mejora un poco, no cambia el orden de magnitud.
- Containers: Cloudflare arranca la instancia en la ubicación con capacidad más cercana a quien la pide, y
  puede cambiar de sitio al reiniciarse (doc de arquitectura de Containers). Los Durable Objects admiten
  pistas de ubicación (por ejemplo, este de Norteamérica) para fijarlos cerca de la base de datos.

## 3. Qué ofrece Cloudflare y cómo encaja cada pieza

Precios del plan Workers Paid, verificados en la documentación oficial el **2026-10-18**:

| Servicio | Precio | Fuente (actualizada) |
| --- | --- | --- |
| Workers Paid | 5 USD/mes mínimo; 10 M peticiones y 30 M ms de CPU incluidos; luego 0,30 USD/M peticiones y 0,02 USD/M ms de CPU; sin cobro por transferencia | [Workers pricing](https://developers.cloudflare.com/workers/platform/pricing/) (2026-10-02) |
| Durable Objects | 1 M peticiones incluidas, luego 0,15 USD/M; 400 000 GB-s incluidos, luego 12,50 USD/M GB-s; mensajes WebSocket entrantes cuentan 20:1; los salientes son gratis; hibernando no cobra duración | ídem |
| D1 (SQLite) | 25 000 M filas leídas y 50 M escritas incluidas; 5 GB incluidos, luego 0,75 USD/GB-mes | ídem |
| Queues | 1 M operaciones incluidas, luego 0,40 USD/M (~3 operaciones por mensaje) | ídem |
| Hyperdrive | consultas ilimitadas en Paid; conecta a Postgres privado por Cloudflare Tunnel + Access (requiere TLS en Postgres) | [Hyperdrive](https://developers.cloudflare.com/hyperdrive/) y [base privada](https://developers.cloudflare.com/hyperdrive/configuration/connect-to-private-database/) (2026-10-12) |
| Containers | incluidos 25 GiB-h de memoria, 375 min de vCPU y 200 GB-h de disco; luego 0,0000025 USD/GiB-s (**0,009 USD/GiB-h**), 0,000020 USD/vCPU-s y 0,00000007 USD/GB-s. La memoria y el disco se cobran por lo **aprovisionado** mientras corre; la CPU, por uso. Salida: 1 TB incluido en Norteamérica y Europa, 500 GB en el resto | [Containers pricing](https://developers.cloudflare.com/containers/pricing/) (2026-10-05) |
| Límites de Containers | tipos de `lite` (1/16 vCPU, 256 MiB) a `standard-4` (4 vCPU, 12 GiB, 20 GB); personalizados de 1–4 vCPU con ≥ 3 GiB por vCPU; imagen ≤ 20 GB; 50 GB de imágenes por cuenta; **disco efímero** (solo snapshots o FUSE sobre R2); arranque en frío de 1–3 s; por defecto se duermen tras 10 min sin uso | [Limits](https://developers.cloudflare.com/containers/platform-details/limits/) (2026-10-12), [Architecture](https://developers.cloudflare.com/containers/platform-details/architecture/) (2026-09-30) |
| R2 | 0,015 USD/GB-mes; 4,50 USD/M escrituras, 0,36 USD/M lecturas; capa gratis de 10 GB, 1 M escrituras y 10 M lecturas; **salida gratis** | [R2 pricing](https://developers.cloudflare.com/r2/pricing/) (2026-10-01) |

Encaje pieza por pieza:

| Pieza | Opción en Cloudflare | ¿Encaja? |
| --- | --- | --- |
| API FastAPI | Containers detrás de un Worker + Durable Object | Sí, sin reescribir. Hay que repartir la carga entre instancias a mano (cada instancia es un Durable Object) y evitar que se duerma. Los WebSockets pasan por el Durable Object. |
| API reescrita | Workers (TypeScript) + Durable Objects para WebSockets y despacho | Técnicamente es lo ideal, pero implica **reescribir toda la API** (36 apps, tests, migraciones). |
| PostgreSQL | No existe Postgres gestionado en Cloudflare. D1 es SQLite (otro dialecto, 10 GB por base). Hyperdrive solo acelera una base que ya existe en otro sitio. | **No.** Hace falta Neon, Supabase o similar, o dejarlo en el homelab (lento desde EE. UU.). |
| Redis | No hay Redis en Cloudflare. KV es eventual (no sirve para despacho ni rate limits). Los Durable Objects pueden reemplazar parte de la lógica, pero eso es reescribir. | **No sin reescribir.** Hace falta Upstash o similar. Redis en un contenedor sin disco pierde sesiones y colas en cada reinicio. |
| Worker Taskiq + scheduler | Container siempre encendido, o Queues + Cron Triggers (reescribiendo) | Sí en contenedor. |
| OSRM | Container con los datos dentro de la imagen (ya se construyen así) | Sí. Necesita ≥ 2 GiB para ir holgado y siempre encendido (o aceptar arranque en frío + carga del mapa). |
| Photon | Container (Java) con el índice en la imagen | Sí. ~1,2 GB con la JVM. Puede ir en la misma instancia que OSRM con una imagen combinada. |
| Admin y web (Nuxt) | Workers (Nuxt tiene preset `cloudflare`) o Pages | Sí, y casi gratis. |
| S3 (MinIO) | R2 | **Sí, muy bien:** misma API S3, salida gratis, ya se usa para backups. |
| Backups | R2 | Ya está. |
| GlitchTip, builder de APK, runner de carga | — | Se quedan en el homelab (no hace falta moverlos). |

## 4. Escenarios y costo mensual estimado

Supuestos para 5000 usuarios activos al día (de `docs/scaling.md`): pico de 25–50 req/s, ~26 M peticiones al
mes, ~300 motorizados conectados de media 8 h/día enviando GPS cada 4 s (~65 M mensajes WebSocket al mes),
~25 ms de CPU por petición en Python. Todo en USD, sin impuestos. **Son estimaciones**: el tráfico real puede
ser distinto.

### A. Lift-and-shift a Cloudflare Containers + base de datos y Redis externos

| Concepto | Cálculo | USD/mes |
| --- | --- | --- |
| Plan Workers Paid | mínimo | 5 |
| API: 2 instancias de 1 vCPU / 3 GiB siempre encendidas | memoria 4380 GiB-h → ~39; CPU 650 000 vCPU-s → ~12,5; disco ~1,5 | ~53 |
| Peticiones Worker + Durable Object delante de la API | 16 M extra × 0,30 + 25 M DO × 0,15 | ~9 |
| Worker + scheduler: `basic` (1/4 vCPU, 1 GiB) | memoria ~6,5; CPU ~5 | ~12 |
| OSRM + Photon en una instancia de 1 vCPU / 3 GiB | memoria ~19,7; CPU ~1–3 | ~22 |
| Postgres en Neon (Launch, 0,5 CU siempre encendido + 5 GB) | 365 CU-h × 0,106 + 5 × 0,35 | ~40 |
| Redis en Upstash (fijo 250 MB, comandos ilimitados, 50 GB de tráfico) | el pago por uso costaría cientos de USD con el GPS | 10–20 |
| Admin y web en Workers | dentro del plan | ~0 |
| Archivos en R2 | < 10 GB | 0–1 |
| **Total** | | **~150** |

Neon y Upstash: precios de [neon.com/pricing](https://neon.com/pricing) y
[upstash.com/pricing/redis](https://upstash.com/pricing/redis), consultados el 2026-10-18. Falta comprobar
que ambos tengan región en el este de EE. UU. junto a los contenedores (es lo habitual), y que el plan fijo de
Upstash aguante el tráfico de pub/sub del GPS.

### B. Reescritura nativa (Workers + Durable Objects + D1 o Postgres por Hyperdrive)

Peticiones ~5 USD extra, CPU (TypeScript, ~5 ms) ~2 USD, Durable Objects para sockets ~1–5 USD, D1 dentro de lo
incluido, más OSRM y Photon en contenedor ~22 USD, más el plan, 5 USD. **~35–40 USD/mes** con D1 o **~70–80**
con Neon. A cambio de **meses de reescritura** (toda la API, tests, migraciones, backups), y con D1 hay que
dejar Postgres. **No recomendado.**

### C. Mismo Coolify en un VPS en la costa este de EE. UU.

Mover el stack tal cual (Coolify, Postgres, Redis, API, worker, OSRM, Photon) a un VPS de 4 vCPU / 8–16 GB en
Miami o Virginia (Hetzner Ashburn, Vultr o DigitalOcean Miami, etc.). **Precio por verificar** cuando se
decida; suele estar en **~20–50 USD/mes**. Misma latencia que el escenario A, sin cambiar código, y los
backups a R2 ya permiten restaurar ahí (plan de contingencia del doc `docs/produccion/02`).

### D. Quedarse en el homelab + lo gratis de Cloudflare (recomendado ahora)

| Qué | Para qué | Costo |
| --- | --- | --- |
| Cloudflare Tunnel | Publicar sin abrir puertos de casa; protege la IP pública | gratis |
| Proxy de Cloudflare (plan Free) en web, admin y API | TLS cerca del usuario, caché de la web y los estáticos, protección DDoS. Soporta WebSockets. Hay que adaptar la confianza en la IP real (`CF-Connecting-IP`, rangos de Cloudflare en `FORWARDED_ALLOW_IPS`), porque los rate limits dependen de ella | gratis |
| R2 en lugar de MinIO para archivos de usuarios | Sale del disco de casa, salida gratis, se puede servir con caché | 0–1 |
| Web pública en Workers/Pages | La web carga rápido desde Bogotá o Miami aunque el homelab caiga | gratis |

Costo: **~5–10 USD/mes** (la luz de hoy). La API sigue a ~130–170 ms de Caracas.

### Comparación

| | A. Containers | B. Nativo | C. VPS EE. UU. | D. Homelab + gratis |
| --- | --- | --- | --- | --- |
| USD/mes | ~150 | ~35–80 | ~20–50 (por verificar) | ~5–10 |
| Latencia desde Caracas | buena (~50–90 ms) | la mejor (borde) | buena (~50–90 ms) | media (~130–170 ms) |
| Cambios de código | pocos (balanceo, sin Redis local) | reescritura total | ninguno | casi ninguno |
| Disponibilidad | alta | alta | la del proveedor | la de la casa de Carlos (luz, internet) |
| Riesgo | medio | alto | bajo | bajo hoy, alto con usuarios reales |

## 5. Pros y contras de ir a Cloudflare

**Pros**
- Sin servidores que mantener, escalado automático y alta disponibilidad, sin depender de la luz ni del
  internet de casa.
- Borde cerca de Venezuela (Bogotá, Panamá, Miami) para todo lo que se pueda cachear o resolver en el borde.
- R2 sin cobro de salida y Workers sin cobro de transferencia: lo que más se transfiere (fotos, web) sale gratis.
- Protección DDoS y WAF básicos incluidos.

**Contras**
- **No hay Postgres ni Redis gestionados en Cloudflare**: lo más caro del escenario A está fuera de Cloudflare.
- Containers cobran la **memoria aprovisionada** todo el tiempo que están encendidos. Una app de viajes necesita
  la API, OSRM y Photon siempre encendidos, así que no se aprovecha el "pagar solo por uso".
- Disco efímero: nada con estado puede vivir en un contenedor.
- La arquitectura de Containers (Worker → Durable Object → contenedor) obliga a balancear la carga a mano y
  añade un salto y peticiones facturables.
- Dependencia de un proveedor: la versión nativa ata el código a Workers/Durable Objects.
- La reescritura nativa es mucho trabajo para ahorrar unos 100 USD/mes frente al escenario A, y aun así cuesta
  más que el VPS.

## 6. Riesgos

- **Bloqueos en Venezuela.** CANTV ha bloqueado por IP servicios de Cloudflare en algunas oleadas (por
  ejemplo, el DNS 1.1.1.1 en enero de 2025, según
  [Internet Society Pulse](https://pulse.internetsociety.org/en/shutdowns/content-blocking-in-venezuela-4-january-2025/);
  [El Diario](https://eldiario.com/2025/01/08/bloqueo-servidores-dns-publicos-google-cantv/) informó otra cosa
  el 8 de enero). Si un bloqueo afectara a rangos de Cloudflare, la app dejaría de funcionar para los usuarios
  de ese operador. El riesgo existe con cualquier proveedor, pero Cloudflare es un objetivo más visible que una IP
  propia. Conviene vigilarlo con [VE sin Filtro](https://vesinfiltro.org/) y Cloudflare Radar.
- **Ubicación de los contenedores:** Cloudflare decide dónde arrancan; tras un reinicio pueden quedar lejos de
  la base de datos. Hay que fijar la región con pistas de ubicación y medir.
- **Precios que cambian:** el almacenamiento SQLite de Durable Objects empezó a cobrarse en enero de 2026, y
  Containers es un producto joven cuyo precio y límites siguen cambiando (las páginas se actualizaron en
  septiembre y octubre de 2026).
- **Costo variable:** con pago por uso, un pico, un bug o un abuso (bucle de reconexión de WebSocket, scraping)
  se convierte en factura. Hay que poner alertas de gasto.
- **Homelab (si no se migra):** un corte de luz o internet en Valencia deja la app caída en Caracas. Ya hubo un
  corte de ~40 s del servidor completo durante la prueba de carga del 2026-10-12.

## 7. Recomendación y cuándo revisarla

1. **Ahora (sin usuarios reales):** escenario D. Seguir en el homelab y, cuando se encienda producción, ponerla
   detrás de Cloudflare (Tunnel + proxy), mover los archivos de usuarios de MinIO a R2 y la web pública a
   Workers/Pages. Costo ≈ 0 adicional.
2. **Antes del lanzamiento en Caracas:** medir la latencia real desde teléfonos en Caracas (CANTV, Movistar y
   Digitel) contra España y contra un VPS de prueba en Miami o Virginia.
3. **Con usuarios reales**, o si la latencia medida pasa de ~150 ms o el homelab se cae: escenario C (mover el
   mismo Coolify a un VPS en el este de EE. UU. restaurando desde los backups de R2). Mantener Cloudflare
   delante.
4. **Revisar Cloudflare Containers** si en el futuro: (a) Cloudflare ofrece Postgres o Redis gestionados, o
   Containers con disco persistente; (b) el tráfico crece tanto que un solo VPS no alcanza y hace falta
   escalar sin administrar servidores. Antes de eso, pagar ~150 USD/mes por lo que un VPS de ~20–50 USD hace
   no cumple el objetivo de gastar lo mínimo.
