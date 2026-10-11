# Self-hosted OSRM (routes for quotes and the live map). The map is preprocessed at build time, so
# the image is ready to serve and a redeploy refreshes the map (Geofabrik updates daily; do it monthly).
#
# REGIONS: space-separated Geofabrik paths merged into one map. Venezuela is the product; Valencia
# (Spain) is there because Carlos tests in Valencia (QA service area). Building needs ~3 GB of RAM.

ARG OSRM_IMAGE=ghcr.io/project-osrm/osrm-backend:v6.0.0

FROM debian:bookworm-slim AS download
ARG REGIONS="south-america/venezuela europe/spain/valencia"
RUN apt-get update && apt-get install -y --no-install-recommends ca-certificates curl osmium-tool \
    && rm -rf /var/lib/apt/lists/*
WORKDIR /data
RUN set -eux; \
    for region in $REGIONS; do \
      curl -fsSL --retry 5 --retry-delay 10 -o "$(basename "$region").osm.pbf" \
        "https://download.geofabrik.de/${region}-latest.osm.pbf"; \
    done; \
    if [ "$(ls *.osm.pbf | wc -l)" -gt 1 ]; then osmium merge *.osm.pbf -o map.osm.pbf; \
    else mv *.osm.pbf map.osm.pbf; fi; \
    ls -la

FROM ${OSRM_IMAGE} AS build
COPY --from=download /data/map.osm.pbf /data/map.osm.pbf
# Car profile: motorbikes in Caracas use the same streets and one-ways as cars.
RUN osrm-extract -p /opt/car.lua /data/map.osm.pbf \
    && osrm-partition /data/map.osrm \
    && osrm-customize /data/map.osrm \
    && rm /data/map.osm.pbf

# The OSRM image is Alpine: busybox wget serves the health check, nothing to install.
FROM ${OSRM_IMAGE}
COPY --from=build /data /data
EXPOSE 5000
HEALTHCHECK --interval=30s --timeout=5s --start-period=60s --retries=3 \
  CMD wget -qO- "http://127.0.0.1:5000/route/v1/driving/-66.88,10.49;-66.85,10.50?overview=false" | grep -q '"Ok"' || exit 1
CMD ["osrm-routed", "--algorithm", "mld", "--max-table-size", "1000", "/data/map.osrm"]
