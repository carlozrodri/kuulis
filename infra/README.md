# Infraestructura propia

Servicios que Kuulis aloja en Coolify en vez de usar servidores públicos. Cada carpeta es una app de
Coolify (build pack Dockerfile, `base_directory` = la carpeta, sin dominio público). La API los llama por la red
interna de Coolify con un **alias de red fijo** (Coolify → app → Advanced → Network aliases): `kuulis-osrm` y
`kuulis-photon`. El uuid no sirve como hostname: el contenedor de una app cambia de nombre en cada despliegue.

| Variable (API y worker) | Valor |
| --- | --- |
| `OSRM_URL` | `http://kuulis-osrm:5000` |
| `PHOTON_URL` | `http://kuulis-photon:2322` |

| Carpeta | Servicio | Puerto | Para qué | RAM en uso |
| --- | --- | --- | --- | --- |
| `osrm/` | OSRM 6 (perfil car) | 5000 | Rutas, distancia y tiempo de las cotizaciones (`OSRM_URL`) | ~1 GB |
| `photon/` | Photon 1.0 | 2322 | Búsqueda de direcciones y geocodificación inversa (`PHOTON_URL`) | ~0,4 GB |

Los datos se preparan **al construir la imagen** (descarga + preprocesado), así que la imagen arranca lista y
un redeploy actualiza el mapa. Recomendado: redeploy manual una vez al mes. Cada build necesita ~3 GB de RAM
durante unos minutos; no lanzarlo mientras compila el APK (`kuulis-builder-qa`).

Cobertura: Venezuela completa y la zona de Valencia (España), donde Carlos prueba en QA. Se cambia con los
build args `REGIONS` (OSRM, rutas de Geofabrik) y `SOURCES` (Photon, dumps de Graphhopper con filtro por país
o caja).

Los dos servicios son compartidos por QA y producción (son de solo lectura y no guardan datos de usuarios).
