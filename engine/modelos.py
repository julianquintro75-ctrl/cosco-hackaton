"""Paso 10 · Modelos M1 (puntualidad) y M2 (transito) frente a la linea base bayesiana.
- Variables SOLO con informacion previa a la solicitud (as_of = fecha_solicitud): sin fuga.
- Division TEMPORAL: entrena con solicitudes hasta 2026-05-31, calibra (isotonica) con junio, valida en julio-septiembre.
- M1: CatBoostClassifier + calibracion isotonica -> P(a tiempo). Metricas: AUC, Brier, curva de calibracion.
- M2: LightGBM objetivo quantile (alpha 0.5 y 0.9) -> transito en horas. Metrica: pinball loss.
- Linea base: estimacion bayesiana del motor A (Beta(17,3) con decaimiento) con el mismo as_of.
Si M1 no mejora la linea base se dice claramente y el motor se queda con el bayesiano.
Nunca usa verdad_oculta.csv.
Uso: python -m engine.modelos   (escribe reportes/paso10_modelos.md y registra modelo_version)"""
from __future__ import annotations
import json, pickle
from datetime import datetime
from pathlib import Path
import numpy as np
import pandas as pd

from engine.datos import RAIZ, Base, base_compartida, cargar_config
from engine.estadisticas import Estadisticas

DIR_MODELOS = Path(__file__).resolve().parent / "modelos"
CAT = ["corredor_id", "tipo_carga", "tipo_vehiculo_req", "nivel_servicio", "proveedor_id"]
NUM = ["distancia_km", "holgura_h", "dia_semana", "mes", "lluvia", "p_tarde_30", "p_tarde_90", "p_tarde_365", "n_30", "n_90", "n_365",
       "p_tarde_corredor", "exp_corredor", "exp_corredor_carga", "utilizacion", "plazo_h", "transito_med_corredor"]
CORTE_TRAIN, CORTE_CAL, FIN_VAL = "2026-05-31", "2026-06-30", "2026-09-30"


def construir_dataset(base: Base | None = None, cfg: dict | None = None) -> pd.DataFrame:
    """Una fila por servicio ENTREGADO, con variables calculadas a la fecha de la solicitud y la linea base bayesiana."""
    base = base or base_compartida(); cfg = cfg or cargar_config()
    est = Estadisticas(base, cfg); est._indices()
    s = base.entregados.copy()
    flota = base.flota.set_index(["proveedor_id", "tipo_vehiculo_id"]).cantidad.to_dict()
    filas = []
    for r in s.itertuples():
        asof = r.fecha_solicitud
        X = est._ctx(asof)
        k = X["k"]; as_d = X["as_d"]
        ip = est._antes(est._g1.get(r.proveedor_id), k)
        edad = as_d - est._dias[ip]
        f = {}
        for w in (30, 90, 365):
            m = ip[edad <= w]
            f[f"n_{w}"] = len(m)
            f[f"p_tarde_{w}"] = (est._late[m].sum() + 3) / (len(m) + 20)     # suavizado con la misma previa
        ic = est._antes(est._g2.get((r.proveedor_id, r.corredor_id)), k)
        icc = est._antes(est._g3.get((r.proveedor_id, r.corredor_id, r.tipo_carga)), k)
        f["p_tarde_corredor"] = (est._late[ic].sum() + 3) / (len(ic) + 20)
        f["exp_corredor"], f["exp_corredor_carga"] = len(ic), len(icc)
        u, _ = base.capacidad_en(r.proveedor_id, r.tipo_vehiculo_req, asof)
        fl = flota.get((r.proveedor_id, r.tipo_vehiculo_req), 0)
        f["utilizacion"] = 1 - u / fl if (u is not None and fl) else np.nan
        plazo_h = (r.plazo_entrega - r.fecha_cargue).total_seconds() / 3600
        med = X["med"].get(r.corredor_id, np.nan)
        b = est.combo(asof, r.proveedor_id, r.corredor_id, r.tipo_carga)
        filas.append(dict(servicio_id=r.servicio_id, fecha_solicitud=asof, proveedor_id=r.proveedor_id, corredor_id=r.corredor_id,
                          tipo_carga=r.tipo_carga, tipo_vehiculo_req=r.tipo_vehiculo_req, nivel_servicio=r.nivel_servicio,
                          distancia_km=float(base.corredores.loc[r.corredor_id].distancia_km), plazo_h=plazo_h, transito_med_corredor=med,
                          holgura_h=plazo_h - med if not np.isnan(med) else np.nan, dia_semana=r.fecha_cargue.day_of_week, mes=r.fecha_cargue.month,
                          lluvia=int(r.fecha_cargue.month in (4, 5, 10, 11)), **f,
                          base_p_a_tiempo=1 - b["p_tarde"], base_p50=b["transito_p50_h"], base_p90=b["transito_p90_h"],
                          a_tiempo=int(r.a_tiempo), transito_h=float(r.transito_h)))
    return pd.DataFrame(filas)


