"""Paso 7 · API (FastAPI) del recomendador.
  POST /recomendar   SolicitudIn -> RecomendacionOut (se guarda en recomendacion)
  POST /decision     DecisionIn  -> registra la decision; acepto_recomendacion se calcula contra el Top-1; crea el servicio EN_CURSO
  POST /cierre       CierreServicioIn -> cierra el servicio, guarda feedback y actualiza la estadistica bayesiana al instante
  GET  /proveedores/{id}/ficha   estadisticas, Dureza, fortalezas, debilidades y riesgos
  GET  /salud
Persistencia: solo a traves de engine.repositorio.Repositorio (COSCO_REPO o COSCO_DB; por defecto SQLite data/cosco.db).
Lectura para interfaces: /config, /datos/tablas, /solicitudes/prueba, /solicitudes/{id}, /decisiones/{id}, /pendientes, /tableros/decisiones, /tableros/cierres.
Roles: solicitante (pide y ve lo suyo) · operador (revisa y decide) · gerencia (todo, además decide lo escalado y gestiona los avisos).
Avisos por Slack: ver app/notificaciones.py. Arranque: uvicorn app.api:app --reload"""
from __future__ import annotations
import json, os, threading, uuid
from contextlib import asynccontextmanager
from datetime import datetime
from typing import Literal, Optional

from fastapi import BackgroundTasks, Depends, FastAPI, HTTPException, Query
from pydantic import BaseModel, Field
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import JSONResponse, Response

from app import auth, notificaciones
from contratos.contracts import CierreServicioIn, DecisionIn, Nivel, RecomendacionOut, SolicitudIn
from engine.datos import Base, cargar_config
from engine.repositorio import ErrorNegocio, crear_repositorio
from engine.estadisticas import actualizar_con_servicio
from engine.fichas import ficha
from engine.repositorio import DB_DEFECTO
from engine.motor_a import MotorA, as_of_de
from engine import ubicacion

ISO = "%Y-%m-%dT%H:%M"


class Estado:
    def __init__(self, destino: str):
        self.destino = destino
        self.repo = crear_repositorio(destino)
        self.cfg = cargar_config()
        self.base = Base(self.repo)
        self.motor = MotorA(self.base, self.cfg)
        self.lock = threading.Lock()
        self._tablas_json: dict[bool, str] = {}
        self._registrar_modelo()

    @property
    def db(self) -> str:
        return self.repo.descripcion

    def _registrar_modelo(self):
        self.repo.registrar_modelo(self.motor.modelo_version, "bayesiano+costo_esperado", json.dumps({k: v for k, v in self.cfg.items() if not k.startswith("_")}),
                                   datetime.now().strftime(ISO), "equipo (pesos iniciales)")

    def recargar(self):
        self._tablas_json = {}
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


@asynccontextmanager
async def _arranque(_app):
    try:
        estado()                         # calienta la instantánea al arrancar: la primera persona no espera varios segundos
        datos_tablas(ligero=True); datos_tablas(ligero=False)
    except Exception:                    # si la base aún no existe, el primer pedido lo dirá con un error claro
        pass
    yield


app = FastAPI(title="Recomendador de proveedores · COSCO SHIPPING (datos sintéticos)", version="1.1", dependencies=[Depends(auth.exigir_sesion)], lifespan=_arranque)
app.include_router(auth.router)
app.add_middleware(GZipMiddleware, minimum_size=1024)      # /datos/tablas pesa ~3 MB sin comprimir
app.add_middleware(CORSMiddleware, allow_origins=[o for o in os.environ.get("COSCO_CORS_ORIGINS", "http://localhost:4200,http://127.0.0.1:4200").split(",") if o],
                   allow_methods=["GET", "POST", "PUT", "OPTIONS"], allow_headers=["Authorization", "Content-Type"], max_age=600)


@app.middleware("http")
async def _cabeceras(request, call_next):
    r = await call_next(request)
    r.headers.update({"X-Content-Type-Options": "nosniff", "X-Frame-Options": "DENY", "Referrer-Policy": "no-referrer", "Cache-Control": "no-store"})
    return r


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


def _validar(E: "Estado", sol: SolicitudIn) -> None:
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


def _recomendar(sol: SolicitudIn, fondo: BackgroundTasks, u: dict) -> RecomendacionOut:
    E = estado()
    _validar(E, sol)
    if E.repo.rechazo_de(sol.solicitud_id):
        raise HTTPException(409, f"la solicitud {sol.solicitud_id} fue devuelta al solicitante; crea una nueva")
    with E.lock:
        E.base.refrescar_reservas()                  # incluye lo que otra persona acaba de decidir
        out = E.motor.recomendar(sol)
        as_of = as_of_de(sol)
        E.repo.guardar_recomendacion(sol, out, as_of.strftime(ISO))
    alm = auth.almacen()
    alm.registrar_autor(sol.solicitud_id, u["usuario"], datetime.now().strftime("%Y-%m-%dT%H:%M:%S"))
    fondo.add_task(notificaciones.notificar, alm, sol, out, u["usuario"])      # aviso por Slack en segundo plano
    return out


