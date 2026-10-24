"""Paso 11 · Backtest y validacion (julio-septiembre 2026).
Para cada solicitud del periodo, MotorA con as_of = fecha de la solicitud. Se compara contra:
  analista (lo que se eligio de verdad), siempre el mas barato, aleatorio (semilla fija) y el oraculo.
Costo REAL esperado de asignar el proveedor p (solo evaluacion, usa la verdad oculta del simulador):
  precio + P(tarde)_real(p, corredor, fecha) x costo_retraso(nivel) + P(incidente)_real(p) x costo_incidente
La P(tarde) real sale de seed/config.py (las mismas funciones que generaron verdad_oculta.csv). El motor NUNCA la ve.
Sesgo de seleccion: el analista se evalua con la verdad oculta, no con los resultados observados de sus elecciones.
Barrido: vida media (15, 30, 45, 60, 90) x lambda (0, 0.5, 1, 2).
Uso: python scripts/backtest.py [--desde 2026-07-01 --hasta 2026-09-30] [--rapido]"""
import argparse, json, sqlite3, sys, time
from collections import defaultdict
from datetime import date, timedelta
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ)); sys.path.insert(0, str(RAIZ / "seed"))
import numpy as np
import pandas as pd
import config as VERDAD            # seed/config.py: historias reales del simulador (SOLO evaluacion)
from contratos.contracts import SolicitudIn
from engine.datos import Base, cargar_config
from engine.motor_a import MotorA

CAMPOS = ("solicitud_id", "cliente_id", "corredor_id", "tipo_vehiculo_req", "tipo_carga", "peso_ton", "fecha_cargue", "plazo_entrega", "tarifa_cliente", "nivel_servicio")
PROV = {p[0]: p for p in VERDAD.PROVEEDORES}
PACIF = {c[0]: c[7] for c in VERDAD.CORREDORES}


def p_tarde_real(pid, cor, d: date) -> float:
    """Copia exacta de la regla del generador (seed/generate.py) sin eventos en vivo."""
    p = PROV[pid][5](d, cor)
    if PACIF[cor] and d.month in VERDAD.LLUVIA_MESES:
        p += 0.05 * VERDAD.PESO_LLUVIA.get(pid, 1.0)
    return float(min(max(p, 0.01), 0.85))


def costo_real(pid, cor, d, precio, nivel, cfg):
    return precio + p_tarde_real(pid, cor, d) * cfg["costo_retraso"][nivel] + PROV[pid][6] * cfg["costo_incidente"]


def cargar(db, desde, hasta):
    con = sqlite3.connect(db); con.row_factory = sqlite3.Row
    reqs = [dict(r) for r in con.execute("SELECT * FROM solicitud WHERE substr(fecha_solicitud,1,10) BETWEEN ? AND ? ORDER BY fecha_solicitud, solicitud_id", (desde, hasta))]
    analista = dict(con.execute("SELECT solicitud_id, proveedor_elegido FROM decision WHERE recomendacion_id IS NULL ORDER BY fecha DESC").fetchall())
    return reqs, analista


def evaluar_vida_media(base, cfg, hl, reqs):
    """Corre el motor una vez por solicitud y guarda los componentes (lambda se aplica despues)."""
    m = MotorA(base, cfg, vida_media_dias=hl, lambda_incertidumbre=1.0)
    out = []
    for r in reqs:
        s = SolicitudIn(**{k: r[k] for k in CAMPOS}, mercancia_peligrosa=bool(r["mercancia_peligrosa"]), as_of=r["fecha_solicitud"])
        fact, _, ctx = m.evaluar(s)
        out.append(dict(r=r, cands=[dict(pid=f["pid"], precio=f["des"].precio, base=f["des"].precio + f["des"].retraso_esperado + f["des"].incidente_esperado + f["des"].concentracion,
                                         incert1=f["des"].incertidumbre, p_nc=f["p_nc"]) for f in fact]))
    return out


