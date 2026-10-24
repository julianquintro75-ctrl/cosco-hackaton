"""Genera un reporte HTML de los datos (para verlos y para mostrarlos). Uso: python seed/reporte_datos.py [base.db] -> reportes/reporte_datos.html"""
import sqlite3, sys
from pathlib import Path
import pandas as pd, plotly.express as px
db = sys.argv[1] if len(sys.argv) > 1 else str(Path(__file__).parent.parent / "data" / "cosco.db")
out = Path(__file__).parent.parent / "reportes"; out.mkdir(exist_ok=True)
con = sqlite3.connect(db)
df = pd.read_sql("""SELECT s.proveedor_id, p.nombre, s.a_tiempo, s.entrega_real, s.precio_pactado, s.costo_final, s.dias_detencion,
 so.corredor_id, so.nivel_servicio, so.tipo_carga, so.fase FROM servicio s JOIN proveedor p USING(proveedor_id) JOIN solicitud so USING(solicitud_id)
 WHERE s.estado='ENTREGADO'""", con, parse_dates=["entrega_real"])
df["semana"] = df.entrega_real.dt.to_period("W").dt.start_time
df["mes"] = df.entrega_real.dt.to_period("M").dt.start_time
pal = px.colors.qualitative.Safe
figs = []
w = df.groupby(["mes", "nombre"]).a_tiempo.mean().mul(100).reset_index()
figs.append(("Puntualidad mensual por proveedor (% de entregas a tiempo)", px.line(w, x="mes", y="a_tiempo", color="nombre", markers=True, color_discrete_sequence=pal, labels={"a_tiempo": "% a tiempo", "mes": "", "nombre": ""})))
v = df.groupby(["mes", "nombre"]).size().reset_index(name="n")
v["cuota"] = v.n / v.groupby("mes").n.transform("sum") * 100
figs.append(("Cuota del volumen por proveedor (%) — concentración", px.area(v, x="mes", y="cuota", color="nombre", color_discrete_sequence=pal, labels={"cuota": "% del volumen", "mes": "", "nombre": ""})))
c = df.groupby(["nombre", "corredor_id"]).a_tiempo.mean().mul(100).round(0).unstack()
figs.append(("Puntualidad por proveedor y corredor (%) — fortalezas y debilidades", px.imshow(c, text_auto=True, color_continuous_scale="RdYlGn", zmin=40, zmax=100, aspect="auto", labels=dict(color="% a tiempo"))))
pr = df.groupby("nombre").agg(precio=("precio_pactado", "mean"), puntual=("a_tiempo", "mean"), n=("a_tiempo", "size")).reset_index(); pr["puntual"] *= 100
figs.append(("Precio medio vs. puntualidad (tamaño = servicios)", px.scatter(pr, x="precio", y="puntual", size="n", text="nombre", labels={"precio": "Precio medio (COP)", "puntual": "% a tiempo"})))
for t, f in figs: f.update_layout(template="plotly_white", height=460, margin=dict(l=40, r=20, t=30, b=40))
kpi = f"{len(df):,} servicios entregados · {df.nombre.nunique()} proveedores · puntualidad global {df.a_tiempo.mean()*100:.1f} % · costo medio {df.costo_final.mean()/1e6:.2f} M COP"
body = "".join(f"<h2>{t}</h2>" + f.to_html(full_html=False, include_plotlyjs="cdn" if i == 0 else False) for i, (t, f) in enumerate(figs))
(out / "reporte_datos.html").write_text(f"<!doctype html><meta charset='utf-8'><title>Reporte de datos</title><body style='font-family:system-ui;max-width:1100px;margin:24px auto;padding:0 16px;color:#141a26'><h1>Reporte de datos sintéticos</h1><p>{kpi}</p>{body}</body>", encoding="utf8")
print("Reporte:", out / "reporte_datos.html")