@app.post("/recomendar", response_model=RecomendacionOut)
def recomendar(sol: SolicitudIn, fondo: BackgroundTasks, u: dict = Depends(auth.sesion)):
    return _recomendar(sol, fondo, u)


class NuevaSolicitudIn(BaseModel):
    """Lo que escribe quien pide el servicio. El identificador lo asigna el servidor."""
    cliente_id: str
    corredor_id: str
    tipo_vehiculo_req: str
    tipo_carga: Literal["general", "refrigerada", "peligrosa", "sobredimensionada"] = "general"
    peso_ton: float = Field(gt=0)
    fecha_cargue: datetime
    plazo_entrega: datetime
    nivel_servicio: Nivel = Nivel.ESTANDAR
    tarifa_cliente: int = Field(gt=0)
    clave_envio: Optional[str] = Field(None, max_length=64, pattern=r"^[A-Za-z0-9_-]+$", description="Identifica este envío del formulario: si se repite (doble clic, reintento) no crea otra solicitud")


@app.post("/solicitudes", response_model=RecomendacionOut)
def nueva_solicitud(n: NuevaSolicitudIn, fondo: BackgroundTasks, u: dict = Depends(auth.sesion)):
    """Crea una solicitud nueva y devuelve su recomendación. Idempotente por `clave_envio`: repetir el mismo envío no duplica nada."""
    E = estado()
    if n.plazo_entrega <= n.fecha_cargue:
        raise HTTPException(422, "el plazo de entrega debe ser posterior al cargue")
    if (n.plazo_entrega - n.fecha_cargue).days > 30:
        raise HTTPException(422, "el plazo de entrega no puede superar 30 días desde el cargue")
    sid = "W" + datetime.now().strftime("%Y%m%d") + "-" + (n.clave_envio[:12].upper() if n.clave_envio else uuid.uuid4().hex[:8].upper())
    sol = SolicitudIn(solicitud_id=sid, mercancia_peligrosa=n.tipo_carga == "peligrosa", **n.model_dump(exclude={"clave_envio"}))
    prev = E.repo.solicitud(sid)
    if prev:        # mismo envío repetido: solo vale si los datos son idénticos; si no, la clave se está reutilizando
        mismo = (prev["cliente_id"], prev["corredor_id"], prev["tipo_vehiculo_req"], float(prev["peso_ton"]), int(prev["tarifa_cliente"])) == \
                (sol.cliente_id, sol.corredor_id, sol.tipo_vehiculo_req, sol.peso_ton, sol.tarifa_cliente)
        if not mismo:
            raise HTTPException(409, "esa clave de envío ya se usó con otros datos")
    return _recomendar(sol, fondo, u)


def _capacidad_vigente(E: "Estado", d: DecisionIn) -> None:
    """Vuelve a mirar la capacidad justo antes de asignar: si otra decisión acaba de comprometer la última unidad, se frena con un mensaje claro."""
    r = E.repo.recomendacion(d.solicitud_id, d.recomendacion_id)
    so = E.repo.solicitud(d.solicitud_id)
    if not r or not so:
        return                                          # el repositorio responde con su propio 404
    E.base.refrescar_reservas()
    as_of = RecomendacionOut.model_validate_json(r[1]).generado_en
    unid, f_cap = E.base.capacidad_en(d.proveedor_elegido, so["tipo_vehiculo_req"], as_of)
    if unid is not None and unid - E.base.reservadas(d.proveedor_elegido, so["tipo_vehiculo_req"], f_cap) <= 0:
        raise HTTPException(409, f"{d.proveedor_elegido} ya no tiene unidades {so['tipo_vehiculo_req']} libres: otra decisión acaba de comprometer la última. Recalcula la recomendación")


@app.post("/decision")
def decision(d: DecisionIn, u: dict = Depends(auth.exigir_rol("operador", "gerencia"))):
    d = d.model_copy(update={"usuario": u["usuario"]}) if auth.exigida() else d   # el autor sale de la sesión, no del cuerpo
    E = estado()
    if u["rol"] != "gerencia":                       # lo escalado a gerencia solo lo decide gerencia
        r = E.repo.recomendacion(d.solicitud_id, d.recomendacion_id)
        if r and RecomendacionOut.model_validate_json(r[1]).escalar_gerencia:
            raise HTTPException(403, "Este caso está escalado a gerencia: solo gerencia puede decidirlo")
    with E.lock:
        _capacidad_vigente(E, d)
        r = E.repo.registrar_decision(d, E.base.tarifa_vigente, proveedores_validos=E.base.nombres, ventana_flex_h=E.cfg.get("ventana_flex_h", 72))
        E._tablas_json = {}
        return r


