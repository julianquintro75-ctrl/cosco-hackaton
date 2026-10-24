"""Paso 8 · Interfaz del operador (Streamlit). Arranque: streamlit run app/ui.py
Pantallas: Nueva solicitud · Revisión · Gerencia · Tableros. Usa la misma lógica que la API (en proceso) y la misma base (COSCO_DB)."""
from __future__ import annotations
import json, sqlite3, sys, uuid
from datetime import datetime, time as dtime, timedelta
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))
import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from fastapi import HTTPException

from app import api
from contratos.contracts import DecisionIn, RecomendacionOut, SolicitudIn

st.set_page_config(page_title="Recomendador COSCO", page_icon="🚚", layout="wide")
st.markdown("""<style>
html, body, [class*="css"] { font-size: 19px; }
h1 { font-size: 2.0rem !important; } h2 { font-size: 1.6rem !important; } h3 { font-size: 1.3rem !important; }
div[data-testid="stDataFrame"] div { font-size: 18px; }
.top-linea { font-size: 1.15rem; padding: .4rem .8rem; border-left: 6px solid #1f4e79; background: rgba(31,78,121,.08); margin-bottom: .6rem; }
</style>""", unsafe_allow_html=True)

BANDA = {"Diamante": "💎 Diamante", "Zafiro": "🔷 Zafiro", "Cuarzo": "🔹 Cuarzo", "Yeso": "⚪ Yeso", None: "—"}
MOTIVOS = {"precio": "Precio", "relacion": "Relación con el proveedor", "capacidad": "Capacidad confirmada por teléfono",
           "experiencia_previa": "Experiencia previa", "cliente_pidio": "El cliente lo pidió", "otro": "Otro"}
REVISION = {"urgente": "Nivel Urgente: revisión detallada obligatoria", "empate_tecnico": "Empate técnico: Top-1 y Top-2 a menos de 3 %",
            "confianza_baja": "Confianza baja: poca evidencia o poca separación", "sin_candidato_en_plazo": "Nadie cumple el plazo con 90 % de confianza (P90)",
            "sin_opcion": "Sin opción: ningún proveedor pasa los filtros duros", "margen_negativo": "Margen esperado negativo"}
COMP = [("precio", "Precio", "#1f4e79"), ("retraso_esperado", "Retraso esperado", "#d9822b"), ("incidente_esperado", "Incidente esperado", "#a23b72"),
        ("incertidumbre", "Incertidumbre", "#8c8c8c"), ("concentracion", "Concentración", "#5b8e7d")]


def cop(x) -> str:
    return "$" + f"{int(round(x)):,}".replace(",", ".")


def millones(x) -> str:
    return f"${x/1e6:,.2f} M".replace(",", "X").replace(".", ",").replace("X", ".")


E = api.estado()
B = E.base
NOM_COR = {c: f"{c} · {r.origen} → {r.destino} ({r.distancia_km:g} km)" for c, r in B.corredores.iterrows()}
NOM_VEH = {v: f"{v} · {r.nombre}" for v, r in B.vehiculos.iterrows()}


def con():
    return sqlite3.connect(E.db)


def solicitud_de_bd(sid: str) -> dict | None:
    c = con(); c.row_factory = sqlite3.Row
    r = c.execute("SELECT * FROM solicitud WHERE solicitud_id=?", (sid,)).fetchone()
    return dict(r) if r else None