def politicas(evals, lam, analista, cfg, rng_seed=7):
    rng = np.random.default_rng(rng_seed)
    filas = []
    for e in evals:
        r, cands = e["r"], e["cands"]
        if not cands:
            continue
        d = date.fromisoformat(r["fecha_cargue"][:10]); nivel = r["nivel_servicio"]
        real = {c["pid"]: costo_real(c["pid"], r["corredor_id"], d, c["precio"], nivel, cfg) for c in cands}
        motor = min(cands, key=lambda c: (c["base"] + lam * c["incert1"], -(1 - c["p_nc"]), c["pid"]))["pid"]
        barato = min(cands, key=lambda c: (c["precio"], c["pid"]))["pid"]
        azar = cands[int(rng.integers(len(cands)))]["pid"]
        oraculo = min(real, key=lambda p: (real[p], p))
        an = analista.get(r["solicitud_id"])
        fila = dict(solicitud_id=r["solicitud_id"], fecha=r["fecha_solicitud"][:10], nivel=nivel, corredor=r["corredor_id"], n_cand=len(cands),
                    oraculo=oraculo, c_oraculo=real[oraculo])
        for nom, p in (("motor", motor), ("barato", barato), ("aleatorio", azar), ("analista", an)):
            if p is None:
                fila[nom] = None; continue
            precio = next((c["precio"] for c in cands if c["pid"] == p), None)
            if precio is None:     # el analista eligio a alguien que hoy no pasa los filtros (p. ej. capacidad): se usa su tarifa vigente
                precio = base_global.tarifa_vigente(p, r["corredor_id"], r["tipo_vehiculo_req"], r["fecha_cargue"])
                if precio is None: fila[nom] = None; continue
            c = costo_real(p, r["corredor_id"], d, precio, nivel, cfg)
            fila[nom] = p; fila[f"arr_{nom}"] = c - real[oraculo]; fila[f"punt_{nom}"] = 1 - p_tarde_real(p, r["corredor_id"], d)
        fila["acuerdo_analista"] = (an == motor) if an else None
        filas.append(fila)
    return pd.DataFrame(filas)


def resumen_politicas(df):
    res = {}
    for nom in ("motor", "barato", "aleatorio", "analista", "oraculo"):
        if nom == "oraculo":
            res[nom] = dict(arrepentimiento=0.0, pct_optimo=100.0, puntualidad_real=float(np.mean([1 - p_tarde_real(r.oraculo, r.corredor, date.fromisoformat(r.fecha)) for r in df.itertuples()])))
            continue
        sub = df[df[nom].notna()]
        res[nom] = dict(arrepentimiento=float(sub[f"arr_{nom}"].mean()), pct_optimo=float((sub[f"arr_{nom}"] < 1).mean() * 100),
                        puntualidad_real=float(sub[f"punt_{nom}"].mean()), n=int(len(sub)))
    return res


base_global = None


def main():
    global base_global
    ap = argparse.ArgumentParser()
    ap.add_argument("--desde", default="2026-07-01"); ap.add_argument("--hasta", default="2026-09-30")
    ap.add_argument("--db", default=str(RAIZ / "data" / "cosco.db")); ap.add_argument("--rapido", action="store_true", help="solo vida media 30/45 y lambda 0.5/1")
    a = ap.parse_args()
    cfg = cargar_config(); base = Base(a.db); base_global = base
    reqs, analista = cargar(a.db, a.desde, a.hasta)
    vidas = (30, 45) if a.rapido else (15, 30, 45, 60, 90)
    lams = (0.5, 1.0) if a.rapido else (0.0, 0.5, 1.0, 2.0)
    print(f"{len(reqs)} solicitudes {a.desde} → {a.hasta}; {len(vidas)} vidas medias × {len(lams)} λ", flush=True)
    tabla, detalle, andina = [], {}, {}
    for hl in vidas:
        t = time.perf_counter()
        ev = evaluar_vida_media(base, cfg, hl, reqs)
        andina[hl] = deteccion(base, cfg, hl, ev)
        for lam in lams:
            df = politicas(ev, lam, analista, cfg)
            res = resumen_politicas(df)
            m = res["motor"]
            tabla.append(dict(vida_media=hl, lam=lam, arrepentimiento=m["arrepentimiento"], pct_optimo=m["pct_optimo"], puntualidad_real=m["puntualidad_real"],
                              acuerdo_analista=float(df.acuerdo_analista.dropna().mean() * 100), **{f"andina_{k}": v for k, v in andina[hl].items()}))
            detalle[(hl, lam)] = (df, res)
        print(f"  vida media {hl:>3}: {time.perf_counter()-t:.0f} s", flush=True)
    T = pd.DataFrame(tabla)
    # elegir: menor arrepentimiento; desempate por deteccion mas temprana
    T["_det"] = T.andina_dias_top1.fillna(999)
    mejor = T.sort_values(["arrepentimiento", "_det"]).iloc[0]
    hl, lam = int(mejor.vida_media), float(mejor.lam)
    # prudencia: si el minimo es lambda = 0, se prefiere el lambda > 0 mas pequeno cuya diferencia NO sea significativa
    # (bootstrap pareado por solicitud, IC 95 %), porque estos datos no contienen proveedores nuevos malos que lambda castigaria
    nota_lam = ""
    if lam == 0:
        d0 = detalle[(hl, 0.0)][0].set_index("solicitud_id").arr_motor
        for l2 in sorted(x for x in lams if x > 0):
            dif = (detalle[(hl, l2)][0].set_index("solicitud_id").arr_motor - d0).dropna().values
            rng = np.random.default_rng(1)
            bs = [rng.choice(dif, len(dif)).mean() for _ in range(2000)]
            lo, hi = np.percentile(bs, [2.5, 97.5])
            nota_lam += f"\n- Diferencia de arrepentimiento λ={l2:g} − λ=0 (vida media {hl}): {cop(dif.mean())} por servicio, IC 95 % [{cop(lo)}, {cop(hi)}]."
            if lo <= 0:
                lam = l2
                nota_lam += f" **No es significativa → se elige λ = {l2:g}** para conservar la protección frente a proveedores con poca evidencia."
                break
            nota_lam += " Significativa."
    df, res = detalle[(hl, lam)]
    salida = RAIZ / "reportes" / "paso11_backtest.md"
    salida.write_text(reporte(T.drop(columns="_det"), hl, lam, df, res, cfg, len(reqs), a, nota_lam), encoding="utf8")
    df.to_csv(RAIZ / "data" / "backtest_detalle.csv", index=False)
    json.dump(dict(vida_media=hl, lam=lam, tabla=T.drop(columns="_det").to_dict("records"), politicas=res), open(RAIZ / "data" / "backtest_resumen.json", "w"), indent=1, default=float)
    print(salida.read_text(encoding="utf8"))


