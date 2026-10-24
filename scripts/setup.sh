#!/usr/bin/env bash
set -e
cd "$(dirname "$0")/.."
PY=$(command -v python3 || command -v python)
$PY -m venv .venv
source .venv/bin/activate
python -m pip install -q -U pip
pip install -r requirements.txt
python seed/generate.py --sucio
python seed/validar_datos.py || true
python scripts/verificar_entorno.py
echo "Siguiente: source .venv/bin/activate && claude"
