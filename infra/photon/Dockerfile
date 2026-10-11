# Self-hosted Photon (address search and reverse geocoding). The index is imported at build time
# from Graphhopper's Photon 1.0 dumps, so a redeploy refreshes it (dumps are rebuilt weekly).
#
# SOURCES: "url|filter" pairs separated by spaces; filter is a list of country codes ("ve") or a
# bbox ("bbox:minLng,minLat,maxLng,maxLat"). Venezuela is the product; the Valencia box is there
# because Carlos tests in Valencia (QA service area). Building needs ~2 GB of RAM.

FROM eclipse-temurin:21-jre AS build
ARG PHOTON_VERSION=1.0.1
ARG SOURCES="https://download1.graphhopper.com/public/south-america/south-america-north/photon-dump-south-america-north-1.0-latest.jsonl.zst|ve https://download1.graphhopper.com/public/europe/spain/photon-dump-spain-1.0-latest.jsonl.zst|bbox:-0.70,39.15,-0.10,39.75"
ARG LANGUAGES=es,en
RUN apt-get update && apt-get install -y --no-install-recommends ca-certificates curl python3 python3-zstandard \
    && rm -rf /var/lib/apt/lists/*
WORKDIR /photon
RUN curl -fsSL --retry 5 -o photon.jar \
    "https://github.com/komoot/photon/releases/download/${PHOTON_VERSION}/photon-${PHOTON_VERSION}.jar"
COPY filter_dump.py .
RUN set -eux; \
    i=0; for source in $SOURCES; do \
      i=$((i+1)); curl -fsSL --retry 5 --retry-delay 10 -o "dump-$i.jsonl.zst" "${source%%|*}"; \
    done; \
    python3 filter_dump.py $(i=0; for source in $SOURCES; do i=$((i+1)); echo "dump-$i.jsonl.zst=${source#*|}"; done) \
      | java -Xmx2g -jar photon.jar import -import-file - -languages "$LANGUAGES" -data-dir /photon; \
    rm dump-*.jsonl.zst; \
    du -sh /photon/photon_data

FROM eclipse-temurin:21-jre
RUN apt-get update && apt-get install -y --no-install-recommends curl && rm -rf /var/lib/apt/lists/*
WORKDIR /photon
COPY --from=build /photon/photon.jar /photon/photon.jar
COPY --from=build /photon/photon_data /photon/photon_data
EXPOSE 2322
HEALTHCHECK --interval=30s --timeout=5s --start-period=60s --retries=3 \
  CMD curl -fsS "http://127.0.0.1:2322/api?q=caracas&limit=1" | grep -q Feature || exit 1
CMD ["java", "-Xmx768m", "-jar", "photon.jar", "serve", "-data-dir", "/photon", "-listen-ip", "0.0.0.0", "-listen-port", "2322"]