@app.post("/cierre")
def cierre(ci: CierreServicioIn, _u: dict = Depends(auth.exigir_rol("operador", "gerencia"))):
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
def datos_tablas(ligero: bool = Query(False, description="solo tablas de referencia (sin servicios ni capacidad): llega en milisegundos")):
    """Tablas de referencia y servicios para que una interfaz arme su propia instantánea (sin acceso a la base)."""
    E = estado()
    if ligero not in E._tablas_json:     # armar las completas tarda segundos: se guardan hasta que cambien los datos
        if ligero:                       # nombres de la instantánea que el motor ya tiene en memoria: no toca la base
            b = E.base
            T = {"proveedor": b.proveedores, "corredor": b.corredores.reset_index(), "tipo_vehiculo": b.vehiculos.reset_index(), "cliente": b.clientes.reset_index()}
        else:
            T = E.repo.tablas_base()
        E._tablas_json[ligero] = "{" + ",".join(f'"{k}":{_json(v)}' for k, v in T.items()) + "}"
    return Response(E._tablas_json[ligero], media_type="application/json")


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
def pendientes(filtro: str = Query("revision", pattern="^(revision|gerencia)$"), u: dict = Depends(auth.exigir_rol("operador", "gerencia"))):
    if filtro == "gerencia" and u["rol"] != "gerencia":
        raise HTTPException(403, "Solo gerencia ve la lista de escalados")
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
def tablero_decisiones(_u: dict = Depends(auth.exigir_rol("operador", "gerencia"))):
    return Response(_json(estado().repo.decisiones_tablero()), media_type="application/json")


@app.get("/tableros/cierres")
def tablero_cierres(_u: dict = Depends(auth.exigir_rol("operador", "gerencia"))):
    return Response(_json(estado().repo.cierres_tablero()), media_type="application/json")


MOTIVOS_DEVOLUCION = ("datos_incompletos", "sin_viabilidad_comercial", "cliente_cancelo", "precio_fuera_de_rango", "otro")


class RechazoIn(BaseModel):
    solicitud_id: str
    motivo: Literal["datos_incompletos", "sin_viabilidad_comercial", "cliente_cancelo", "precio_fuera_de_rango", "otro"]
    nota: Optional[str] = Field(None, max_length=500)


@app.post("/rechazo")
def rechazo(r: RechazoIn, u: dict = Depends(auth.exigir_rol("operador", "gerencia"))):
    """Devuelve la solicitud al solicitante con un motivo: no se asigna a ningún proveedor. Lo escalado a gerencia solo lo devuelve gerencia."""
    E = estado()
    if r.motivo == "otro" and not (r.nota or "").strip():
        raise HTTPException(422, "con el motivo «otro» escribe una nota")
    if u["rol"] != "gerencia":
        rec = E.repo.recomendacion(r.solicitud_id)
        if rec and RecomendacionOut.model_validate_json(rec[1]).escalar_gerencia:
            raise HTTPException(403, "Este caso está escalado a gerencia: solo gerencia puede devolverlo")
    with E.lock:
        return E.repo.rechazar(r.solicitud_id, u["usuario"], r.motivo, r.nota, datetime.now().strftime("%Y-%m-%dT%H:%M:%S"))


@app.get("/rechazos/{sid}")
def rechazo_de(sid: str):
    return estado().repo.rechazo_de(sid)


# ---------- seguimiento en ruta (simulado; puerto engine.ubicacion.FuenteUbicacion) ----------
_FUENTE = ubicacion.crear_fuente(os.environ.get("COSCO_UBICACION", "simulador"))


def _dt(x: Optional[str]) -> Optional[datetime]:
    return datetime.fromisoformat(x) if x else None


