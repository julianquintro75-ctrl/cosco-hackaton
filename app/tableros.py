"""Paso 12 · Tableros (Streamlit + Plotly). Se ven en la pestaña «Tableros» de app/ui.py o solos: streamlit run app/tableros.py
Pestañas: Precios · Tiempos de tránsito · Capacidad · Disponibilidad de vehículos · Tendencias · Ranking y fichas · Gestión.
Paleta única y accesible: azul secuencial para magnitudes, azul↔rojo con gris al centro para el índice de precio,
máximo 3 proveedores en color a la vez (el resto en gris) y alertas siempre con ícono + texto. Datos sintéticos."""
from __future__ import annotations
import json, sys
from datetime import date, timedelta
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))
import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from scipy.stats import beta as beta_dist

from app import cliente_api as cli_api
from engine.fichas import ficha

SERIE = ["#2a78d6", "#eb6834", "#1baf7a"]          # slots categoricos 1-3 (validados todos-contra-todos)
GRIS = "#b4b2ab"; TINTA = "#0b0b0b"; TINTA2 = "#52514e"
AZUL = ["#cde2fb", "#9ec5f4", "#6da7ec", "#3987e5", "#256abf", "#184f95", "#0d366b"]
DIVERG = [[0, "#1c5cab"], [0.25, "#86b6ef"], [0.5, "#f0efec"], [0.75, "#f0a3a2"], [1, "#b8302f"]]
CRITICO, AVISO, BUENO = "#d03b3b", "#fab219", "#0ca30c"
BANDA = {"Diamante": "💎", "Zafiro": "🔷", "Cuarzo": "🔹", "Yeso": "⚪"}
FUENTE = dict(family="Source Sans Pro, sans-serif", size=15, color=TINTA)


def estilo(fig, alto=420, titulo=None):
    fig.update_layout(template="plotly_white", height=alto, font=FUENTE, margin=dict(l=10, r=10, t=60 if titulo else 20, b=10),
                      title=dict(text=titulo, font=dict(size=18)) if titulo else None, hoverlabel=dict(font_size=14),
                      legend=dict(orientation="h", y=-0.18))
    fig.update_xaxes(gridcolor="#ecebe8", zeroline=False); fig.update_yaxes(gridcolor="#ecebe8", zeroline=False)
    return fig


def corto(n: str) -> str:
    return n.replace(" del ", " ").replace("Logistics", "Log.").replace("Economica", "Económica")