def pinball(y, q, alpha):
    d = y - q
    return float(np.mean(np.maximum(alpha * d, (alpha - 1) * d)))


def calibracion(y, p, bins=10):
    df = pd.DataFrame({"y": y, "p": p})
    df["bin"] = pd.qcut(df.p, bins, duplicates="drop")
    return df.groupby("bin", observed=True).agg(p_media=("p", "mean"), real=("y", "mean"), n=("y", "size")).reset_index(drop=True)


def entrenar(df: pd.DataFrame, guardar=True, cortes: tuple[str, str, str] | None = None, dir_salida: Path | None = None) -> dict:
    """`cortes` = (fin_entrenamiento, fin_calibracion, fin_validacion); por omision los del reto. `dir_salida`: donde guardar los artefactos."""
    from catboost import CatBoostClassifier, Pool
    from lightgbm import LGBMRegressor
    from sklearn.isotonic import IsotonicRegression
    from sklearn.metrics import brier_score_loss, roc_auc_score

    c_tr, c_ca, c_va = cortes or (CORTE_TRAIN, CORTE_CAL, FIN_VAL)
    df = df.sort_values("fecha_solicitud").reset_index(drop=True)
    tr = df[df.fecha_solicitud <= c_tr]
    ca = df[(df.fecha_solicitud > c_tr) & (df.fecha_solicitud <= c_ca)]
    va = df[(df.fecha_solicitud > c_ca) & (df.fecha_solicitud <= c_va)]
    cols = CAT + NUM
    # ---- M1 ----
    m1 = CatBoostClassifier(iterations=600, depth=5, learning_rate=0.03, loss_function="Logloss", random_seed=7, verbose=0, cat_features=CAT)
    m1.fit(tr[cols], tr.a_tiempo, eval_set=(ca[cols], ca.a_tiempo), use_best_model=True)
    iso = IsotonicRegression(out_of_bounds="clip", y_min=0.01, y_max=0.99).fit(m1.predict_proba(ca[cols])[:, 1], ca.a_tiempo)
    p_ml = iso.predict(m1.predict_proba(va[cols])[:, 1])
    p_raw = m1.predict_proba(va[cols])[:, 1]
    y = va.a_tiempo.values
    met = {"n_train": len(tr), "n_calibracion": len(ca), "n_validacion": len(va),
           "M1": {"bayes": {"auc": roc_auc_score(y, va.base_p_a_tiempo), "brier": brier_score_loss(y, va.base_p_a_tiempo)},
                  "catboost_sin_calibrar": {"auc": roc_auc_score(y, p_raw), "brier": brier_score_loss(y, p_raw)},
                  "catboost_isotonica": {"auc": roc_auc_score(y, p_ml), "brier": brier_score_loss(y, p_ml)}}}
    met["calibracion"] = {"bayes": calibracion(y, va.base_p_a_tiempo.values).round(3).to_dict("records"),
                          "catboost_isotonica": calibracion(y, p_ml).round(3).to_dict("records")}
    # ---- M2 ----
    X_tr = tr[cols].copy(); X_va = va[cols].copy()
    for c in CAT:
        cats = pd.Categorical(df[c]).categories
        X_tr[c] = pd.Categorical(X_tr[c], categories=cats); X_va[c] = pd.Categorical(X_va[c], categories=cats)
    trc = pd.concat([X_tr, ca[cols].assign(**{c: pd.Categorical(ca[c], categories=pd.Categorical(df[c]).categories) for c in CAT})])
    ytr = pd.concat([tr.transito_h, ca.transito_h])
    m2 = {}
    for a in (0.5, 0.9):
        m = LGBMRegressor(objective="quantile", alpha=a, n_estimators=400, learning_rate=0.03, num_leaves=15, min_child_samples=30, random_state=7, verbose=-1)
        m.fit(trc, ytr); m2[a] = m
    yt = va.transito_h.values
    q50, q90 = m2[0.5].predict(X_va), m2[0.9].predict(X_va)
    met["M2"] = {"bayes": {"pinball_p50": pinball(yt, va.base_p50.values, .5), "pinball_p90": pinball(yt, va.base_p90.values, .9),
                           "cobertura_p90": float(np.mean(yt <= va.base_p90.values))},
                 "lightgbm": {"pinball_p50": pinball(yt, q50, .5), "pinball_p90": pinball(yt, q90, .9), "cobertura_p90": float(np.mean(yt <= q90))}}
    # ---- decision ----
    b, c = met["M1"]["bayes"], met["M1"]["catboost_isotonica"]
    met["decision_M1"] = "usar_ml" if (c["brier"] < b["brier"] - 0.002 and c["auc"] >= b["auc"]) else "mantener_bayes"
    bb, ll = met["M2"]["bayes"], met["M2"]["lightgbm"]
    met["decision_M2"] = "usar_ml" if (ll["pinball_p50"] < bb["pinball_p50"] * 0.97 and ll["pinball_p90"] < bb["pinball_p90"] * 0.97) else "mantener_bayes"
    # ---- SHAP (contribuciones de CatBoost) ----
    shap = m1.get_feature_importance(Pool(va[cols], cat_features=CAT), type="ShapValues")[:, :-1]
    met["shap_importancia_media"] = dict(sorted(zip(cols, np.abs(shap).mean(0).round(4).tolist()), key=lambda x: -x[1]))
    met["imp_m2_p90"] = dict(sorted(zip(cols, m2[0.9].feature_importances_.tolist()), key=lambda x: -x[1])[:8])
    if guardar:
        d = Path(dir_salida or DIR_MODELOS); d.mkdir(parents=True, exist_ok=True)
        m1.save_model(str(d / "m1_catboost.cbm"))
        pickle.dump(dict(iso=iso, m2=m2, cols=cols, cat=CAT), open(d / "m1_iso_m2.pkl", "wb"))
    return met