@app.get("/seguimiento")
def seguimiento(u: dict = Depends(auth.sesion)):
    """Servicios en ruta con su recorrido. Operador y gerencia ven todos (en curso + repeticiones de la fase de prueba);
    el solicitante ve solo los servicios de sus solicitudes. Hoy las posiciones son SIMULADAS (campo `simulado`)."""
    filas = estado().repo.servicios_en_seguimiento()
    if u["rol"] not in ("operador", "gerencia"):
        mias = {a["solicitud_id"] for a in auth.almacen().solicitudes_de(u["usuario"])}
        filas = [f for f in filas if f["solicitud_id"] in mias]
    out = []
    for f in filas:
        if f["corredor_id"] not in ubicacion.RUTAS:
            continue
        p50 = f["transito_p50_h"] or f["distancia_km"] / 45
        s = ubicacion.ServicioEnRuta(
            servicio_id=f["servicio_id"], corredor_id=f["corredor_id"],
            salida=_dt(f["cargue_real"]) or _dt(f["fecha_cargue"]), llegada=_dt(f["entrega_real"]),
            transito_p50_h=p50, transito_p90_h=f["transito_p90_h"] or p50 * 1.4, p_tarde=f["p_tarde"] if f["p_tarde"] is not None else 0.2,
            entrega_planeada=_dt(f["entrega_planeada"]))
        tr = _FUENTE.traza(s)
        llegada = tr.puntos[-1].t
        out.append({
            "servicio_id": f["servicio_id"], "solicitud_id": f["solicitud_id"], "proveedor_id": f["proveedor_id"], "proveedor": f["proveedor"],
            "corredor_id": f["corredor_id"], "origen": f["origen"], "destino": f["destino"], "nivel_servicio": f["nivel_servicio"],
            "tipo": "en_curso" if f["estado"] == "EN_CURSO" else "repeticion", "simulado": tr.simulado, "fuente": tr.fuente,
            "salida": tr.puntos[0].t, "llegada": llegada, "entrega_planeada": f["entrega_planeada"],
            "a_tiempo": llegada <= f["entrega_planeada"],
            "paradas": [{"nombre": n, "lat": ubicacion.CIUDADES[n][0], "lon": ubicacion.CIUDADES[n][1]} for n in ubicacion.RUTAS[f["corredor_id"]]],
            "puntos": [{"t": p.t, "lat": p.lat, "lon": p.lon, "evento": p.evento} for p in tr.puntos],
        })
    return out


# ---------- seguimiento por rol y avisos ----------
@app.get("/mis-solicitudes")
def mis_solicitudes(u: dict = Depends(auth.sesion)):
    """El solicitante ve las suyas; operador y gerencia ven todas. Estado: decidida · devuelta · escalada · en_revision · lista (sin decidir y sin alerta)."""
    E = estado()
    out = []
    for a in auth.almacen().solicitudes_de(None if u["rol"] in ("operador", "gerencia") else u["usuario"]):
        sid = a["solicitud_id"]
        r, d, dev = E.repo.recomendacion(sid), E.repo.decision_de(sid), E.repo.rechazo_de(sid)
        rec = RecomendacionOut.model_validate_json(r[1]) if r else None
        estado_ = "decidida" if d else "devuelta" if dev else ("escalada" if rec and rec.escalar_gerencia else "en_revision" if rec and rec.requiere_revision else "lista")
        top = rec.ranking[0] if rec and rec.ranking else None
        out.append({"solicitud_id": sid, "solicitante": a["usuario"], "fecha": a["fecha"], "estado": estado_,
                    "proveedor_sugerido": top.nombre if top else None, "proveedor_elegido": d["proveedor_elegido"] if d else None,
                    "decidida_por": d["usuario"] if d else None, "motivos": rec.motivos_revision if rec else [],
                    "devuelta_por": dev["usuario"] if dev else None, "motivo_devolucion": dev["motivo"] if dev else None, "nota_devolucion": dev["nota"] if dev else None})
    return out


class AjustesIn(BaseModel):
    slack_activo: Optional[bool] = None
    avisar_revision: Optional[bool] = None
    avisar_escalamiento: Optional[bool] = None


@app.get("/notificaciones/ajustes")
def ajustes_avisos(_u: dict = Depends(auth.exigir_rol("operador", "gerencia"))):
    return {"ajustes": auth.almacen().ajustes(), "webhooks": notificaciones.configurados()}


@app.put("/notificaciones/ajustes")
def cambiar_ajustes(a: AjustesIn, _u: dict = Depends(auth.exigir_rol("gerencia"))):
    auth.almacen().poner_ajustes({k: v for k, v in a.model_dump().items() if v is not None})
    return {"ajustes": auth.almacen().ajustes(), "webhooks": notificaciones.configurados()}


@app.get("/notificaciones/historial")
def historial_avisos(limite: int = Query(50, ge=1, le=200), _u: dict = Depends(auth.exigir_rol("operador", "gerencia"))):
    return auth.almacen().notificaciones(limite)


@app.post("/notificaciones/probar")
def probar_avisos(_u: dict = Depends(auth.exigir_rol("gerencia"))):
    return notificaciones.probar(auth.almacen())
