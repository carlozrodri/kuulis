#!/usr/bin/env bash
# Full ride on two Android devices/emulators at once (doc 20): passenger on the first, driver on the second.
# Usage: PASSENGER_EMAIL=… PASSENGER_PASSWORD=… DRIVER_EMAIL=… DRIVER_PASSWORD=… ./scripts/viaje-completo.sh
set -euo pipefail
cd "$(dirname "$0")/.."
mapfile -t DEVICES < <(adb devices | awk 'NR>1 && $2=="device" {print $1}')
if [ "${#DEVICES[@]}" -lt 2 ]; then
  echo "Hacen falta dos dispositivos o emuladores (adb devices)." >&2
  exit 1
fi
ENV=(-e PASSENGER_EMAIL="$PASSENGER_EMAIL" -e PASSENGER_PASSWORD="$PASSENGER_PASSWORD"
  -e DRIVER_EMAIL="$DRIVER_EMAIL" -e DRIVER_PASSWORD="$DRIVER_PASSWORD")
maestro --device "${DEVICES[1]}" test "${ENV[@]}" motorizado-viaje.yaml &
DRIVER=$!
sleep 25 # the driver is online before the passenger asks
maestro --device "${DEVICES[0]}" test "${ENV[@]}" pasajero-viaje.yaml
wait "$DRIVER"
