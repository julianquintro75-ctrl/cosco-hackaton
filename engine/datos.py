"""Acceso a la base SQLite: carga una sola vez las tablas que usa el motor y las deja en memoria (pandas/numpy).
Nunca lee data/verdad_oculta.csv. Se invalida con Base.invalidar() cuando entra un cierre nuevo."""
from __future__ import annotations
import json, sqlite3
from functools import lru_cache
from pathlib import Path
import numpy as np
import pandas as pd

RAIZ = Path(__file__).resolve().parent.parent
DB_DEFECTO = RAIZ / "data" / "cosco.db"
CONFIG_DEFECTO = Path(__file__).resolve().parent / "config_motor.json"


def cargar_config(ruta: str | Path | None = None, **sobrescribir) -> dict:
    cfg = json.loads(Path(ruta or CONFIG_DEFECTO).read_text(encoding="utf8"))
    cfg.update(sobrescribir)
    return cfg


class Base:
    """Instantanea en memoria de la base. Todas las consultas con as_of se resuelven filtrando aqui (sin ver el futuro)."""

    def __init__(self, db: str | Path | None = None):
        self.db = str(db or DB_DEFECTO)
        self.cargar()

    def conectar(self) -> sqlite3.Connection:
        con = sqlite3.connect(self.db)
        con.execute("PRAGMA foreign_keys = ON")
        return con

    def cargar(self):
        con = self.conectar()
        q = lambda s: pd.read_sql(s, con)
        self.proveedores = q("SELECT * FROM proveedor ORDER BY proveedor_id")
        self.nombres = dict(zip(self.proveedores.proveedor_id, self.proveedores.nombre))
        self.corredores = q("SELECT * FROM corredor ORDER BY corredor_id").set_index("corredor_id")
        self.vehiculos = q("SELECT * FROM tipo_vehiculo").set_index("tipo_vehiculo_id")
        self.certs = q("SELECT * FROM certificacion")
        self.flota = q("SELECT * FROM flota")
        self.clientes = q("SELECT * FROM cliente").set_index("cliente_id")
        t = q("SELECT * FROM tarifa")
        t["desde"] = pd.to_datetime(t.vigente_desde); t["hasta"] = pd.to_datetime(t.vigente_hasta)
        self.tarifas = t
        c = q("SELECT * FROM capacidad_snapshot")
        c["fh"] = pd.to_datetime(c.fecha_hora)
        self.capacidad = c.sort_values("fh")
        s = q("""SELECT s.servicio_id, s.solicitud_id, s.proveedor_id, s.precio_pactado, s.cargue_real, s.entrega_planeada,
                        s.entrega_real, s.a_tiempo, s.costo_final, s.estado, so.corredor_id, so.tipo_carga, so.nivel_servicio,
                        so.fecha_cargue, so.fecha_solicitud, so.plazo_entrega, so.tipo_vehiculo_req,
                        EXISTS (SELECT 1 FROM evento_servicio e WHERE e.servicio_id=s.servicio_id AND e.tipo IN ('INCIDENTE','DANO')) AS incidente
                 FROM servicio s JOIN solicitud so USING(solicitud_id)""")
        for col in ("entrega_real", "fecha_cargue", "entrega_planeada", "plazo_entrega", "fecha_solicitud"):
            s[col] = pd.to_datetime(s[col])
        s["transito_h"] = (s.entrega_real - s.fecha_cargue).dt.total_seconds() / 3600
        s["plan_h"] = (s.entrega_planeada - s.fecha_cargue).dt.total_seconds() / 3600
        self.servicios_todos = s
        e = s[(s.estado == "ENTREGADO") & s.entrega_real.notna() & s.a_tiempo.notna()].copy()
        e["a_tiempo"] = e.a_tiempo.astype(int)
        self.entregados = e.sort_values("entrega_real").reset_index(drop=True)
        # arreglos numpy para filtrar rapido por as_of
        self._t_ent = self.entregados.entrega_real.values.astype("datetime64[m]")
        self.cancelados = s[s.estado != "ENTREGADO"].copy()
        con.close()
        # indices en diccionarios para consultas rapidas
        self._tar = {}
        for r in t.sort_values("desde").itertuples():
            self._tar.setdefault((r.proveedor_id, r.corredor_id, r.tipo_vehiculo_id), []).append((r.desde, r.hasta, int(r.precio_cop)))
        self._cert = {}
        for r in self.certs.itertuples():
            self._cert.setdefault(r.proveedor_id, []).append((r.tipo, pd.Timestamp(r.vigente_hasta)))
        self._cap = {k: (g.fh.values.astype("datetime64[m]"), g.unidades_disponibles.values, g.fh.values)
                     for k, g in self.capacidad.groupby(["proveedor_id", "tipo_vehiculo_id"])}
        self.version_datos = (len(self.entregados), str(self.entregados.entrega_real.max()), len(self.servicios_todos))
        self._cache = {}

    def invalidar(self):
        self.cargar()

    # ---------- consultas con as_of ----------
    def entregados_hasta(self, as_of) -> pd.DataFrame:
        """Servicios entregados con entrega_real <= as_of (nunca el futuro)."""
        k = np.searchsorted(self._t_ent, np.datetime64(pd.Timestamp(as_of).to_datetime64(), "m"), side="right")
        return self.entregados.iloc[:k]

    def asignados_hasta(self, as_of) -> pd.DataFrame:
        """Servicios asignados (cualquier estado) con fecha de cargue <= as_of: para cuota y rechazos."""
        return self.servicios_todos[self.servicios_todos.fecha_cargue <= pd.Timestamp(as_of)]

    def certificaciones(self, pid: str, fecha) -> set[str]:
        f = pd.Timestamp(fecha).normalize()
        return {t for t, h in self._cert.get(pid, []) if h >= f}

    def tarifa_vigente(self, pid: str, corredor: str, vehiculo: str, fecha):
        f = pd.Timestamp(fecha).normalize()
        precio = None
        for d0, d1, pr in self._tar.get((pid, corredor, vehiculo), []):
            if d0 <= f and (pd.isna(d1) or d1 >= f):
                precio = pr          # la vigencia mas reciente que aplica
        return precio

    def capacidad_en(self, pid: str, vehiculo: str, as_of):
        """Ultimo snapshot de capacidad anterior o igual a as_of: (unidades, fecha) o (None, None)."""
        c = self._cap.get((pid, vehiculo))
        if c is None:
            return None, None
        k = int(np.searchsorted(c[0], np.datetime64(pd.Timestamp(as_of).to_datetime64(), "m"), side="right"))
        if k == 0:
            return None, None
        return int(c[1][k - 1]), pd.Timestamp(c[2][k - 1])


@lru_cache(maxsize=8)
def base_compartida(db: str | None = None) -> Base:
    return Base(db)
