#!/usr/bin/env bash
# Builds the APK for this image's source once (skipped if the same source was already built), uploads it to
# S3 and then only serves the status page (http://<container>:8080/) so Coolify sees the container healthy.
#
# Env: EXPO_TOKEN, EXPO_OWNER (Expo account), AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY, AWS_S3_ENDPOINT,
# AWS_S3_BUCKET, optional AWS_S3_REGION, BUILD_PROFILE (eas.json profile, default qa) and APP_ENV (default qa).
set -uo pipefail

PROFILE="${BUILD_PROFILE:-qa}"
export APP_ENV="${APP_ENV:-qa}"
STATUS_DIR=/tmp/status
mkdir -p "$STATUS_DIR" /cache
status() { printf '%s %s\n' "$(date -u +%FT%TZ)" "$*" | tee -a "$STATUS_DIR/index.html"; }

# Serve the status log right away (the healthcheck only needs the server).
python3 -m http.server 8080 --directory "$STATUS_DIR" > /dev/null 2>&1 &

SOURCE_ID=$(cd /src && find . -type f -not -path './builder/*' -print0 | sort -z | xargs -0 sha256sum | sha256sum | cut -c1-10)
NAME="kuulis-${APP_ENV}-${PROFILE}-$(date -u +%Y%m%d-%H%M)-${SOURCE_ID}.apk"
MARK="/cache/built-${PROFILE}-${SOURCE_ID}"

build() {
  if [ -f "$MARK" ]; then
    status "Source ${SOURCE_ID} (${PROFILE}) was already built: $(cat "$MARK")"
    return 0
  fi
  status "Building ${PROFILE} APK for source ${SOURCE_ID}"
  rm -rf /work && cp -a /src /work && cd /work || return 1
  npm ci --no-audit --no-fund || { status "npm ci failed"; return 1; }
  mkdir -p /out
  if ! eas build --local --platform android --profile "$PROFILE" --non-interactive --output "/out/${NAME}"; then
    status "Build failed (see the container logs)"
    return 1
  fi
  status "Built ${NAME} ($(du -h "/out/${NAME}" | cut -f1)), uploading to S3"
  python3 /src/builder/upload.py "/out/${NAME}" "builds/${APP_ENV}/${NAME}" "builds/${APP_ENV}/kuulis-${APP_ENV}-${PROFILE}-latest.apk" \
    | tee -a "$STATUS_DIR/index.html" || { status "Upload failed"; return 1; }
  echo "builds/${APP_ENV}/${NAME}" > "$MARK"
  rm -rf /work "/out/${NAME}"
  status "Done"
}

START=$(date +%s)
build
status "Finished in $(( ($(date +%s) - START) / 60 )) min"
wait
