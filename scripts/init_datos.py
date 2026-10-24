"""Inicializa los datos sintéticos de forma idempotente (para Docker o primer arranque).

Replica los pasos 1–4 de scripts/preparar_demo.sh sin levantar servidores.
Si data/cosco.db ya existe no hace nada (usa --forzar para regenerar).
"""
import argparse
import os
import subprocess
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
DB = Path(os.environ.get("COSCO_REPO") or os.environ.get("COSCO_DB") or RAIZ / "data" / "cosco.db")


def correr(*args: str) -> None:
    print("→", " ".join(args), flush=True)
    subprocess.run([sys.executable, *args], cwd=RAIZ, check=True)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--forzar", action="store_true", help="regenerar aunque ya exista la base")
    a = ap.parse_args()
    if DB.exists() and not a.forzar:
        print(f"Datos ya presentes en {DB}; nada que hacer.")
        return
    DB.parent.mkdir(parents=True, exist_ok=True)
    correr("seed/generate.py", "--sucio", "--seed", os.environ.get("COSCO_SEED", "7"), "--out", str(DB.parent))
    correr("seed/validar_datos.py")
    correr("-m", "engine.estadisticas", "--as-of", "2026-09-30")
    correr("scripts/replay.py")
    print("Datos listos.")


if __name__ == "__main__":
    main()