def deteccion(base, cfg, hl, ev):
    """Andina (P01): dias desde el 2026-08-01 hasta que (a) su P(tarde) estimada supera 15 % y (b) deja de ser Top-1 en Estandar
    (ventana movil de 7 dias con < 10 % de Top-1). Altiplano (P12): pico de P(tarde) por el paro de marzo (falsa alarma si > 20 %)."""
    from engine.estadisticas import Estadisticas
    est = Estadisticas(base, dict(cfg, vida_media_dias=hl))
    def p_prov(pid, d):
        X = est._ctx(d); ii = est._antes(est._g1.get(pid), X["k"]); w = est._w(ii, X["as_d"], hl, est._dias)
        return (float((w * est._late[ii]).sum()) + 3) / (float(w.sum()) + 20)
    d0 = date(2026, 8, 1)
    cruce = next(((d - d0).days for d in (d0 + timedelta(days=i) for i in range(0, 75)) if p_prov("P01", pd.Timestamp(d)) > 0.15), None)
    pico = max(p_prov("P12", pd.Timestamp(date(2026, 3, 1) + timedelta(days=i))) for i in range(0, 61))
    # Top-1 de Andina en Estandar (lambda = 1) por dia
    por_dia = defaultdict(lambda: [0, 0])
    for e in ev:
        r = e["r"]
        if r["nivel_servicio"] != "Estandar" or not any(c["pid"] == "P01" for c in e["cands"]):
            continue
        top = min(e["cands"], key=lambda c: (c["base"] + c["incert1"], -(1 - c["p_nc"]), c["pid"]))["pid"]
        k = r["fecha_solicitud"][:10]; por_dia[k][0] += top == "P01"; por_dia[k][1] += 1
    s = pd.DataFrame([(pd.Timestamp(k), v[0], v[1]) for k, v in por_dia.items()], columns=["f", "top", "n"]).set_index("f").sort_index()
    roll = s.top.rolling("7D").sum() / s.n.rolling("7D").sum()
    caida = None
    for f in roll.index:
        if f >= pd.Timestamp(d0) and (roll.loc[f:] < 0.10).all():
            caida = (f - pd.Timestamp(d0)).days; break
    return dict(dias_p15=cruce, dias_top1=caida, altiplano_pico=round(pico, 3))


def cop(x):
    return "$" + f"{int(round(x)):,}".replace(",", ".")