def render(E):
    B = E.base
    est = E.motor.est
    ult = B.entregados.entrega_real.max().date()
    st.header("Tableros")
    st.caption("Datos **sintéticos** (COSCO no entregó datos). Distancias de Buenaventura reales; precios y desempeño son supuestos.")
    f1, f2, f3 = st.columns([2, 2, 3])
    cors = f1.multiselect("Corredores", list(B.corredores.index), default=list(B.corredores.index),
                          format_func=lambda c: f"{c} {B.corredores.loc[c].origen[:4]}→{B.corredores.loc[c].destino[:4]}")
    rango = f2.date_input("Fechas", (date(2026, 1, 1), ult), min_value=date(2025, 11, 1), max_value=ult)
    d0, d1 = (rango if isinstance(rango, tuple) and len(rango) == 2 else (date(2026, 1, 1), ult))
    nom = B.nombres
    resaltar = f3.multiselect("Proveedores resaltados (máx. 3; el resto en gris)", list(nom), default=["P01", "P02", "P03"],
                              format_func=nom.get, max_selections=3)
    cors = cors or list(B.corredores.index)
    as_of = pd.Timestamp(d1) + timedelta(hours=23, minutes=59)
    e = B.entregados
    e = e[e.corredor_id.isin(cors) & (e.entrega_real.dt.date >= d0) & (e.entrega_real.dt.date <= d1)]
    tabla = est.tabla(as_of)
    tabs = st.tabs(["Precios", "Tiempos de tránsito", "Capacidad", "Disponibilidad de vehículos", "Tendencias", "Ranking y fichas", "Gestión"])

    # ---------------- PRECIOS ----------------
    with tabs[0]:
        filas = []
        for (pid, c), _ in B.tarifas.groupby(["proveedor_id", "corredor_id"]):
            if c not in cors: continue
            pr = B.tarifa_vigente(pid, c, "V40", as_of)
            if pr: filas.append(dict(pid=pid, c=c, precio=pr))
        P = pd.DataFrame(filas)
        if P.empty:
            st.info("Sin tarifas V40 vigentes para el filtro.")
        else:
            P["indice"] = P.precio / P.groupby("c").precio.transform("median")
            M = P.pivot(index="pid", columns="c", values="indice").sort_index()
            caro = P.groupby("pid").indice.mean().idxmax(); barato = P.groupby("pid").indice.mean().idxmin()
            fig = go.Figure(go.Heatmap(z=M.values, x=M.columns, y=[nom[p] for p in M.index], colorscale=DIVERG, zmid=1.0, zmin=0.8, zmax=1.2,
                                       text=np.where(np.isnan(M.values), "", np.vectorize(lambda v: f"{v:.2f}")(np.nan_to_num(M.values))), texttemplate="%{text}",
                                       hovertemplate="%{y} · %{x}<br>índice de precio %{z:.2f}<extra></extra>", colorbar=dict(title="índice")))
            st.plotly_chart(estilo(fig, 470, f"{nom[barato]} es el más barato y {nom[caro]} el más caro (índice = tarifa V40 / mediana del corredor, al {d1})"), width="stretch")
            T = tabla[(tabla.tipo_carga == "general") & tabla.corredor_id.isin(cors)][["proveedor_id", "corredor_id", "p_tarde", "n_servicios"]]
            S = P.merge(T, left_on=["pid", "c"], right_on=["proveedor_id", "corredor_id"])
            S["punt"] = 1 - S.p_tarde
            r = float(np.corrcoef(S.indice, S.punt)[0, 1]) if len(S) > 2 else float("nan")
            fig = go.Figure()
            otros = S[~S.pid.isin(resaltar)]
            fig.add_scatter(x=otros.indice, y=otros.punt, mode="markers", marker=dict(size=10, color=GRIS, line=dict(color="#fcfcfb", width=2)), name="Otros",
                            text=[f"{nom[p]} · {c} · {n} serv." for p, c, n in zip(otros.pid, otros.c, otros.n_servicios)], hovertemplate="%{text}<br>índice %{x:.2f} · a tiempo %{y:.0%}<extra></extra>")
            for i, p in enumerate(resaltar):
                s = S[S.pid == p]
                fig.add_scatter(x=s.indice, y=s.punt, mode="markers+text", text=s.c, textposition="top center", name=nom[p],
                                marker=dict(size=12, color=SERIE[i], line=dict(color="#fcfcfb", width=2)),
                                customdata=s.n_servicios, hovertemplate=nom[p] + " · %{text} · %{customdata} serv.<br>índice %{x:.2f} · a tiempo %{y:.0%}<extra></extra>")
            fig.update_xaxes(title="índice de precio (1 = mediana del corredor)"); fig.update_yaxes(title="P(a tiempo) bayesiana", tickformat=".0%")
            concl = "pagar más no compra puntualidad" if (np.isnan(r) or r < 0.3) else "los más caros sí son más puntuales"
            st.plotly_chart(estilo(fig, 470, f"Precio vs. puntualidad: {concl} (correlación {r:+.2f})"), width="stretch")

    # ---------------- TRANSITO ----------------
    with tabs[1]:
        c_sel = st.selectbox("Corredor para el detalle", cors, key="tr_c")
        sub = e[e.corredor_id == c_sel]
        if sub.empty:
            st.info("Sin servicios en el filtro.")
        else:
            orden = sub.groupby("proveedor_id").transito_h.median().sort_values().index
            plazo = float(sub.plan_h.median())
            fig = go.Figure()
            for p in orden:
                s = sub[sub.proveedor_id == p]
                col = SERIE[resaltar.index(p)] if p in resaltar else "#6da7ec"
                fig.add_box(y=s.transito_h, name=f"{corto(nom[p])} ({len(s)})", marker_color=col, boxpoints=False, line=dict(width=2),
                            hovertemplate="%{y:.0f} h<extra>" + nom[p] + "</extra>")
            fig.add_hline(y=plazo, line_dash="dash", line_color=TINTA2, annotation_text=f"plazo típico {plazo:.0f} h")
            g = sub.groupby("proveedor_id").transito_h
            q = pd.DataFrame({"P50": g.quantile(.5), "P90": g.quantile(.9)})
            peor = q.P90.idxmax(); mejor = q.P90.idxmin()
            fig.update_yaxes(title="horas desde el cargue")
            st.plotly_chart(estilo(fig, 480, f"{c_sel}: {nom[mejor]} es el más predecible (P90 {q.P90.min():.0f} h); {nom[peor]} el más variable (P90 {q.P90.max():.0f} h)"), width="stretch")
            q["P90 > plazo"] = np.where(q.P90 > plazo, "⚠ sí", "no"); q.index = [nom[p] for p in q.index]
            st.dataframe(q.round(1), width="stretch")

    # ---------------- CAPACIDAD ----------------
    with tabs[2]:
        v_sel = st.selectbox("Vehículo", list(B.vehiculos.index), format_func=lambda v: f"{v} · {B.vehiculos.loc[v].nombre}", key="cap_v")
        cap = B.capacidad[(B.capacidad.tipo_vehiculo_id == v_sel) & (B.capacidad.fh.dt.date >= d0) & (B.capacidad.fh.dt.date <= d1)]
        if cap.empty:
            st.info("Sin reportes de capacidad para el filtro.")
        else:
            fl = B.flota[B.flota.tipo_vehiculo_id == v_sel].set_index("proveedor_id").cantidad
            Mx = cap.pivot_table(index="proveedor_id", columns=cap.fh.dt.date, values="unidades_disponibles", aggfunc="last").reindex(fl.index)
            ultima = cap[cap.fh == cap.fh.max()].set_index("proveedor_id").unidades_disponibles.reindex(fl.index).fillna(0)
            util = 1 - ultima / fl
            fig = go.Figure()
            fig.add_bar(x=[corto(nom[p]) for p in fl.index], y=fl.values - ultima.values, name="ocupadas", marker_color="#9ec5f4", marker_line=dict(color="#fcfcfb", width=2))
            fig.add_bar(x=[corto(nom[p]) for p in fl.index], y=ultima.values, name="disponibles", marker_color="#256abf", marker_line=dict(color="#fcfcfb", width=2),
                        text=[f"{u:.0%} usado" for u in util], textposition="outside")
            fig.update_layout(barmode="stack"); fig.update_yaxes(title="unidades")
            lleno = [nom[p] for p in fl.index if util[p] >= 0.9]
            st.plotly_chart(estilo(fig, 420, f"{v_sel} al {cap.fh.max().date()}: " + (f"⚠ casi sin cupo: {', '.join(lleno)}" if lleno else "todos con cupo")), width="stretch")
            fig = go.Figure(go.Heatmap(z=Mx.values, x=[str(c) for c in Mx.columns], y=[nom[p] for p in Mx.index], colorscale=[[i / 6, c] for i, c in enumerate(AZUL)],
                                       hovertemplate="%{y} · semana %{x}<br>%{z} unidades disponibles<extra></extra>", colorbar=dict(title="unid.")))
            st.plotly_chart(estilo(fig, 420, "Unidades disponibles por proveedor y semana (foto semanal)"), width="stretch")

    # ---------------- DISPONIBILIDAD DE VEHICULOS ----------------
    with tabs[3]:
        F = B.flota.pivot_table(index="proveedor_id", columns="tipo_vehiculo_id", values="cantidad", fill_value=0)
        fig = go.Figure(go.Heatmap(z=F.values, x=[f"{v} · {B.vehiculos.loc[v].nombre}" for v in F.columns], y=[nom[p] for p in F.index],
                                   colorscale=[[0, "#f0efec"], [0.01, AZUL[0]]] + [[(i + 1) / 7, c] for i, c in enumerate(AZUL)], text=F.values, texttemplate="%{text}",
                                   hovertemplate="%{y} · %{x}<br>%{z} unidades en flota<extra></extra>", showscale=False))
        alertas = []
        for c in cors:
            for v in B.vehiculos.index:
                t = B.tarifas[(B.tarifas.corredor_id == c) & (B.tarifas.tipo_vehiculo_id == v)].proveedor_id.unique()
                prov = [p for p in t if F.get(v, pd.Series(dtype=int)).get(p, 0) > 0]
                if len(prov) == 1: alertas.append((c, v, nom[prov[0]]))
                elif len(prov) == 0 and v in ("VRF", "VCB"): alertas.append((c, v, None))
        st.plotly_chart(estilo(fig, 470, f"Flota por tipo de vehículo: {len([a for a in alertas if a[2]])} combinaciones corredor × vehículo dependen de un solo proveedor"), width="stretch")
        for c, v, p in alertas:
            (st.error if p is None else st.warning)(f"{'⛔ Nadie' if p is None else '⚠ Solo ' + p} ofrece {v} ({B.vehiculos.loc[v].nombre}) en {c} {B.corredores.loc[c].origen}→{B.corredores.loc[c].destino}")

    # ---------------- TENDENCIAS ----------------
    with tabs[4]:
        w = e.assign(semana=e.entrega_real.dt.to_period("M").dt.start_time).groupby(["proveedor_id", "semana"]).a_tiempo.agg(["sum", "count"]).reset_index()   # mensual: la semana es demasiado ruidosa
        fig = go.Figure()
        for p in [x for x in nom if x not in resaltar]:
            s = w[w.proveedor_id == p]
            fig.add_scatter(x=s.semana, y=s["sum"] / s["count"], mode="lines", line=dict(color="#dcdad4", width=1.5), name=nom[p], showlegend=False,
                            hovertemplate=nom[p] + " · %{x|%b %Y}<br>%{y:.0%} a tiempo<extra></extra>")
        y_fin = []                                                          # para separar etiquetas finales
        for i, p in enumerate(resaltar):
            s = w[w.proveedor_id == p]
            if s.empty: continue
            yf = float(s["sum"].iloc[-1] / s["count"].iloc[-1]); k = sum(abs(yf - y) < 0.04 for y in y_fin); y_fin.append(yf)
            lo = beta_dist.ppf(0.05, 1 + s["sum"], 1 + s["count"] - s["sum"]); hi = beta_dist.ppf(0.95, 1 + s["sum"], 1 + s["count"] - s["sum"])
            fig.add_scatter(x=list(s.semana) + list(s.semana[::-1]), y=list(hi) + list(lo[::-1]), fill="toself", fillcolor=SERIE[i], opacity=0.15, line=dict(width=0),
                            hoverinfo="skip", showlegend=False)
            fig.add_scatter(x=s.semana, y=s["sum"] / s["count"], mode="lines+markers", line=dict(color=SERIE[i], width=2), marker=dict(size=8), name=nom[p],
                            customdata=s["count"], hovertemplate=nom[p] + " · %{x|%b %Y}<br>%{y:.0%} a tiempo (%{customdata} serv.)<extra></extra>")
            fig.add_annotation(x=s.semana.iloc[-1], y=float(s["sum"].iloc[-1] / s["count"].iloc[-1]), text=corto(nom[p]), showarrow=False, xanchor="left", xshift=8, yshift=-16 * k,
                               font=dict(color=TINTA, size=14))
        if pd.Timestamp("2026-08-01").date() >= d0:
            fig.add_vline(x=pd.Timestamp("2026-08-01").timestamp() * 1000, line_dash="dot", line_color=TINTA2)
        fig.update_yaxes(title="entregas a tiempo (mensual) · banda 90 %", tickformat=".0%", range=[0, 1.05])
        alert = [(p, est.tendencia(as_of, p)) for p in nom]; alert = [(p, t) for p, t in alert if t > 0]
        titulo = ("⚠ En deterioro: " + ", ".join(f"{nom[p]} (+{100*t:.0f} pts de retrasos)" for p, t in alert)) if alert else "Sin deterioros significativos en los últimos 30 días"
        st.plotly_chart(estilo(fig, 480, titulo), width="stretch")
        for p, t in alert:
            st.error(f"⛔ {nom[p]}: retrasos de los últimos 30 días {100*t:.0f} pts por encima de su año anterior (prueba binomial, p < 0,05)")
        rp = RAIZ / "data" / "replay.csv"
        if rp.exists():
            R = pd.read_csv(rp, parse_dates=["fecha"])
            p_r = st.selectbox("Repetición del tiempo (paso 9): P(tarde) estimada vs. real", list(nom), format_func=nom.get, key="rp")
            a = R[R.proveedor_id == p_r]
            fig = go.Figure()
            fig.add_scatter(x=a.fecha, y=a.p_tarde_est, name="estimada por el sistema (bayesiana)", line=dict(color=SERIE[0], width=2))
            fig.add_scatter(x=a.fecha, y=a.p_tarde_real, name="real (verdad oculta, solo evaluación)", line=dict(color=TINTA2, width=2, dash="dash"))
            fig.update_yaxes(tickformat=".0%", title="P(tarde)")
            st.plotly_chart(estilo(fig, 380, f"{nom[p_r]}: el sistema sigue a la realidad con unas semanas de amortiguación"), width="stretch")

    # ---------------- RANKING Y FICHAS ----------------
    with tabs[5]:
        G = tabla[(tabla.tipo_carga == "general") & tabla.corredor_id.isin(cors)]
        R = G.groupby("proveedor_id").agg(dureza=("indice_dureza", "mean"), puntualidad=("p_tarde", lambda x: 1 - x.mean()), servicios=("n_servicios", "sum")).sort_values("dureza", ascending=False)
        R["banda"] = [BANDA.get(b, "") + " " + (b or "") for b in [next((n for lim, n in E.cfg["dureza_bandas"] if d >= lim), "Yeso") for d in R.dureza]]
        R.insert(0, "proveedor", [nom[p] for p in R.index]); R.insert(0, "#", range(1, len(R) + 1))
        st.subheader(f"Ranking por Índice de Dureza (carga general, al {d1}): lidera {R.proveedor.iloc[0]}")
        st.dataframe(R.round({"dureza": 2, "puntualidad": 3}), hide_index=True, width="stretch",
                     column_config={"puntualidad": st.column_config.NumberColumn(format="percent")})
        D = G.pivot(index="proveedor_id", columns="corredor_id", values="indice_dureza").reindex(R.index)
        fig = go.Figure(go.Heatmap(z=D.values, x=D.columns, y=[nom[p] for p in D.index], colorscale=[[i / 6, c] for i, c in enumerate(AZUL)], zmin=5, zmax=9,
                                   text=np.where(np.isnan(D.values), "", np.vectorize(lambda v: f"{v:.1f}")(np.nan_to_num(D.values))), texttemplate="%{text}",
                                   hovertemplate="%{y} · %{x}<br>Dureza %{z:.1f}<extra></extra>", colorbar=dict(title="Dureza")))
        fig.update_yaxes(autorange="reversed")
        st.plotly_chart(estilo(fig, 470, "Dureza por corredor: el mismo proveedor puede ser fuerte en un corredor y débil en otro"), width="stretch")
        pf = st.selectbox("Ficha del proveedor", list(nom), format_func=nom.get, key="ficha")
        f = ficha(pf, as_of, B, est, E.cfg)
        a, b, c = st.columns(3)
        a.metric("Puntualidad general (ponderada)", f"{f['puntualidad_general']:.0%}" if f["puntualidad_general"] is not None else "—")
        b.metric("Dureza media", f["dureza_media"]); c.metric("Cuota 30 días", f"{f['cuota_30d']:.0%}")
        x, y, z = st.columns(3)
        x.markdown("**✅ Fortalezas**"); [x.success(t) for t in f["fortalezas"]] or x.caption("Ninguna con evidencia suficiente")
        y.markdown("**⚠ Debilidades**"); [y.warning(t) for t in f["debilidades"]] or y.caption("Ninguna con evidencia suficiente")
        z.markdown("**⛔ Riesgos activos**"); [z.error(t) for t in f["riesgos"]] or z.caption("Sin señales activas")

    # ---------------- GESTION ----------------
    with tabs[6]:
        s = B.servicios_todos
        s = s[(s.fecha_cargue.dt.date >= d0) & (s.fecha_cargue.dt.date <= d1) & s.corredor_id.isin(cors)]
        m = s.assign(mes=s.fecha_cargue.dt.to_period("M").dt.start_time).groupby(["mes", "proveedor_id"]).size().unstack(fill_value=0)
        cuota = m.div(m.sum(axis=1), axis=0)
        top = cuota.mean().sort_values(ascending=False).index[:3]
        hhi = (cuota ** 2).sum(axis=1)
        fig = go.Figure()
        for i, p in enumerate(top):
            fig.add_scatter(x=cuota.index, y=cuota[p], name=nom[p], mode="lines+markers", line=dict(color=SERIE[i], width=2), marker=dict(size=8),
                            hovertemplate=nom[p] + " · %{x|%b %Y}<br>%{y:.0%} del volumen<extra></extra>")
            fig.add_annotation(x=cuota.index[-1], y=float(cuota[p].iloc[-1]), text=corto(nom[p]), showarrow=False, xanchor="left", xshift=8)
        fig.add_scatter(x=cuota.index, y=cuota.drop(columns=top).sum(axis=1), name="Otros (9)", mode="lines", line=dict(color=GRIS, width=2))
        fig.add_hline(y=E.cfg["concentracion_umbral"], line_dash="dash", line_color=CRITICO, annotation_text="umbral 35 %")
        fig.update_yaxes(tickformat=".0%", title="cuota mensual")
        lider = top[0]
        st.plotly_chart(estilo(fig, 430, f"{nom[lider]} concentra {cuota[lider].iloc[-1]:.0%} del volumen del último mes" + (" ⚠ por encima del umbral" if cuota[lider].iloc[-1] > E.cfg['concentracion_umbral'] else "")), width="stretch")
        fig = go.Figure(go.Scatter(x=hhi.index, y=hhi, mode="lines+markers", line=dict(color=SERIE[0], width=2), marker=dict(size=8), name="HHI",
                                   hovertemplate="%{x|%b %Y}<br>HHI %{y:.3f}<extra></extra>"))
        fig.add_hline(y=0.25, line_dash="dash", line_color=CRITICO, annotation_text="alerta 0,25")
        fig.update_yaxes(title="HHI = Σ cuota²", rangemode="tozero")
        st.plotly_chart(estilo(fig, 330, f"Índice Herfindahl: {hhi.iloc[-1]:.3f} en el último mes ({'⚠ concentrado' if hhi.iloc[-1] > 0.25 else 'por debajo de 0,25'})"), width="stretch")
        dec = cli_api.tablero_decisiones()
        a, b, c = st.columns(3)
        if dec.empty:
            a.metric("Decisiones con el sistema", 0); st.info("Todavía no hay decisiones tomadas con el sistema: aprueba casos en «Nueva solicitud» o corre scripts/demo_api.py.")
        else:
            a.metric("Decisiones con el sistema", len(dec)); b.metric("Tasa de aceptación del #1", f"{dec.acepto_recomendacion.mean():.0%}")
            mot = dec[dec.acepto_recomendacion == 0].motivo.value_counts()
            c.metric("Motivo de rechazo más común", mot.index[0] if len(mot) else "—")
            if len(mot):
                fig = go.Figure(go.Bar(x=mot.values, y=mot.index, orientation="h", marker_color=SERIE[0], text=mot.values, textposition="outside"))
                st.plotly_chart(estilo(fig, 260, "Motivos al elegir otro proveedor"), width="stretch")
            cerr = cli_api.tablero_cierres()
            if len(cerr):
                filas = []
                for r in cerr.itertuples():
                    rk = {p["proveedor_id"]: p for p in json.loads(r.top3_y_desglose)["ranking"]}
                    if r.proveedor_elegido in rk:
                        real = r.costo_final + (0 if r.a_tiempo else E.cfg["costo_retraso"][r.nivel_servicio])
                        filas.append(dict(solicitud=r.solicitud_id, esperado=rk[r.proveedor_elegido]["costo_esperado"], real=real))
                if filas:
                    C = pd.DataFrame(filas)
                    st.markdown(f"**Costo esperado vs. real** (servicios cerrados con el sistema, {len(C)}): esperado medio {C.esperado.mean():,.0f} · real medio {C.real.mean():,.0f} COP "
                                "(real = costo final + costo de retraso del nivel si llegó tarde)".replace(",", "."))
                    st.dataframe(C, hide_index=True, width="stretch")


if __name__ == "__main__":
    st.set_page_config(page_title="Tableros COSCO", page_icon="📊", layout="wide")
    from app import contexto
    render(contexto.cargar())
