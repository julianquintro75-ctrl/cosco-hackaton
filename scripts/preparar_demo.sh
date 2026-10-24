#!/usr/bin/env bash
# Paso 14 · Prepara la demostracion: reinicia la base, carga los datos, recalcula estadisticas y la repeticion del tiempo,
# y arranca la API (puerto 8000) y la interfaz (puerto 8501). Ctrl+C detiene ambas.
# Uso: bash scripts/preparar_demo.sh [--sin-replay]
set -e
cd "$(dirname "$0")/.."
if [ -f .venv/bin/activate ]; then source .venv/bin/activate; fi
PY=$(command -v python || command -v python3)

echo "== 1/5 Datos sinteticos (semilla 7): data/cosco.db, cosco_sucio.db y verdad_oculta.csv"
$PY seed/generate.py --sucio
echo "== 2/5 Validador de calidad (debe decir 0 criticas)"
$PY seed/validar_datos.py | tail -1
echo "== 3/5 Estadisticas bayesianas a la fecha de la demo"
$PY -m engine.estadisticas --as-of 2026-09-30 | sed -n 1p
if [ "$1" != "--sin-replay" ]; then
  echo "== 4/5 Repeticion del tiempo (data/replay.csv para el tablero de Tendencias)"
  $PY scripts/replay.py | tail -5
else
  echo "== 4/5 Repeticion del tiempo omitida (--sin-replay)"
fi
echo "== 5/5 Arrancando API y UI"
$PY -m uvicorn app.api:app --port 8000 > /tmp/cosco_api.log 2>&1 &
API=$!
trap 'kill $API 2>/dev/null' EXIT
sleep 2
echo "   API:        http://127.0.0.1:8000/docs   (salud: http://127.0.0.1:8000/salud)"
echo "   Interfaz:   http://localhost:8501        (guion: docs/guion_demo.md)"
$PY -m streamlit run app/ui.py --server.port 8501
