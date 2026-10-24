"""Verifica que los datos cuenten las historias y que un estimador bayesiano con decaimiento las detecte."""
import sqlite3, sys
from datetime import date, datetime, timedelta
import pandas as pd, numpy as np
from pathlib import Path
db = sys.argv[1] if len(sys.argv) > 1 else str(Path(__file__).resolve().parent.parent / "data" / "cosco.db")
con = sqlite3.connect(db)
df = pd.read_sql("""SELECT s.proveedor_id, p.nombre, s.a_tiempo, s.entrega_real, so.corredor_id, so.nivel_servicio
                    FROM servicio s JOIN proveedor p USING(proveedor_id) JOIN solicitud so USING(solicitud_id)
                    WHERE s.estado='ENTREGADO'""", con, parse_dates=["entrega_real"])
df["mes"] = df.entrega_real.dt.to_period("M")
print("== % de entregas a tiempo por proveedor y mes ==")
t = df.pivot_table(index="nombre", columns="mes", values="a_tiempo", aggfunc="mean").mul(100).round(0)
print(t.to_string(na_rep="  ."))
print("\n== Servicios por proveedor (cuota) ==")
print((df.groupby("nombre").size().sort_values(ascending=False)).to_string())
sh = df.groupby(["mes", "nombre"]).size().unstack(fill_value=0); sh = sh.div(sh.sum(axis=1), axis=0)
print("\nCuota mensual de Mulas del Valle (%):", (sh["Mulas del Valle"] * 100).round(0).astype(int).tolist())

# deteccion: P(tarde) bayesiana con decaimiento, usando solo lo que se sabia cada semana
A0, B0 = 17, 3
def p_tarde(sub, asof, half):
    sub = sub[sub.entrega_real <= asof]
    if sub.empty: return np.nan
    age = (asof - sub.entrega_real).dt.total_seconds() / 86400
    w = 0.5 ** (age / half) if half else np.ones(len(sub))
    late = ((1 - sub.a_tiempo) * w).sum(); n = w.sum()
    return (late + B0) / (n + A0 + B0)
def cruce(pid, ini, fin, umbral, half):
    sub = df[df.proveedor_id == pid]; d = ini
    while d <= fin:
        if p_tarde(sub, pd.Timestamp(d), half) > umbral: return d
        d += timedelta(days=1)
    return None
print("\n== Andina Cargo (P01): colapsa el 2026-08-01 (P(tarde) real 6% -> 35% en 20 dias). Primer dia con P(tarde)>15% ==")
for nombre, half in [("sin decaimiento", None), ("vida media 90 d", 90), ("vida media 45 d", 45), ("vida media 30 d", 30)]:
    c = cruce("P01", date(2026, 7, 1), date(2026, 10, 15), 0.15, half)
    print(f"  {nombre:18s}: {c}  (+{(c - date(2026,8,1)).days if c else '-'} dias)")
print("\n== Altiplano (P12): paro 10-24 mar. Pico de P(tarde) con cada configuracion, y cuando vuelve <20% ==")
sub = df[df.proveedor_id == "P12"]
for nombre, half in [("vida media 90 d", 90), ("vida media 30 d", 30)]:
    ser = {d: p_tarde(sub, pd.Timestamp(d), half) for d in pd.date_range("2026-03-01", "2026-06-30")}
    pico = max(ser, key=lambda k: ser[k]); vuelve = next((d for d in ser if d > pico and ser[d] < 0.20), None)
    print(f"  {nombre}: pico {ser[pico]:.0%} el {pico.date()}; vuelve <20% el {vuelta.date() if (vuelta:=vuelve) else '-'}")
print("\n== TransPacifico (P02): mejora abr-jun. P(tarde) bayesiana (vida media 45 d) al 1 de cada mes ==")
sub = df[df.proveedor_id == "P02"]
print("  ", {str(m): round(p_tarde(sub, pd.Timestamp(m), 45), 3) for m in ["2026-02-01","2026-04-01","2026-06-01","2026-08-01","2026-10-01"]})
print("\n== Caribe Express (P03) a tiempo por corredor (debil en Pacifico C1-C3) ==")
print((df[df.proveedor_id == "P03"].groupby("corredor_id").a_tiempo.mean() * 100).round(0).to_string())