# ---------------- vista de una recomendación (reutilizada en las tres pantallas) ----------------
def mostrar_recomendacion(rec: RecomendacionOut, sol: dict, clave: str, rol: str = "operador"):
    fc = pd.Timestamp(sol["fecha_cargue"]); H = (pd.Timestamp(sol["plazo_entrega"]) - fc).total_seconds() / 3600
    st.markdown(f"<div class='top-linea'><b>Solicitud {rec.solicitud_id}</b> · {NOM_COR[sol['corredor_id']]} · {NOM_VEH[sol['tipo_vehiculo_req']]} · "
                f"carga {sol['tipo_carga']} · cargue {fc:%d/%m %H:%M} · plazo {H:.0f} h · <b>{sol['nivel_servicio']}</b> · tarifa al cliente {cop(sol['tarifa_cliente'])}"
                f"<br><small>Modelo {rec.modelo_version} · confianza {rec.confianza:.0%} · {rec.latencia_ms or 0:.0f} ms · datos sintéticos</small></div>", unsafe_allow_html=True)
    if rec.escalar_gerencia:
        st.error("⛔ Escalar a gerencia: " + " · ".join(REVISION.get(m, m) for m in rec.motivos_revision if m in ("margen_negativo", "sin_candidato_en_plazo", "sin_opcion")))
    if rec.requiere_revision:
        st.warning("⚠ Revisión detallada: " + " · ".join(REVISION.get(m, m) for m in rec.motivos_revision))
    else:
        st.success("✓ Confianza alta: se puede aprobar en un clic")
    if rec.ranking:
        filas = []
        for p in rec.ranking:
            filas.append({"#": p.posicion, "Proveedor": p.nombre, "Precio": millones(p.desglose.precio),
                          "Tránsito P50 / P90": f"{p.transito_p50_h:.0f} h / {p.transito_p90_h:.0f} h",                           "Capacidad": f"{p.capacidad_unidades} unid." if p.capacidad_unidades is not None else "sin reporte",
                          "P(a tiempo) · IC 90 %": f"{p.p_a_tiempo:.0%} ({p.ic90_p_a_tiempo[0]:.0%}–{p.ic90_p_a_tiempo[1]:.0%}) · {p.n_servicios_corredor} serv.",
                          "Dureza": BANDA[p.banda_dureza] + (f" {p.indice_dureza:.1f}" if p.indice_dureza is not None else ""),
                          "Costo esperado": millones(p.costo_esperado), "Margen": millones(p.margen_esperado)})
        st.dataframe(pd.DataFrame(filas), hide_index=True, width="stretch")
        izq, der = st.columns([3, 2])
        with izq:
            st.markdown("**Alertas y por qué**")
            for p in rec.ranking:
                with st.expander(f"#{p.posicion} {p.nombre} — {len(p.alertas)} alerta(s)", expanded=p.posicion == 1):
                    for a in p.alertas:
                        (st.error if ("Plazo" in a or "empeorar" in a) else st.warning)(a)
                    if not p.alertas:
                        st.info("Sin alertas")
                    for f in p.factores_clave:
                        st.markdown(f"- {f}")
            if rec.explicacion_texto:
                st.info(rec.explicacion_texto)
        with der:
            fig = go.Figure()
            nombres = [f"#{p.posicion} {p.nombre}" for p in rec.ranking][::-1]
            for k, nom, col in COMP:
                fig.add_bar(y=nombres, x=[getattr(p.desglose, k) / 1e6 for p in rec.ranking][::-1], name=nom, orientation="h", marker_color=col)
            fig.add_vline(x=sol["tarifa_cliente"] / 1e6, line_dash="dash", annotation_text="tarifa al cliente")
            fig.update_layout(barmode="stack", height=300, margin=dict(l=10, r=10, t=40, b=10), title="Desglose del costo esperado (millones COP)",
                              legend=dict(orientation="h", y=-0.25), font=dict(size=15))
            st.plotly_chart(fig, width="stretch", key=f"g_{clave}")
    if rec.descartados:
        st.markdown("**Descartados por reglas duras:** " + " · ".join(f"{B.nombres[d.proveedor_id]} ({d.motivo.replace('_', ' ')}: {d.detalle})" for d in rec.descartados))
    if rec.sugerencia_prueba:
        st.info(f"🧪 Sugerencia de prueba (aparte del ranking): {rec.sugerencia_prueba.razon}")
    decidir(rec, sol, clave, rol)


