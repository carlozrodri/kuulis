#!/usr/bin/env bash
# Compiles this image's source once (skipped if the same source was already done), uploads the result to S3
# and then only serves the status page (http://<container>:8080/) so Coolify sees the container healthy.
#
# When an APK built from the same native code (expo-updates runtime version, a fingerprint of native
# dependencies and config) is already in S3, it exports a JS update (OTA) instead, in about a minute; the admin
# publishes it from Versiones. Otherwise it builds a new APK. FORCE_APK=1 always builds the APK.
#
# Env: EXPO_TOKEN, EXPO_OWNER (Expo account), AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY, AWS_S3_ENDPOINT,
# AWS_S3_BUCKET, optional AWS_S3_REGION, BUILD_PROFILE (eas.json profile, default qa), APP_ENV (default qa)
# and FORCE_APK.
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
  status "Compiling ${PROFILE} for source ${SOURCE_ID}"
  rm -rf /work && cp -a /src /work && cd /work || return 1
  npm ci --no-audit --no-fund || { status "npm ci failed"; return 1; }
  mkdir -p /out
  RUNTIME=$(npx expo-updates runtimeversion:resolve --platform android \
    | python3 -c 'import json, sys; print(json.load(sys.stdin)["runtimeVersion"] or "")')
  if [ -z "$RUNTIME" ]; then status "Could not resolve the runtime version"; return 1; fi
  if [ "${FORCE_APK:-0}" != "1" ] && APK_RUNTIME=$(python3 /src/builder/ota.py has-apk "$RUNTIME"); then
    status "Native code unchanged (runtime ${RUNTIME}): exporting a JS update"
    rm -rf /out/update
    if ! npx expo export --platform android --output-dir /out/update; then
      status "Export failed (see the container logs)"
      return 1
    fi
    npx expo config --type public --json > /out/update/expoConfig.json || { status "expo config failed"; return 1; }
    python3 /src/builder/ota.py upload /out/update "$APK_RUNTIME" "$SOURCE_ID" \
      | tee -a "$STATUS_DIR/index.html" || { status "Upload failed"; return 1; }
    echo "update for runtime ${APK_RUNTIME}" > "$MARK"
    rm -rf /work /out/update
    status "Done"
    return 0
  fi
  status "New native code (runtime ${RUNTIME}): building the APK"
  if ! eas build --local --platform android --profile "$PROFILE" --non-interactive --output "/out/${NAME}"; then
    status "Build failed (see the container logs)"
    return 1
  fi
  status "Built ${NAME} ($(du -h "/out/${NAME}" | cut -f1)), uploading to S3"
  python3 /src/builder/upload.py "/out/${NAME}" "builds/${APP_ENV}/${NAME}" "builds/${APP_ENV}/kuulis-${APP_ENV}-${PROFILE}-latest.apk" "$PROFILE" "$RUNTIME" \
    | tee -a "$STATUS_DIR/index.html" || { status "Upload failed"; return 1; }
  echo "builds/${APP_ENV}/${NAME}" > "$MARK"
  rm -rf /work "/out/${NAME}"
  status "Done"
}

START=$(date +%s)
build
status "Finished in $(( ($(date +%s) - START) / 60 )) min"
wait