def factores_shap(m1, fila: pd.DataFrame, n=3) -> list[str]:
    """Factores clave de una prediccion M1 (contribucion SHAP en log-odds)."""
    from catboost import Pool
    cols = CAT + NUM
    sv = m1.get_feature_importance(Pool(fila[cols], cat_features=CAT), type="ShapValues")[0, :-1]
    o = np.argsort(-np.abs(sv))[:n]
    return [f"{cols[i]} = {fila[cols[i]].iloc[0]} {'sube' if sv[i] > 0 else 'baja'} la P(a tiempo) ({sv[i]:+.2f} log-odds)" for i in o]


def registrar(met: dict, db=None):
    from engine.repositorio import crear_repositorio
    repo = crear_repositorio(db)
    hoy = datetime.now().strftime("%Y-%m-%dT%H:%M")
    repo.registrar_modelo("M1-catboost-iso-v1", "M1 puntualidad (CatBoost + isotonica)", json.dumps({"M1": met["M1"], "decision": met["decision_M1"]}), hoy,
                          None if met["decision_M1"] != "usar_ml" else "pendiente de aprobacion", reemplazar=True)
    repo.registrar_modelo("M2-lgbm-quantile-v1", "M2 transito (LightGBM quantile 0.5/0.9)", json.dumps({"M2": met["M2"], "decision": met["decision_M2"]}), hoy,
                          None if met["decision_M2"] != "usar_ml" else "pendiente de aprobacion", reemplazar=True)


