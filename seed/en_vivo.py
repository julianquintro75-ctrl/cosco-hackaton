"""Simulacion en vivo: agrega un dia simulado cada N segundos a la base (para la demostracion).
Uso: python en_vivo.py --dias 14 --pausa 3 --evento P03:0.6:2026-10-25
 - Cada tick = 1 dia: llegan solicitudes nuevas (fase 'vivo'), se asignan con la politica historica y se cierran con resultados.
 - --evento fuerza la P(tarde) real de un proveedor desde una fecha (para mostrar que el sistema se da cuenta).
 - La verdad oculta se sigue anotando en data/verdad_oculta.csv (solo para evaluar)."""
import argparse, subprocess, sys, time, sqlite3
from datetime import date, timedelta
from pathlib import Path
ap = argparse.ArgumentParser(); ap.add_argument("--dias", type=int, default=7); ap.add_argument("--pausa", type=float, default=3)
ap.add_argument("--evento", action="append", default=[]); ap.add_argument("--out", default=str(Path(__file__).resolve().parent.parent / "data")); a = ap.parse_args()
db = Path(a.out) / "cosco.db"
ult = sqlite3.connect(db).execute("SELECT MAX(substr(fecha_solicitud,1,10)) FROM solicitud").fetchone()[0]
d = date.fromisoformat(ult) + timedelta(days=1)
for _ in range(a.dias):
    cmd = [sys.executable, str(Path(__file__).parent / "generate.py"), "--append", "--desde", d.isoformat(), "--hasta", d.isoformat(), "--out", a.out]
    for e in a.evento: cmd += ["--evento", e]
    r = subprocess.run(cmd, capture_output=True, text=True)
    print(f"[{d}] {r.stdout.strip() or r.stderr.strip()}", flush=True)
    d += timedelta(days=1); time.sleep(a.pausa)