def decidir(rec: RecomendacionOut, sol: dict, clave: str, rol: str):
    c = con()
    ya = c.execute("SELECT proveedor_elegido, acepto_recomendacion, motivo, usuario FROM decision WHERE solicitud_id=? AND recomendacion_id IS NOT NULL", (rec.solicitud_id,)).fetchone()
    if ya:
        st.success(f"Decisión registrada: {B.nombres[ya[0]]} · {'aceptó la recomendación' if ya[1] else 'eligió otro (' + MOTIVOS.get(ya[2], ya[2]) + ')'} · usuario {ya[3]}")
        return
    usuario = st.text_input("Usuario", value=rol, key=f"u_{clave}")
    col1, col2 = st.columns(2)
    if rec.ranking and col1.button(f"✅ Aprobar #1 · {rec.ranking[0].nombre}", key=f"ap_{clave}", type="primary", width="stretch"):
        registrar(DecisionIn(recomendacion_id=rec.recomendacion_id, solicitud_id=rec.solicitud_id, proveedor_elegido=rec.ranking[0].proveedor_id, usuario=usuario))
    with col2.popover("Elegir otro (motivo obligatorio)", width="stretch"):
        desc = {d.proveedor_id for d in rec.descartados}
        opciones = [p for p in B.proveedores.proveedor_id if p not in desc and (not rec.ranking or p != rec.ranking[0].proveedor_id)]
        elegido = st.selectbox("Proveedor", opciones, format_func=lambda p: B.nombres[p], key=f"o_{clave}")
        motivo = st.selectbox("Motivo", [None] + list(MOTIVOS), format_func=lambda m: "— elige un motivo —" if m is None else MOTIVOS[m], key=f"m_{clave}")
        if st.button("Confirmar elección", key=f"c_{clave}", disabled=motivo is None or not opciones):
            registrar(DecisionIn(recomendacion_id=rec.recomendacion_id, solicitud_id=rec.solicitud_id, proveedor_elegido=elegido, usuario=usuario, motivo=motivo))


def registrar(d: DecisionIn):
    try:
        r = api.decision(d)
        st.session_state["aviso"] = f"Decisión guardada · servicio {r['servicio_id']} asignado a {B.nombres[d.proveedor_elegido]} por {cop(r['precio_pactado'])}"
        st.rerun()
    except HTTPException as e:
        st.error(e.detail)


def pendientes(filtro: str) -> list[tuple[RecomendacionOut, dict]]:
    c = con()
    filas = c.execute("""SELECT r.top3_y_desglose FROM recomendacion r WHERE NOT EXISTS (SELECT 1 FROM decision d WHERE d.solicitud_id=r.solicitud_id AND d.recomendacion_id IS NOT NULL)
                         ORDER BY r.fecha DESC LIMIT 200""").fetchall()
    out = []
    for (j,) in filas:
        rec = RecomendacionOut.model_validate_json(j)
        if (filtro == "revision" and rec.requiere_revision and not rec.escalar_gerencia) or (filtro == "gerencia" and rec.escalar_gerencia):
            s = solicitud_de_bd(rec.solicitud_id)
            if s: out.append((rec, s))
    return out


