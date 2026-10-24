"""Paso 7 · API (FastAPI) del recomendador.
  POST /recomendar   SolicitudIn -> RecomendacionOut (se guarda en recomendacion)
  POST /decision     DecisionIn  -> registra la decision; acepto_recomendacion se calcula contra el Top-1; crea el servicio EN_CURSO
  POST /cierre       CierreServicioIn -> cierra el servicio, guarda feedback y actualiza la estadistica bayesiana al instante
  GET  /proveedores/{id}/ficha   estadisticas, Dureza, fortalezas, debilidades y riesgos
  GET  /salud
Base de datos: variable de entorno COSCO_DB (por defecto data/cosco.db).
Arranque: uvicorn app.api:app --reload"""
from __future__ import annotations
import json, os, sqlite3, threading, uuid
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

import pandas as pd
from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import JSONResponse

from contratos.contracts import CierreServicioIn, DecisionIn, RecomendacionOut, SolicitudIn
from engine.datos import DB_DEFECTO, Base, cargar_config
from engine.estadisticas import actualizar_con_servicio
from engine.fichas import ficha
from engine.motor_a import MotorA, as_of_de

ISO = "%Y-%m-%dT%H:%M"


def migrar(db: str):
    """Asegura que una base creada con un esquema anterior acepte el estado EN_CURSO (paso 7) y tenga nivel_respaldo (paso 4)."""
    con = sqlite3.connect(db)
    sql = con.execute("SELECT sql FROM sqlite_master WHERE name='servicio'").fetchone()[0]
    if "EN_CURSO" not in sql:
        con.execute("PRAGMA foreign_keys=OFF")
        nuevo = sql.replace("'RECHAZADO')", "'RECHAZADO','EN_CURSO')").replace("CREATE TABLE servicio", "CREATE TABLE servicio_nuevo", 1)
        con.executescript(f"""BEGIN; {nuevo}; INSERT INTO servicio_nuevo SELECT * FROM servicio; DROP TABLE servicio;
                              ALTER TABLE servicio_nuevo RENAME TO servicio;
                              CREATE INDEX IF NOT EXISTS ix_serv_prov ON servicio (proveedor_id, entrega_real); COMMIT;""")
    cols = [r[1] for r in con.execute("PRAGMA table_info(estadistica_proveedor)")]
    if "nivel_respaldo" not in cols:
        con.execute("ALTER TABLE estadistica_proveedor ADD COLUMN nivel_respaldo TEXT")
    con.commit(); con.close()


class Estado:
    def __init__(self, db: str):
        self.db = db
        migrar(db)
        self.cfg = cargar_config()
        self.base = Base(db)
        self.motor = MotorA(self.base, self.cfg)
        self.lock = threading.Lock()
        self._registrar_modelo()

    def con(self):
        c = sqlite3.connect(self.db); c.execute("PRAGMA foreign_keys = ON"); return c

    def _registrar_modelo(self):
        with self.con() as c:
            c.execute("INSERT OR IGNORE INTO modelo_version VALUES (?,?,?,?,?)",
                      (self.motor.modelo_version, "bayesiano+costo_esperado", json.dumps({k: v for k, v in self.cfg.items() if not k.startswith("_")}),
                       datetime.now().strftime(ISO), "equipo (pesos iniciales)"))

    def recargar(self):
        self.base.invalidar()
        self.motor = MotorA(self.base, self.cfg)


ESTADO: Optional[Estado] = None


def estado() -> Estado:
    global ESTADO
    db = os.environ.get("COSCO_DB", str(DB_DEFECTO))
    if ESTADO is None or ESTADO.db != db:
        ESTADO = Estado(db)
    return ESTADO


app = FastAPI(title="Recomendador de proveedores · COSCO SHIPPING (datos sintéticos)", version="1.0")


@app.exception_handler(ValueError)
async def _valor(_, exc: ValueError):
    return JSONResponse(status_code=422, content={"error": str(exc)})


@app.get("/salud")
def salud():
    E = estado()
    with E.con() as c:
        n = {t: c.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0] for t in ("proveedor", "solicitud", "servicio", "recomendacion", "decision", "estadistica_proveedor")}
    return {"estado": "ok", "base": E.db, "modelo_version": E.motor.modelo_version, "conteos": n,
            "ultimo_entregado": str(E.base.entregados.entrega_real.max()), "datos": "sintéticos"}