def reporte(T, hl, lam, df, res, cfg, n, a, nota_lam=""):
    L = ["# Paso 11 · Backtest y validación", "",
         f"Periodo {a.desde} → {a.hasta}: {n} solicitudes ({len(df)} con al menos un proveedor factible). Datos **sintéticos**. "
         "El motor usa as_of = fecha de la solicitud (no ve el futuro). El costo real se calcula con la verdad oculta del simulador; "
         "por eso la comparación con el analista no sufre el sesgo de selección de los resultados observados.", "",
         "Costo real = precio + P(tarde) real × costo de retraso del nivel + P(incidente) real × $8.000.000 (sin penalizaciones de decisión).", "",
         "## Barrido de configuración (motor A)", "",
         "| Vida media (d) | λ | Arrepentimiento medio | % óptimo | Puntualidad real | Acuerdo con analista | Andina: días hasta P(tarde)>15 % | Andina: días hasta dejar el Top-1 Estándar | Pico Altiplano (paro) |",
         "|---|---|---|---|---|---|---|---|---|"]
    for r in T.itertuples():
        marca = " **←**" if (r.vida_media == hl and r.lam == lam) else ""
        L.append(f"| {r.vida_media} | {r.lam:g} | {cop(r.arrepentimiento)}{marca} | {r.pct_optimo:.1f} % | {r.puntualidad_real:.1%} | {r.acuerdo_analista:.1f} % | "
                 f"{r.andina_dias_p15 if r.andina_dias_p15 is not None and r.andina_dias_p15 == r.andina_dias_p15 else 'no'} | "
                 f"{int(r.andina_dias_top1) if r.andina_dias_top1 == r.andina_dias_top1 and r.andina_dias_top1 is not None else 'no'} | {r.andina_altiplano_pico:.0%} |")
    L += ["", f"## Configuración elegida: vida media {hl} días, λ = {lam:g}", "",
          "| Política | Arrepentimiento medio | % elige el óptimo | Puntualidad real esperada |", "|---|---|---|---|"]
    nom = {"motor": "Motor A (nuestro)", "analista": "Analista (decisión histórica)", "barato": "Siempre el más barato", "aleatorio": "Aleatorio", "oraculo": "Oráculo (verdad oculta)"}
    for k in ("motor", "analista", "barato", "aleatorio", "oraculo"):
        r = res[k]; L.append(f"| {nom[k]} | {cop(r['arrepentimiento'])} | {r['pct_optimo']:.1f} % | {r['puntualidad_real']:.1%} |")
    L += ["", "### Por nivel de servicio (arrepentimiento medio en COP)", "", "| Nivel | n | Motor A | Analista | Más barato | Aleatorio | Acuerdo motor–analista |", "|---|---|---|---|---|---|---|"]
    for nv, g in df.groupby("nivel"):
        L.append(f"| {nv} | {len(g)} | {cop(g.arr_motor.mean())} | {cop(g.arr_analista.mean())} | {cop(g.arr_barato.mean())} | {cop(g.arr_aleatorio.mean())} | {g.acuerdo_analista.dropna().mean():.0%} |")
    ahorro = (res["analista"]["arrepentimiento"] - res["motor"]["arrepentimiento"])
    L += ["", "## Justificación", "",
          f"- Se elige la configuración con **menor arrepentimiento medio**; el desempate es la detección más temprana de Andina.{nota_lam}",
          f"- Frente a la decisión histórica del analista, el motor ahorraría en promedio **{cop(ahorro)} de costo real esperado por servicio** "
          f"({cop(ahorro * len(df))} en el trimestre simulado). Cifra sobre datos sintéticos: indica la dirección, no el valor real para COSCO.",
          "- Vidas medias cortas detectan antes a Andina pero se mueven más con eventos puntuales (pico de Altiplano en el paro de marzo); "
          "las largas son estables pero tardan semanas en reaccionar. La alerta de tendencia (binomial a 30 días) avisa independientemente de la vida media.",
          "- λ alto protege frente a proveedores con poca evidencia pero sacrifica ahorro cuando la evidencia es suficiente.",
          f"- La configuración elegida se copia a `engine/config_motor.json` (vida_media_dias = {hl}, lambda_incertidumbre = {lam:g}).",
          "- Limitación: los datos simulados siguen una estructura parecida a la que supone el modelo, así que la ventaja frente a las referencias probablemente está exagerada respecto a datos reales."]
    return "\n".join(L)


if __name__ == "__main__":
    main()
