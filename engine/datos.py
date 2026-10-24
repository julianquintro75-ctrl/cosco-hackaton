"""Acceso a datos: carga una sola vez las tablas que usa el motor y las deja en memoria (pandas/numpy).
Nunca lee data/verdad_oculta.csv. Se invalida con Base.invalidar() cuando entra un cierre nuevo."""
from __future__ import annotations
import json
from functools import lru_cache
from pathlib import Path
import numpy as np
import pandas as pd

from engine.repositorio import DB_DEFECTO, RAIZ, Repositorio, crear_repositorio  # noqa: F401  (se reexportan)

CONFIG_DEFECTO = Path(__file__).resolve().parent / "config_motor.json"


def cargar_config(ruta: str | Path | None = None, **sobrescribir) -> dict:
    cfg = json.loads(Path(ruta or CONFIG_DEFECTO).read_text(encoding="utf8"))
    cfg.update(sobrescribir)
    return cfg


class Base:
    """Instantanea en memoria de la base. Todas las consultas con as_of se resuelven filtrando aqui (sin ver el futuro).
    Se alimenta de un `Repositorio` (SQLite por omision), de modo que no depende del motor de base de datos."""

    def __init__(self, db: str | Path | Repositorio | None = None, tablas: dict[str, pd.DataFrame] | None = None):
        """`db`: ruta/URL (se resuelve con crear_repositorio) o un Repositorio ya creado. `tablas`: alternativa sin repositorio
        (p. ej. las que entrega la API por HTTP a la interfaz)."""
        self.repo = None if tablas is not None else (db if isinstance(db, Repositorio) else crear_repositorio(db))
        self._tablas_dadas = tablas
        self.db = self.repo.descripcion if self.repo else "remoto"
        self.cargar()

    def cargar(self):
        T = self._tablas_dadas if self._tablas_dadas is not None else self.repo.tablas_base()
        self.proveedores = T["proveedor"].sort_values("proveedor_id").reset_index(drop=True)
        self.nombres = dict(zip(self.proveedores.proveedor_id, self.proveedores.nombre))
        self.corredores = T["corredor"].sort_values("corredor_id").set_index("corredor_id")
        self.vehiculos = T["tipo_vehiculo"].set_index("tipo_vehiculo_id")
        self.certs = T["certificacion"]
        self.flota = T["flota"]
        self.clientes = T["cliente"].set_index("cliente_id")
        t = T["tarifa"].copy()
        t["desde"] = pd.to_datetime(t.vigente_desde); t["hasta"] = pd.to_datetime(t.vigente_hasta)
        self.tarifas = t
        c = T["capacidad_snapshot"].copy()
        c["fh"] = pd.to_datetime(c.fecha_hora)
        self.capacidad = c.sort_values("fh")
        s = T["servicios"].copy()
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
        self.cancelados = s[s.estado.isin(["CANCELADO", "RECHAZADO"])].copy()
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
        self.refrescar_reservas()

    # ---------- capacidad ya comprometida ----------
    def refrescar_reservas(self):
        """Lee los servicios en curso (decisiones tomadas): son unidades que el último reporte de capacidad aún no refleja.
        Es una consulta liviana; la API la repite antes de recomendar y de decidir, así dos solicitudes simultáneas no se disputan la misma unidad."""
        res: dict[tuple[str, str], list] = {}
        if self.repo is not None:
            for pid, veh, fecha in self.repo.reservas_en_curso():
                res.setdefault((pid, veh), []).append(pd.Timestamp(fecha))
        self._reservas = res

    def reservadas(self, pid: str, vehiculo: str, desde) -> int:
        """Unidades comprometidas por decisiones posteriores al reporte de capacidad (`desde`)."""
        if desde is None:
            return 0
        d = pd.Timestamp(desde)
        return sum(1 for t in self._reservas.get((pid, vehiculo), ()) if t >= d)

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
