"""Paso 7 · API (FastAPI) del recomendador.
  POST /recomendar   SolicitudIn -> RecomendacionOut (se guarda en recomendacion)
  POST /decision     DecisionIn  -> registra la decision; acepto_recomendacion se calcula contra el Top-1; crea el servicio EN_CURSO
  POST /cierre       CierreServicioIn -> cierra el servicio, guarda feedback y actualiza la estadistica bayesiana al instante
  GET  /proveedores/{id}/ficha   estadisticas, Dureza, fortalezas, debilidades y riesgos
  GET  /salud
Persistencia: solo a traves de engine.repositorio.Repositorio (COSCO_REPO o COSCO_DB; por defecto SQLite data/cosco.db).
Lectura para interfaces: /config, /datos/tablas, /solicitudes/prueba, /solicitudes/{id}, /decisiones/{id}, /pendientes, /tableros/decisiones, /tableros/cierres.
Arranque: uvicorn app.api:app --reload"""
from __future__ import annotations
import json, os, threading
from datetime import datetime
from typing import Optional

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import JSONResponse, Response

from contratos.contracts import CierreServicioIn, DecisionIn, RecomendacionOut, SolicitudIn
from engine.datos import Base, cargar_config
from engine.repositorio import ErrorNegocio, crear_repositorio
from engine.estadisticas import actualizar_con_servicio
from engine.fichas import ficha
from engine.repositorio import DB_DEFECTO
from engine.motor_a import MotorA, as_of_de

ISO = "%Y-%m-%dT%H:%M"


class Estado:
    def __init__(self, destino: str):
        self.destino = destino
        self.repo = crear_repositorio(destino)
        self.cfg = cargar_config()
        self.base = Base(self.repo)
        self.motor = MotorA(self.base, self.cfg)
        self.lock = threading.Lock()
        self._registrar_modelo()

    @property
    def db(self) -> str:
        return self.repo.descripcion

    def _registrar_modelo(self):
        self.repo.registrar_modelo(self.motor.modelo_version, "bayesiano+costo_esperado", json.dumps({k: v for k, v in self.cfg.items() if not k.startswith("_")}),
                                   datetime.now().strftime(ISO), "equipo (pesos iniciales)")

    def recargar(self):
        self.base.invalidar()
        self.motor = MotorA(self.base, self.cfg)


ESTADO: Optional[Estado] = None


def _destino() -> str:
    return os.environ.get("COSCO_REPO") or os.environ.get("COSCO_DB") or str(DB_DEFECTO)


def estado() -> Estado:
    global ESTADO
    d = _destino()
    if ESTADO is None or ESTADO.destino != d:
        ESTADO = Estado(d)
    return ESTADO


app = FastAPI(title="Recomendador de proveedores · COSCO SHIPPING (datos sintéticos)", version="1.0")


@app.exception_handler(ErrorNegocio)
async def _negocio(_, exc: ErrorNegocio):
    return JSONResponse(status_code=exc.codigo, content={"detail": exc.detail})


@app.exception_handler(ValueError)
async def _valor(_, exc: ValueError):
    return JSONResponse(status_code=422, content={"error": str(exc)})


@app.get("/salud")
def salud():
    E = estado()
    return {"estado": "ok", "base": E.db, "modelo_version": E.motor.modelo_version, "conteos": E.repo.conteos(),
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
        E.repo.guardar_recomendacion(sol, out, as_of.strftime(ISO))
    return out


@app.post("/decision")
def decision(d: DecisionIn):
    E = estado()
    with E.lock:
        return E.repo.registrar_decision(d, E.base.tarifa_vigente, proveedores_validos=E.base.nombres, ventana_flex_h=E.cfg.get("ventana_flex_h", 72))


@app.post("/cierre")
def cierre(ci: CierreServicioIn):
    E = estado()
    with E.lock:
        r = E.repo.cerrar_servicio(ci)
        if not E.base.entregados.empty and E.repo.contar_estadisticas() == 0:
            from engine.estadisticas import calcular
            calcular(r["entrega_real"], base=E.base)
        nueva = actualizar_con_servicio(ci, base=E.base, cfg=E.cfg)
        E.recargar()
    return {"servicio_id": ci.servicio_id, "estadistica_actualizada": nueva,
            "aviso": None if r["coherente"] == ci.a_tiempo else "a_tiempo no coincide con entrega_real <= entrega_planeada; se guardó lo reportado"}


@app.get("/proveedores/{pid}/ficha")
def ficha_proveedor(pid: str, as_of: Optional[str] = Query(None, description="fecha AAAA-MM-DD; por defecto el último dato")):
    E = estado()
    if pid not in E.base.nombres:
        raise HTTPException(404, f"proveedor {pid} no existe")
    f = as_of or str(E.base.entregados.entrega_real.max())
    return ficha(pid, f, E.base, E.motor.est, E.cfg)


# ---------- lectura para interfaces (la UI no abre la base de datos) ----------
def _json(df) -> str:
    return df.to_json(orient="records", date_format="iso", force_ascii=False)


@app.get("/config")
def config():
    return {k: v for k, v in estado().cfg.items()}


@app.get("/datos/tablas")
def datos_tablas():
    """Tablas de referencia y servicios para que una interfaz arme su propia instantánea (sin acceso a la base)."""
    T = estado().repo.tablas_base()
    cuerpo = "{" + ",".join(f'"{k}":{_json(v)}' for k, v in T.items()) + "}"
    return Response(cuerpo, media_type="application/json")


@app.get("/solicitudes/prueba")
def solicitudes_prueba():
    return estado().repo.solicitudes_prueba()


@app.get("/solicitudes/{sid}")
def solicitud(sid: str):
    r = estado().repo.solicitud(sid)
    if not r:
        raise HTTPException(404, f"solicitud {sid} no existe")
    return r


@app.get("/decisiones/{sid}")
def decision_de(sid: str):
    return estado().repo.decision_de(sid)


@app.get("/pendientes")
def pendientes(filtro: str = Query("revision", pattern="^(revision|gerencia)$")):
    E = estado()
    out = []
    for j in E.repo.recomendaciones_sin_decision():
        rec = RecomendacionOut.model_validate_json(j)
        if (filtro == "revision" and rec.requiere_revision and not rec.escalar_gerencia) or (filtro == "gerencia" and rec.escalar_gerencia):
            s = E.repo.solicitud(rec.solicitud_id)
            if s:
                out.append({"recomendacion": json.loads(j), "solicitud": s})
    return out


@app.get("/tableros/decisiones")
def tablero_decisiones():
    return Response(_json(estado().repo.decisiones_tablero()), media_type="application/json")


@app.get("/tableros/cierres")
def tablero_cierres():
    return Response(_json(estado().repo.cierres_tablero()), media_type="application/json")
