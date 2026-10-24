"""Reentrenamiento nocturno de M1 (puntualidad) y M2 (tránsito).  Publica SOLO si el candidato mejora la línea base bayesiana.

Ventanas móviles respecto de `as_of` (hoy simulado = último servicio entregado, o --as-of):
  entrenamiento: todo hasta as_of-60 d · calibración: as_of-60..-30 d · validación: últimos 30 d (el candidato nunca se evalúa con lo que aprendió).
Regla de publicación (la misma del paso 10): M1 debe bajar el Brier ≥ 0,002 sin perder AUC; M2 debe bajar el pinball P50 y P90 ≥ 3 %.
Además la ventana de validación debe tener ≥ 300 servicios. Si no mejora: no se publica nada, se registra «mantener_bayes» y el motor sigue con la estadística bayesiana.
Si mejora: el candidato queda en engine/modelos/candidato/ y en modelo_version como «pendiente de aprobacion»; **no se activa solo**:
una persona lo aprueba (decisión del proyecto: pesos y modelos nuevos con aprobación humana).
Registro de cada corrida: data/reentrenamiento_log.jsonl.

Uso:  python scripts/reentrenar.py                       # una corrida
      python scripts/reentrenar.py --demonio --hora 02:00  # se queda corriendo y reentrena cada noche (Docker: perfil «ml»)
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

from engine import modelos  # noqa: E402
from engine.datos import Base, cargar_config  # noqa: E402
from engine.repositorio import crear_repositorio  # noqa: E402

LOG = Path(os.environ.get("COSCO_LOG_REENTRENAMIENTO", RAIZ / "data" / "reentrenamiento_log.jsonl"))
CANDIDATO = modelos.DIR_MODELOS / "candidato"
MIN_VALIDACION = 300


def corrida(as_of: str | None = None, dry_run: bool = False) -> dict:
    t0 = time.perf_counter()
    repo = crear_repositorio()
    base = Base(repo)
    fin = datetime.fromisoformat(as_of) if as_of else base.entregados.entrega_real.max().to_pydatetime()
    cortes = ((fin - timedelta(days=60)).date().isoformat(), (fin - timedelta(days=30)).date().isoformat(), fin.date().isoformat())
    df = modelos.construir_dataset(base, cargar_config())
    tmp = modelos.DIR_MODELOS / "_tmp_candidato"
    met = modelos.entrenar(df, guardar=True, cortes=cortes, dir_salida=tmp)
    suficiente = met["n_validacion"] >= MIN_VALIDACION     # con pocos casos una «mejora» es ruido
    publicar_m1, publicar_m2 = suficiente and met["decision_M1"] == "usar_ml", suficiente and met["decision_M2"] == "usar_ml"
    publicado = []
    if (publicar_m1 or publicar_m2) and not dry_run:
        if CANDIDATO.exists():
            shutil.rmtree(CANDIDATO)
        shutil.move(str(tmp), str(CANDIDATO))
        ahora = datetime.now().strftime("%Y-%m-%dT%H:%M")
        for nom, desc, clave, ok in (("M1", "M1 puntualidad (CatBoost + isotonica)", "M1", publicar_m1), ("M2", "M2 transito (LightGBM quantile 0.5/0.9)", "M2", publicar_m2)):
            if ok:
                v = f"{nom}-{fin.date().isoformat()}"
                repo.registrar_modelo(v, desc, json.dumps({clave: met[clave], "cortes": cortes}), ahora, "pendiente de aprobacion", reemplazar=True)
                publicado.append(v)
    else:
        shutil.rmtree(tmp, ignore_errors=True)
    reg = {"fecha": datetime.now().isoformat(timespec="seconds"), "as_of": fin.isoformat(timespec="minutes"), "cortes": cortes,
           "n": {k: met[k] for k in ("n_train", "n_calibracion", "n_validacion")},
           "M1": {"decision": met["decision_M1"], "bayes": met["M1"]["bayes"], "candidato": met["M1"]["catboost_isotonica"]},
           "M2": {"decision": met["decision_M2"], "bayes": met["M2"]["bayes"], "candidato": met["M2"]["lightgbm"]},
           "publicado": publicado, "segundos": round(time.perf_counter() - t0, 1), "dry_run": dry_run}
    if not dry_run:
        LOG.parent.mkdir(parents=True, exist_ok=True)
        with LOG.open("a", encoding="utf8") as f:
            f.write(json.dumps(reg, ensure_ascii=False) + "\n")
    return reg


def resumen(r: dict) -> str:
    m1, m2 = r["M1"], r["M2"]
    return (f"as_of {r['as_of']} · M1: {m1['decision']} (Brier bayes {m1['bayes']['brier']:.4f} vs candidato {m1['candidato']['brier']:.4f}) · "
            f"M2: {m2['decision']} (pinball P90 bayes {m2['bayes']['pinball_p90']:.1f} vs {m2['candidato']['pinball_p90']:.1f}) · "
            f"publicado: {', '.join(r['publicado']) or 'nada (se mantiene la estadística bayesiana)'} · {r['segundos']} s")


def segundos_hasta(hhmm: str) -> float:
    h, m = map(int, hhmm.split(":"))
    ahora = datetime.now(); prox = ahora.replace(hour=h, minute=m, second=0, microsecond=0)
    if prox <= ahora:
        prox += timedelta(days=1)
    return (prox - ahora).total_seconds()


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--as-of"); ap.add_argument("--dry-run", action="store_true", help="evalúa sin publicar ni registrar")
    ap.add_argument("--demonio", action="store_true"); ap.add_argument("--hora", default="02:00")
    a = ap.parse_args()
    if not a.demonio:
        print(resumen(corrida(a.as_of, a.dry_run))); return
    print(f"Reentrenador activo: corre todos los días a las {a.hora} (hora del contenedor).", flush=True)
    while True:
        time.sleep(segundos_hasta(a.hora))
        try:
            print(resumen(corrida(None)), flush=True)
        except Exception as e:  # una noche fallida no debe tumbar el servicio
            print(f"Reentrenamiento falló: {e!r}", flush=True)


if __name__ == "__main__":
    main()
