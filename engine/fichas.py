"""Ficha automatica por proveedor (seccion 6 del PDF): estadisticas por corredor, Dureza, fortalezas, debilidades y riesgos.
Todo con as_of: solo lo que se sabia en esa fecha."""
from __future__ import annotations
from datetime import timedelta
import numpy as np
import pandas as pd

from engine.datos import Base, base_compartida, cargar_config
from engine.estadisticas import Estadisticas

LLUVIA = {4, 5, 10, 11}
PACIFICO = {"C1", "C2", "C3"}


def _punt(df: pd.DataFrame, as_of, hl) -> tuple[float, float]:
    """Puntualidad ponderada por antiguedad y n ponderado."""
    if df.empty:
        return float("nan"), 0.0
    w = 0.5 ** (((pd.Timestamp(as_of) - df.entrega_real).dt.total_seconds() / 86400).clip(lower=0) / hl)
    return float((w * df.a_tiempo).sum() / w.sum()), float(w.sum())


def ficha(pid: str, as_of, base: Base | None = None, est: Estadisticas | None = None, cfg: dict | None = None) -> dict:
    base = base or base_compartida()
    cfg = cfg or cargar_config()
    est = est or Estadisticas(base, cfg)
    as_of = pd.Timestamp(as_of)
    hl = cfg["vida_media_dias"]
    if pid not in base.nombres:
        raise KeyError(pid)
    e = base.entregados_hasta(as_of)
    ep = e[e.proveedor_id == pid]
    punt_prov, _ = _punt(ep, as_of, hl)
    tabla = est.tabla(as_of)
    filas = tabla[tabla.proveedor_id == pid].copy()
    filas["puntualidad"] = 1 - filas.p_tarde
    fort, deb, riesgos = [], [], []
    for r in filas.itertuples():
        sub = ep[(ep.corredor_id == r.corredor_id) & (ep.tipo_carga == r.tipo_carga)]
        if len(sub) < 15:
            continue
        p_c, _ = _punt(sub, as_of, hl)
        otros = e[(e.corredor_id == r.corredor_id) & (e.tipo_carga == r.tipo_carga) & (e.proveedor_id != pid)]
        p_m, _ = _punt(otros, as_of, hl)
        etiqueta = f"{r.corredor_id} · {r.tipo_carga}"
        if p_c - punt_prov >= 0.05 and (np.isnan(p_m) or p_c - p_m >= 0.03):
            fort.append(f"{etiqueta}: puntualidad {p_c:.0%}, {100*(p_c-punt_prov):.0f} pts sobre su promedio y {100*(p_c-p_m):.0f} pts sobre el mercado ({len(sub)} servicios)" if not np.isnan(p_m)
                        else f"{etiqueta}: puntualidad {p_c:.0%} ({len(sub)} servicios)")
        elif punt_prov - p_c >= 0.05 or (not np.isnan(p_m) and p_m - p_c >= 0.05):
            deb.append(f"{etiqueta}: puntualidad {p_c:.0%}, {100*(punt_prov-p_c):.0f} pts bajo su promedio" + (f" y {100*(p_m-p_c):.0f} pts bajo el mercado" if not np.isnan(p_m) else "") + f" ({len(sub)} servicios)")
    t = est.tendencia(as_of, pid)
    if t > 0:
        riesgos.append(f"Puntualidad en caída: retrasos de los últimos {cfg.get('tendencia_ventana_dias', 30)} días {100*t:.0f} pts por encima de su año anterior (significativo)")
    # temporada de lluvias en el Pacifico (ultimo ano)
    pa = ep[ep.corredor_id.isin(PACIFICO) & (ep.entrega_real > as_of - timedelta(days=365))]
    ll, sec = pa[pa.entrega_real.dt.month.isin(LLUVIA)], pa[~pa.entrega_real.dt.month.isin(LLUVIA)]
    if len(ll) >= 15 and len(sec) >= 15 and sec.a_tiempo.mean() - ll.a_tiempo.mean() >= 0.08:
        deb.append(f"Temporada de lluvias en el Pacífico: puntualidad {100*(sec.a_tiempo.mean()-ll.a_tiempo.mean()):.0f} pts menor ({len(ll)} servicios en lluvia)")
    # concentracion, rechazos, incidentes recientes, capacidad
    s = base.servicios_todos
    m = s[(s.fecha_cargue <= as_of) & (s.fecha_cargue > as_of - timedelta(days=cfg["concentracion_ventana_dias"]))]
    cuota = float((m.proveedor_id == pid).mean()) if len(m) else 0.0
    if cuota > cfg["concentracion_umbral"]:
        riesgos.append(f"Concentración: {cuota:.0%} del volumen de los últimos {cfg['concentracion_ventana_dias']} días")
    mp = m[m.proveedor_id == pid]
    if len(mp) >= 10 and mp.estado.isin(["CANCELADO", "RECHAZADO"]).mean() > 0.05:
        riesgos.append(f"Rechazos recientes: {mp.estado.isin(['CANCELADO','RECHAZADO']).mean():.0%} de las órdenes de 30 días")
    inc30 = int(ep[ep.entrega_real > as_of - timedelta(days=30)].incidente.sum())
    if inc30:
        riesgos.append(f"Incidentes recientes: {inc30} en los últimos 30 días")
    fl = base.flota[base.flota.proveedor_id == pid]
    cap = []
    for r in fl.itertuples():
        u, f = base.capacidad_en(pid, r.tipo_vehiculo_id, as_of)
        cap.append(dict(vehiculo=r.tipo_vehiculo_id, flota=int(r.cantidad), disponibles=u, reporte=str(f.date()) if f is not None else None))
        if u is not None and r.cantidad and u / r.cantidad <= 0.1:
            riesgos.append(f"Capacidad casi agotada en {r.tipo_vehiculo_id}: {u} de {r.cantidad} unidades")
    p = base.proveedores.set_index("proveedor_id").loc[pid]
    dur = filas[filas.tipo_carga == "general"].indice_dureza
    return dict(
        proveedor_id=pid, nombre=p.nombre, ciudad_base=p.ciudad_base, fecha_alta=p.fecha_alta, as_of=as_of.isoformat(),
        servicios_entregados=int(len(ep)), puntualidad_general=None if np.isnan(punt_prov) else round(punt_prov, 4),
        dureza_media=None if dur.empty else round(float(dur.mean()), 2), cuota_30d=round(cuota, 4),
        certificaciones=sorted(base.certificaciones(pid, as_of)), capacidad=cap,
        fortalezas=fort, debilidades=deb, riesgos=riesgos,
        estadisticas=[{k: (round(v, 4) if isinstance(v, float) else v) for k, v in r.items() if k not in ("ic90_p_tarde",)}
                      for r in filas.drop(columns=["ic90_p_tarde"]).to_dict("records")])
