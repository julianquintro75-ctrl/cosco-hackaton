#!/bin/sh
# Genera config.json al arrancar el contenedor. COSCO_DEMO_USER / COSCO_DEMO_PASSWORD vacíos ocultan el cuadro de acceso de demostración.
set -eu
API="${COSCO_WEB_API_URL:-/api}"
if [ -n "${COSCO_DEMO_USER:-}" ] && [ -n "${COSCO_DEMO_PASSWORD:-}" ]; then
  DEMO="{\"usuario\":\"${COSCO_DEMO_USER}\",\"clave\":\"${COSCO_DEMO_PASSWORD}\"}"
else
  DEMO="null"
fi
printf '{"apiUrl":"%s","demo":%s}\n' "$API" "$DEMO" > /usr/share/nginx/html/config.json