def reporte(met: dict) -> str:
    M1, M2 = met["M1"], met["M2"]
    L = ["# Paso 10 · Modelos M1 y M2 frente a la línea base bayesiana", "",
         f"Datos sintéticos. División temporal: entrenamiento hasta {CORTE_TRAIN} ({met['n_train']} servicios), calibración isotónica en junio "
         f"({met['n_calibracion']}), validación julio–septiembre ({met['n_validacion']}). Variables calculadas con as_of = fecha de la solicitud (sin fuga).", "",
         "## M1 · Probabilidad de entrega a tiempo", "", "| Modelo | AUC (↑) | Brier (↓) |", "|---|---|---|"]
    for k, nom in (("bayes", "Línea base bayesiana (motor A)"), ("catboost_sin_calibrar", "CatBoost sin calibrar"), ("catboost_isotonica", "CatBoost + isotónica")):
        L.append(f"| {nom} | {M1[k]['auc']:.4f} | {M1[k]['brier']:.4f} |")
    L += ["", "### Curva de calibración (validación, deciles de probabilidad predicha)", "", "| Bayes: predicho | Bayes: real | n | CatBoost: predicho | CatBoost: real | n |", "|---|---|---|---|---|---|"]
    for a, b in zip(met["calibracion"]["bayes"], met["calibracion"]["catboost_isotonica"]):
        L.append(f"| {a['p_media']:.3f} | {a['real']:.3f} | {a['n']} | {b['p_media']:.3f} | {b['real']:.3f} | {b['n']} |")
    L += ["", "## M2 · Tiempo de tránsito (horas)", "", "| Modelo | Pinball P50 (↓) | Pinball P90 (↓) | Cobertura real del P90 (ideal 0,90) |", "|---|---|---|---|"]
    for k, nom in (("bayes", "Línea base (percentiles ponderados del corredor)"), ("lightgbm", "LightGBM quantile")):
        L.append(f"| {nom} | {M2[k]['pinball_p50']:.3f} | {M2[k]['pinball_p90']:.3f} | {M2[k]['cobertura_p90']:.3f} |")
    L += ["", "## Variables más influyentes en M1 (|SHAP| medio)", ""] + [f"- {k}: {v}" for k, v in list(met["shap_importancia_media"].items())[:8]]
    d1 = "**M1 mejora la línea base**" if met["decision_M1"] == "usar_ml" else "**M1 NO mejora la línea base bayesiana de forma suficiente: el motor se queda con el bayesiano.**"
    d2 = "**M2 mejora la línea base**" if met["decision_M2"] == "usar_ml" else "**M2 NO mejora la línea base de forma suficiente: el motor se queda con los percentiles bayesianos.**"
    L += ["", "## Decisión", "", f"- {d1} Criterio: Brier al menos 0,002 menor y AUC no peor.",
          f"- {d2} Criterio: pinball P50 y P90 al menos 3 % menores.",
          "- Advertencia: la validación usa solo los servicios que la política humana histórica eligió (sesgo de selección); el backtest del paso 11 evalúa con la verdad oculta.",
          "- Los modelos quedan guardados en `engine/modelos/` y registrados en `modelo_version`; el reentrenamiento nocturno solo publicaría una versión nueva si mejora estas métricas."]
    return "\n".join(L)


if __name__ == "__main__":
    import time
    t = time.perf_counter()
    df = construir_dataset()
    print(f"dataset: {len(df)} filas en {time.perf_counter()-t:.0f} s")
    met = entrenar(df)
    registrar(met)
    txt = reporte(met)
    (RAIZ / "reportes" / "paso10_modelos.md").write_text(txt, encoding="utf8")
    print(txt)
