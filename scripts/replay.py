"""Paso 9 · Repeticion del tiempo (aprendizaje en vivo).
Recorre los dias desde --desde (por defecto 2026-06-01). Cada dia:
  1. Recomienda con MotorA las solicitudes de ese dia (as_of = momento de la solicitud: no ve el futuro).
  2. Aplica los cierres de los servicios entregados ese dia: al avanzar as_of entran a la estadistica bayesiana
     (equivale a llamar actualizar_con_servicio con cada cierre; el motor recalcula desde la base con as_of).
  3. Guarda por proveedor: P(tarde) estimada, posicion media en el ranking, % Top-1 y Top-3 (todos y Estandar), cuota.
Al final mide el dia en que Andina Cargo cae del Top-3 en Estandar frente al 2026-08-01 real.
La verdad oculta se usa SOLO para evaluar (columna p_tarde_real y retraso de deteccion), nunca para recomendar.
Uso: python scripts/replay.py [--desde 2026-06-01] [--hasta 2026-10-15] [--velocidad 0.0] [--vida-media 45]"""
import argparse, sqlite3, sys, time
from collections import defaultdict
from datetime import date, timedelta
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))
import numpy as np
import pandas as pd
from contratos.contracts import SolicitudIn
from engine.datos import Base
from engine.motor_a import MotorA

CAMPOS = ("solicitud_id", "cliente_id", "corredor_id", "tipo_vehiculo_req", "tipo_carga", "peso_ton", "fecha_cargue", "plazo_entrega", "tarifa_cliente", "nivel_servicio")


def solicitudes(db, desde, hasta):
    con = sqlite3.connect(db); con.row_factory = sqlite3.Row
    return [dict(r) for r in con.execute("SELECT * FROM solicitud WHERE substr(fecha_solicitud,1,10) BETWEEN ? AND ? ORDER BY fecha_solicitud, solicitud_id",
                                         (desde, hasta))]


def a_sol(r) -> SolicitudIn:
    return SolicitudIn(**{k: r[k] for k in CAMPOS}, mercancia_peligrosa=bool(r["mercancia_peligrosa"]), as_of=r["fecha_solicitud"])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--desde", default="2026-06-01"); ap.add_argument("--hasta", default="2026-10-15")
    ap.add_argument("--velocidad", type=float, default=0.0, help="segundos de pausa por dia simulado (0 = lo mas rapido posible)")
    ap.add_argument("--vida-media", type=float); ap.add_argument("--db", default=str(RAIZ / "data" / "cosco.db"))
    ap.add_argument("--salida", default=str(RAIZ / "data" / "replay.csv")); ap.add_argument("--silencioso", action="store_true")
    a = ap.parse_args()
    base = Base(a.db)
    extra = {"vida_media_dias": a.vida_media} if a.vida_media else {}
    motor = MotorA(base, **extra)
    est = motor.est
    reqs = solicitudes(a.db, a.desde, a.hasta)
    por_dia = defaultdict(list)
    for r in reqs:
        por_dia[r["fecha_solicitud"][:10]].append(r)
    pids = list(base.proveedores.proveedor_id)
    ent = base.entregados
    filas = []
    d, fin = date.fromisoformat(a.desde), date.fromisoformat(a.hasta)
    escrito = False
    while d <= fin:
        ds = d.isoformat()
        pos = defaultdict(list); top1 = defaultdict(int); top3 = defaultdict(int); fact = defaultdict(int)
        top3_e = defaultdict(int); fact_e = defaultdict(int); n_rec = 0
        for r in por_dia.get(ds, []):
            factibles, _, _ = motor.evaluar(a_sol(r)); n_rec += 1
            for i, f in enumerate(factibles):
                p = f["pid"]; pos[p].append(i + 1); fact[p] += 1
                top1[p] += i == 0; top3[p] += i < 3
                if r["nivel_servicio"] == "Estandar":
                    fact_e[p] += 1; top3_e[p] += i < 3
        fin_dia = pd.Timestamp(ds) + timedelta(days=1) - timedelta(minutes=1)
        cierres = int(((ent.entrega_real.dt.normalize() == pd.Timestamp(ds))).sum())
        cuotas = motor.cuotas(fin_dia)
        X = est._ctx(fin_dia)
        for p in pids:
            ii = est._antes(est._g1.get(p), X["k"])
            w = est._w(ii, X["as_d"], motor.cfg["vida_media_dias"], est._dias)
            pt = (float((w * est._late[ii]).sum()) + motor.cfg["prior_beta"]) / (float(w.sum()) + motor.cfg["prior_alfa"] + motor.cfg["prior_beta"])
            filas.append(dict(fecha=ds, proveedor_id=p, nombre=base.nombres[p], p_tarde_est=round(pt, 4), tendencia=round(est.tendencia(fin_dia, p), 4),
                              posicion_media=round(float(np.mean(pos[p])), 3) if pos[p] else None, n_factible=fact[p],
                              pct_top1=round(top1[p] / fact[p], 4) if fact[p] else None, pct_top3=round(top3[p] / fact[p], 4) if fact[p] else None,
                              n_factible_estandar=fact_e[p], top3_estandar=top3_e[p], cuota_30d=round(cuotas.get(p, 0.0), 4),
                              solicitudes_dia=n_rec, cierres_dia=cierres))
        if not a.silencioso:
            andina = next(f for f in filas[-len(pids):] if f["proveedor_id"] == "P01")
            print(f"[{ds}] {n_rec:3d} solicitudes · {cierres:3d} cierres · Andina P(tarde) {andina['p_tarde_est']:.1%} · Top-3 {andina['pct_top3'] if andina['pct_top3'] is not None else '-'}", flush=True)
        # escritura incremental para que el tablero lo muestre en vivo
        pd.DataFrame(filas[-len(pids):]).to_csv(a.salida, mode="a" if escrito else "w", header=not escrito, index=False); escrito = True
        if a.velocidad: time.sleep(a.velocidad)
        d += timedelta(days=1)
    df = pd.read_csv(a.salida)
    # p_tarde real (verdad oculta, SOLO evaluacion): promedio semanal del proveedor
    vo = pd.read_csv(RAIZ / "data" / "verdad_oculta.csv")
    vo = vo.groupby(["semana", "proveedor_id"]).apply(lambda g: np.average(g.p_tarde_real, weights=g.n_servicios), include_groups=False).rename("p_tarde_real").reset_index()
    df["semana"] = (pd.to_datetime(df.fecha) - pd.to_timedelta(pd.to_datetime(df.fecha).dt.day_of_week, unit="D")).dt.strftime("%Y-%m-%d")
    df = df.drop(columns=[c for c in ("p_tarde_real",) if c in df]).merge(vo, on=["semana", "proveedor_id"], how="left").drop(columns="semana")
    df.to_csv(a.salida, index=False)
    print(resumen(df))