# ---------------- pantallas ----------------
def pantalla_nueva():
    st.header("Nueva solicitud")
    c = con(); c.row_factory = sqlite3.Row
    ej = [dict(r) for r in c.execute("SELECT * FROM solicitud WHERE fase='prueba' ORDER BY solicitud_id")]
    idx = {f"{r['solicitud_id']} · {r['corredor_id']} {r['tipo_vehiculo_req']} {r['tipo_carga']} {r['nivel_servicio']}": r for r in ej}
    base = idx[st.selectbox("Cargar un caso de la fase de prueba (1–15 oct 2026) como plantilla", list(idx))] if idx else {}
    with st.form("sol"):
        a, b, cc = st.columns(3)
        corredor = a.selectbox("Corredor", list(NOM_COR), index=list(NOM_COR).index(base.get("corredor_id", "C1")), format_func=NOM_COR.get)
        vehiculo = b.selectbox("Vehículo requerido", list(NOM_VEH), index=list(NOM_VEH).index(base.get("tipo_vehiculo_req", "V40")), format_func=NOM_VEH.get)
        cargas = ["general", "refrigerada", "peligrosa", "sobredimensionada"]
        carga = cc.selectbox("Tipo de carga", cargas, index=cargas.index(base.get("tipo_carga", "general")))
        a, b, cc = st.columns(3)
        peso = a.number_input("Peso (t)", 0.5, 40.0, float(base.get("peso_ton", 20.0)))
        niveles = ["Flexible", "Estandar", "Urgente"]
        nivel = b.selectbox("Nivel de servicio", niveles, index=niveles.index(base.get("nivel_servicio", "Estandar")))
        tarifa = cc.number_input("Tarifa al cliente (COP)", 100_000, 50_000_000, int(base.get("tarifa_cliente", 4_000_000)), step=50_000)
        fc0 = pd.Timestamp(base.get("fecha_cargue", "2026-10-17T08:00"))
        H0 = (pd.Timestamp(base.get("plazo_entrega", "2026-10-18T08:00")) - fc0).total_seconds() / 3600
        a, b, cc, d = st.columns(4)
        f_cargue = a.date_input("Fecha de cargue", fc0.date()); h_cargue = b.time_input("Hora de cargue", fc0.time())
        plazo_h = cc.number_input("Plazo (horas desde el cargue)", 1.0, 400.0, float(round(H0, 1)))
        cliente = d.selectbox("Cliente", list(B.clientes.index), index=list(B.clientes.index).index(base.get("cliente_id", "K001")))
        peligrosa = st.checkbox("Mercancía peligrosa (exige IMO)", value=bool(base.get("mercancia_peligrosa", 0)))
        asof_def = (fc0 - timedelta(days=1))
        a, b = st.columns(2)
        asof_d = a.date_input("«Hoy» del sistema (as_of): solo se usa lo que se sabía hasta aquí", asof_def.date())
        asof_t = b.time_input("Hora as_of", asof_def.time())
        ir = st.form_submit_button("Recomendar", type="primary", width="stretch")
    if ir:
        fc = datetime.combine(f_cargue, h_cargue)
        try:
            sol = SolicitudIn(solicitud_id=f"N-{uuid.uuid4().hex[:8]}", cliente_id=cliente, corredor_id=corredor, tipo_vehiculo_req=vehiculo, tipo_carga=carga,
                              peso_ton=peso, mercancia_peligrosa=peligrosa, fecha_cargue=fc, plazo_entrega=fc + timedelta(hours=plazo_h), nivel_servicio=nivel,
                              tarifa_cliente=int(tarifa), as_of=datetime.combine(asof_d, asof_t))
            st.session_state["rec"] = api.recomendar(sol).model_dump_json()
            st.session_state["sol_id"] = sol.solicitud_id
        except HTTPException as e:
            st.error(e.detail)
        except ValueError as e:
            st.error(f"Datos inválidos: {e}")
    if st.session_state.get("rec"):
        rec = RecomendacionOut.model_validate_json(st.session_state["rec"])
        s = solicitud_de_bd(rec.solicitud_id)
        if s:
            st.divider(); mostrar_recomendacion(rec, s, "nueva")


def pantalla_lista(filtro: str, titulo: str, rol: str, vacio: str):
    st.header(titulo)
    p = pendientes(filtro)
    if not p:
        st.info(vacio); return
    st.caption(f"{len(p)} casos pendientes, del más reciente al más antiguo")
    opc = {f"{r.solicitud_id} · {s['corredor_id']} {s['nivel_servicio']} · " + ", ".join(REVISION.get(m, m).split(":")[0] for m in r.motivos_revision): (r, s) for r, s in p}
    k = st.selectbox("Caso", list(opc))
    r, s = opc[k]
    mostrar_recomendacion(r, s, f"{filtro}_{r.solicitud_id}", rol)


def pantalla_tableros():
    try:
        from app import tableros
        tableros.render(E)
    except ImportError:
        st.info("Los tableros se agregan en el paso 12 (app/tableros.py).")


st.sidebar.markdown("## 🚚 Recomendador")
st.sidebar.caption("COSCO SHIPPING · transporte terrestre Colombia\n\nDatos **sintéticos** (COSCO no entregó datos).")
pag = st.sidebar.radio("Pantalla", ["Nueva solicitud", "Revisión", "Gerencia", "Tableros"])
if st.session_state.get("aviso"):
    st.success(st.session_state.pop("aviso"))
if pag == "Nueva solicitud":
    pantalla_nueva()
elif pag == "Revisión":
    pantalla_lista("revision", "Revisión detallada", "analista", "No hay casos pendientes de revisión.")
elif pag == "Gerencia":
    pantalla_lista("gerencia", "Escalamientos a gerencia", "gerencia", "No hay escalamientos pendientes.")
else:
    pantalla_tableros()