@app.post("/recomendar", response_model=RecomendacionOut)
def recomendar(sol: SolicitudIn):
    E = estado()
    b = E.base
    if sol.corredor_id not in b.corredores.index:
        raise HTTPException(422, f"corredor desconocido: {sol.corredor_id}")
    if sol.tipo_vehiculo_req not in b.vehiculos.index:
        raise HTTPException(422, f"tipo de vehículo desconocido: {sol.tipo_vehiculo_req}")
    if sol.cliente_id not in b.clientes.index:
        raise HTTPException(422, f"cliente desconocido: {sol.cliente_id}")
    cap = float(b.vehiculos.loc[sol.tipo_vehiculo_req].capacidad_ton)
    if sol.peso_ton > cap:
        raise HTTPException(422, f"el peso ({sol.peso_ton} t) supera la capacidad del vehículo {sol.tipo_vehiculo_req} ({cap:g} t)")
    with E.lock:
        out = E.motor.recomendar(sol)
        as_of = as_of_de(sol)
        with E.con() as c:
            if not c.execute("SELECT 1 FROM solicitud WHERE solicitud_id=?", (sol.solicitud_id,)).fetchone():
                c.execute("INSERT INTO solicitud VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
                          (sol.solicitud_id, sol.cliente_id, sol.corredor_id, sol.tipo_vehiculo_req, sol.tipo_carga, sol.peso_ton, int(sol.mercancia_peligrosa),
                           as_of.strftime(ISO), pd.Timestamp(sol.fecha_cargue).strftime(ISO), pd.Timestamp(sol.plazo_entrega).strftime(ISO),
                           sol.nivel_servicio.value, sol.tarifa_cliente, "vivo"))
            c.execute("INSERT OR REPLACE INTO recomendacion VALUES (?,?,?,?,?,?,?)",
                      (out.recomendacion_id, sol.solicitud_id, out.modelo_version, out.model_dump_json(), out.confianza, int(out.requiere_revision), as_of.strftime(ISO)))
    return out


@app.post("/decision")
def decision(d: DecisionIn):
    E = estado()
    with E.con() as c:
        so = c.execute("SELECT fecha_cargue, plazo_entrega, nivel_servicio, corredor_id, tipo_vehiculo_req FROM solicitud WHERE solicitud_id=?", (d.solicitud_id,)).fetchone()
        if not so:
            raise HTTPException(404, f"solicitud {d.solicitud_id} no existe: llama primero a /recomendar")
        if d.recomendacion_id:
            r = c.execute("SELECT recomendacion_id, top3_y_desglose FROM recomendacion WHERE recomendacion_id=? AND solicitud_id=?", (d.recomendacion_id, d.solicitud_id)).fetchone()
        else:
            r = c.execute("SELECT recomendacion_id, top3_y_desglose FROM recomendacion WHERE solicitud_id=? ORDER BY fecha DESC LIMIT 1", (d.solicitud_id,)).fetchone()
        if not r:
            raise HTTPException(404, "no hay recomendación para esa solicitud")
        rec = RecomendacionOut.model_validate_json(r[1])
        if d.proveedor_elegido not in E.base.nombres:
            raise HTTPException(422, f"proveedor desconocido: {d.proveedor_elegido}")
        desc = {x.proveedor_id: x for x in rec.descartados}
        if d.proveedor_elegido in desc:
            x = desc[d.proveedor_elegido]
            raise HTTPException(422, f"{d.proveedor_elegido} fue descartado por regla dura ({x.motivo}: {x.detalle}); no se puede asignar")
        top1 = rec.ranking[0].proveedor_id if rec.ranking else None
        acepto = d.proveedor_elegido == top1
        if not acepto and d.motivo is None:
            raise HTTPException(422, "motivo obligatorio cuando no se elige el #1 (precio, relacion, capacidad, experiencia_previa, cliente_pidio, otro)")
        ahora = pd.Timestamp(rec.generado_en)
        did = "D-" + uuid.uuid4().hex[:10]
        c.execute("INSERT INTO decision VALUES (?,?,?,?,?,?,?,?)",
                  (did, d.solicitud_id, r[0], d.proveedor_elegido, d.usuario, int(acepto), d.motivo, ahora.strftime(ISO)))
        fc, plazo, nivel, cor, veh = so
        precio = E.base.tarifa_vigente(d.proveedor_elegido, cor, veh, fc)
        if precio is None:
            raise HTTPException(422, f"{d.proveedor_elegido} no tiene tarifa vigente para {veh} en {cor}")
        plan = pd.Timestamp(plazo) - (timedelta(hours=E.cfg.get("ventana_flex_h", 72)) if nivel == "Flexible" else timedelta(0))
        sid = "SV-" + uuid.uuid4().hex[:10]
        c.execute("INSERT INTO servicio (servicio_id, solicitud_id, proveedor_id, precio_pactado, entrega_planeada, estado) VALUES (?,?,?,?,?, 'EN_CURSO')",
                  (sid, d.solicitud_id, d.proveedor_elegido, precio, plan.strftime(ISO)))
    return {"decision_id": did, "servicio_id": sid, "acepto_recomendacion": acepto, "top1": top1, "precio_pactado": precio,
            "entrega_planeada": plan.strftime(ISO)}