def resumen(df: pd.DataFrame) -> str:
    """Deteccion de la caida de Andina en Estandar: primer dia desde el cual el % de Top-3 (ventana movil de 7 dias) queda por debajo del 50 %."""
    a = df[df.proveedor_id == "P01"].sort_values("fecha").set_index("fecha")
    r = (a.top3_estandar.rolling(7, min_periods=1).sum() / a.n_factible_estandar.rolling(7, min_periods=1).sum())
    real = pd.Timestamp("2026-08-01")
    caida = None
    for f in r.index:
        if pd.Timestamp(f) >= real - timedelta(days=30) and (r.loc[f:] < 0.5).all():
            caida = f; break
    alerta = next((f for f, v in a.tendencia.items() if v > 0 and pd.Timestamp(f) >= real - timedelta(days=30)), None)
    cruce = next((f for f, v in a.p_tarde_est.items() if v > 0.15 and pd.Timestamp(f) >= real - timedelta(days=30)), None)
    antes = r[(r.index >= "2026-07-01") & (r.index < "2026-08-01")].mean()
    despues = r[(r.index >= "2026-09-15") & (r.index <= "2026-09-30")].mean()
    dias = lambda f: f"{(pd.Timestamp(f) - real).days} días" if f else "no detectado"
    return "\n".join([
        "== Andina Cargo: deterioro real desde 2026-08-01 (verdad oculta) ==",
        f"  % Top-3 en Estandar (ventana 7 d): julio {antes:.0%} -> 15-30 sep {despues:.0%}",
        f"  Cae del Top-3 en Estandar (queda < 50 % para siempre): {caida or '-'}  -> retraso de detección {dias(caida)}",
        f"  Alerta de tendencia (binomial 30 d) desde: {alerta or '-'}  -> {dias(alerta)}",
        f"  P(tarde) estimada del proveedor supera 15 %: {cruce or '-'}  -> {dias(cruce)}"])


if __name__ == "__main__":
    main()