@app.post("/cierre")
def cierre(ci: CierreServicioIn):
    E = estado()
    with E.lock:
        with E.con() as c:
            r = c.execute("""SELECT s.estado, s.precio_pactado, so.fecha_cargue, s.entrega_planeada FROM servicio s JOIN solicitud so USING(solicitud_id)
                             WHERE servicio_id=?""", (ci.servicio_id,)).fetchone()
            if not r:
                raise HTTPException(404, f"servicio {ci.servicio_id} no existe")
            est_s, precio, fc, plan = r
            if est_s != "EN_CURSO":
                raise HTTPException(409, f"el servicio ya está cerrado ({est_s})")
            ent = pd.Timestamp(ci.entrega_real)
            if ent <= pd.Timestamp(fc):
                raise HTTPException(422, "la entrega real debe ser posterior al cargue")
            if ci.costo_final < precio:
                raise HTTPException(422, f"costo_final ({ci.costo_final}) menor que el precio pactado ({precio})")
            coherente = ent <= pd.Timestamp(plan)
            c.execute("""UPDATE servicio SET cargue_real=COALESCE(cargue_real, ?), entrega_real=?, a_tiempo=?, costo_final=?, dias_detencion=?, estado='ENTREGADO'
                         WHERE servicio_id=?""", (fc, ent.strftime(ISO), int(ci.a_tiempo), ci.costo_final, ci.dias_detencion, ci.servicio_id))
            if ci.hubo_incidente:
                c.execute("INSERT INTO evento_servicio (servicio_id, tipo, fecha_hora, detalle) VALUES (?,?,?,?)",
                          (ci.servicio_id, "INCIDENTE", (pd.Timestamp(fc) + (ent - pd.Timestamp(fc)) / 2).strftime(ISO), "reportado al cierre"))
            if ci.feedback_puntaje:
                c.execute("INSERT INTO feedback VALUES (?,?,?,?)", (ci.servicio_id, "operador", ci.feedback_puntaje, ci.feedback_causa))
        if not E.base.entregados.empty and not sqlite3.connect(E.db).execute("SELECT COUNT(*) FROM estadistica_proveedor").fetchone()[0]:
            from engine.estadisticas import calcular
            calcular(ent, base=E.base)
        nueva = actualizar_con_servicio(ci, base=E.base, cfg=E.cfg)
        E.recargar()
    return {"servicio_id": ci.servicio_id, "estadistica_actualizada": nueva,
            "aviso": None if coherente == ci.a_tiempo else "a_tiempo no coincide con entrega_real <= entrega_planeada; se guardó lo reportado"}


@app.get("/proveedores/{pid}/ficha")
def ficha_proveedor(pid: str, as_of: Optional[str] = Query(None, description="fecha AAAA-MM-DD; por defecto el último dato")):
    E = estado()
    if pid not in E.base.nombres:
        raise HTTPException(404, f"proveedor {pid} no existe")
    f = as_of or str(E.base.entregados.entrega_real.max())
    return ficha(pid, f, E.base, E.motor.est, E.cfg)
