"""Implementación SQLite del puerto `Repositorio`. Es el ÚNICO módulo de la aplicación que habla SQL (junto con seed/ y los scripts de carga)."""
from __future__ import annotations

import logging
import sqlite3
import uuid
from datetime import timedelta
from pathlib import Path
from typing import Any, Optional

import pandas as pd

from engine.repositorio import ErrorNegocio, registrar_backend

ISO = "%Y-%m-%dT%H:%M"
COLS_ESTADISTICA = ["proveedor_id", "corredor_id", "tipo_carga", "alfa", "beta", "p_tarde", "ic90_ancho", "transito_p50_h", "transito_p90_h",
                    "n_servicios", "tasa_incidente", "indice_dureza", "actualizado", "nivel_respaldo"]


class RepositorioSQLite:
    def __init__(self, destino: str | Path):
        d = str(destino)
        self.ruta = d.split("://", 1)[1] if d.startswith("sqlite://") else d
        self.descripcion = f"sqlite:{self.ruta}"
        self._migrar()

    # ---------- infraestructura ----------
    def _con(self) -> sqlite3.Connection:
        c = sqlite3.connect(self.ruta)
        c.execute("PRAGMA foreign_keys = ON")
        return c

    def _migrar(self) -> None:
        """Acepta bases creadas con esquemas anteriores: estado EN_CURSO y columna nivel_respaldo."""
        con = sqlite3.connect(self.ruta)
        fila = con.execute("SELECT sql FROM sqlite_master WHERE name='servicio'").fetchone()
        if fila and "EN_CURSO" not in fila[0]:
            con.execute("PRAGMA foreign_keys=OFF")
            nuevo = fila[0].replace("'RECHAZADO')", "'RECHAZADO','EN_CURSO')").replace("CREATE TABLE servicio", "CREATE TABLE servicio_nuevo", 1)
            con.executescript(f"""BEGIN; {nuevo}; INSERT INTO servicio_nuevo SELECT * FROM servicio; DROP TABLE servicio;
                                  ALTER TABLE servicio_nuevo RENAME TO servicio;
                                  CREATE INDEX IF NOT EXISTS ix_serv_prov ON servicio (proveedor_id, entrega_real); COMMIT;""")
        cols = [r[1] for r in con.execute("PRAGMA table_info(estadistica_proveedor)")]
        if cols and "nivel_respaldo" not in cols:
            con.execute("ALTER TABLE estadistica_proveedor ADD COLUMN nivel_respaldo TEXT")
        con.commit(); con.close()

    def _df(self, sql: str, params: tuple = ()) -> pd.DataFrame:
        con = self._con()
        try:
            return pd.read_sql(sql, con, params=params)
        finally:
            con.close()

    # ---------- lectura masiva ----------
    def tablas_base(self) -> dict[str, pd.DataFrame]:
        q = self._df
        return {
            "proveedor": q("SELECT * FROM proveedor ORDER BY proveedor_id"),
            "corredor": q("SELECT * FROM corredor ORDER BY corredor_id"),
            "tipo_vehiculo": q("SELECT * FROM tipo_vehiculo"),
            "certificacion": q("SELECT * FROM certificacion"),
            "flota": q("SELECT * FROM flota"),
            "cliente": q("SELECT * FROM cliente"),
            "tarifa": q("SELECT * FROM tarifa"),
            "capacidad_snapshot": q("SELECT * FROM capacidad_snapshot"),
            "servicios": q("""SELECT s.servicio_id, s.solicitud_id, s.proveedor_id, s.precio_pactado, s.cargue_real, s.entrega_planeada,
                                     s.entrega_real, s.a_tiempo, s.costo_final, s.estado, so.corredor_id, so.tipo_carga, so.nivel_servicio,
                                     so.fecha_cargue, so.fecha_solicitud, so.plazo_entrega, so.tipo_vehiculo_req,
                                     EXISTS (SELECT 1 FROM evento_servicio e WHERE e.servicio_id=s.servicio_id AND e.tipo IN ('INCIDENTE','DANO')) AS incidente
                              FROM servicio s JOIN solicitud so USING(solicitud_id)"""),
        }

    # ---------- consultas puntuales ----------
    def conteos(self) -> dict[str, int]:
        con = self._con()
        try:
            return {t: con.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
                    for t in ("proveedor", "solicitud", "servicio", "recomendacion", "decision", "estadistica_proveedor")}
        finally:
            con.close()

    def solicitud(self, solicitud_id: str) -> Optional[dict]:
        con = self._con(); con.row_factory = sqlite3.Row
        try:
            r = con.execute("SELECT * FROM solicitud WHERE solicitud_id=?", (solicitud_id,)).fetchone()
            return dict(r) if r else None
        finally:
            con.close()

    def solicitudes_prueba(self) -> list[dict]:
        return self._df("SELECT * FROM solicitud WHERE fase='prueba' ORDER BY solicitud_id").to_dict("records")

    def recomendacion(self, solicitud_id: str, recomendacion_id: Optional[str] = None) -> Optional[tuple[str, str]]:
        con = self._con()
        try:
            if recomendacion_id:
                r = con.execute("SELECT recomendacion_id, top3_y_desglose FROM recomendacion WHERE recomendacion_id=? AND solicitud_id=?",
                                (recomendacion_id, solicitud_id)).fetchone()
            else:
                r = con.execute("SELECT recomendacion_id, top3_y_desglose FROM recomendacion WHERE solicitud_id=? ORDER BY fecha DESC LIMIT 1",
                                (solicitud_id,)).fetchone()
            return (r[0], r[1]) if r else None
        finally:
            con.close()

    def decision_de(self, solicitud_id: str) -> Optional[dict]:
        con = self._con(); con.row_factory = sqlite3.Row
        try:
            r = con.execute("SELECT proveedor_elegido, acepto_recomendacion, motivo, usuario FROM decision WHERE solicitud_id=? AND recomendacion_id IS NOT NULL",
                            (solicitud_id,)).fetchone()
            return dict(r) if r else None
        finally:
            con.close()

    def recomendaciones_sin_decision(self, limite: int = 200) -> list[str]:
        con = self._con()
        try:
            return [j for (j,) in con.execute("""SELECT r.top3_y_desglose FROM recomendacion r WHERE NOT EXISTS
                       (SELECT 1 FROM decision d WHERE d.solicitud_id=r.solicitud_id AND d.recomendacion_id IS NOT NULL)
                       ORDER BY r.fecha DESC LIMIT ?""", (limite,))]
        finally:
            con.close()

    def decisiones_tablero(self) -> pd.DataFrame:
        return self._df("SELECT d.*, r.top3_y_desglose FROM decision d JOIN recomendacion r USING(recomendacion_id)")

    def cierres_tablero(self) -> pd.DataFrame:
        return self._df("""SELECT d.solicitud_id, d.proveedor_elegido, s.costo_final, s.a_tiempo, r.top3_y_desglose, so.nivel_servicio FROM decision d
                           JOIN recomendacion r USING(recomendacion_id) JOIN servicio s ON s.solicitud_id=d.solicitud_id AND s.proveedor_id=d.proveedor_elegido
                           JOIN solicitud so ON so.solicitud_id=d.solicitud_id WHERE s.estado='ENTREGADO'""")

    # ---------- escritura ----------
    def registrar_modelo(self, version, descripcion, params_json, fecha, aprobado_por, reemplazar=False) -> None:
        con = self._con()
        con.execute(f"INSERT OR {'REPLACE' if reemplazar else 'IGNORE'} INTO modelo_version VALUES (?,?,?,?,?)",
                    (version, descripcion, params_json, fecha, aprobado_por))
        con.commit(); con.close()

    def guardar_recomendacion(self, sol: Any, rec: Any, as_of_iso: str) -> None:
        con = self._con()
        with con:
            if not con.execute("SELECT 1 FROM solicitud WHERE solicitud_id=?", (sol.solicitud_id,)).fetchone():
                con.execute("INSERT INTO solicitud VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
                            (sol.solicitud_id, sol.cliente_id, sol.corredor_id, sol.tipo_vehiculo_req, sol.tipo_carga, sol.peso_ton, int(sol.mercancia_peligrosa),
                             as_of_iso, pd.Timestamp(sol.fecha_cargue).strftime(ISO), pd.Timestamp(sol.plazo_entrega).strftime(ISO),
                             sol.nivel_servicio.value, sol.tarifa_cliente, "vivo"))
            con.execute("INSERT OR REPLACE INTO recomendacion VALUES (?,?,?,?,?,?,?)",
                        (rec.recomendacion_id, sol.solicitud_id, rec.modelo_version, rec.model_dump_json(), rec.confianza, int(rec.requiere_revision), as_of_iso))
        con.close()

    def registrar_decision(self, d: Any, precio_de: Any, proveedores_validos: Any = None, ventana_flex_h: float = 72) -> dict:
        from contratos.contracts import RecomendacionOut
        con = self._con()
        try:
            with con:
                so = con.execute("SELECT fecha_cargue, plazo_entrega, nivel_servicio, corredor_id, tipo_vehiculo_req FROM solicitud WHERE solicitud_id=?", (d.solicitud_id,)).fetchone()
                if not so:
                    raise ErrorNegocio(404, f"solicitud {d.solicitud_id} no existe: llama primero a /recomendar")
                r = self.recomendacion(d.solicitud_id, d.recomendacion_id)
                if not r:
                    raise ErrorNegocio(404, "no hay recomendación para esa solicitud")
                rec = RecomendacionOut.model_validate_json(r[1])
                if proveedores_validos is not None and d.proveedor_elegido not in proveedores_validos:
                    raise ErrorNegocio(422, f"proveedor desconocido: {d.proveedor_elegido}")
                desc = {x.proveedor_id: x for x in rec.descartados}
                if d.proveedor_elegido in desc:
                    x = desc[d.proveedor_elegido]
                    raise ErrorNegocio(422, f"{d.proveedor_elegido} fue descartado por regla dura ({x.motivo}: {x.detalle}); no se puede asignar")
                top1 = rec.ranking[0].proveedor_id if rec.ranking else None
                acepto = d.proveedor_elegido == top1
                if not acepto and d.motivo is None:
                    raise ErrorNegocio(422, "motivo obligatorio cuando no se elige el #1 (precio, relacion, capacidad, experiencia_previa, cliente_pidio, otro)")
                fc, plazo, nivel, cor, veh = so
                precio = precio_de(d.proveedor_elegido, cor, veh, fc)
                if precio is None:
                    raise ErrorNegocio(422, f"{d.proveedor_elegido} no tiene tarifa vigente para {veh} en {cor}")
                did = "D-" + uuid.uuid4().hex[:10]
                con.execute("INSERT INTO decision VALUES (?,?,?,?,?,?,?,?)",
                            (did, d.solicitud_id, r[0], d.proveedor_elegido, d.usuario, int(acepto), d.motivo, pd.Timestamp(rec.generado_en).strftime(ISO)))
                plan = pd.Timestamp(plazo) - (timedelta(hours=ventana_flex_h) if nivel == "Flexible" else timedelta(0))
                sid = "SV-" + uuid.uuid4().hex[:10]
                con.execute("INSERT INTO servicio (servicio_id, solicitud_id, proveedor_id, precio_pactado, entrega_planeada, estado) VALUES (?,?,?,?,?, 'EN_CURSO')",
                            (sid, d.solicitud_id, d.proveedor_elegido, precio, plan.strftime(ISO)))
            return {"decision_id": did, "servicio_id": sid, "acepto_recomendacion": acepto, "top1": top1, "precio_pactado": precio, "entrega_planeada": plan.strftime(ISO)}
        finally:
            con.close()

    def cerrar_servicio(self, ci: Any) -> dict:
        con = self._con()
        try:
            with con:
                r = con.execute("""SELECT s.estado, s.precio_pactado, so.fecha_cargue, s.entrega_planeada FROM servicio s JOIN solicitud so USING(solicitud_id)
                                   WHERE servicio_id=?""", (ci.servicio_id,)).fetchone()
                if not r:
                    raise ErrorNegocio(404, f"servicio {ci.servicio_id} no existe")
                est_s, precio, fc, plan = r
                if est_s != "EN_CURSO":
                    raise ErrorNegocio(409, f"el servicio ya está cerrado ({est_s})")
                ent = pd.Timestamp(ci.entrega_real)
                if ent <= pd.Timestamp(fc):
                    raise ErrorNegocio(422, "la entrega real debe ser posterior al cargue")
                if ci.costo_final < precio:
                    raise ErrorNegocio(422, f"costo_final ({ci.costo_final}) menor que el precio pactado ({precio})")
                con.execute("""UPDATE servicio SET cargue_real=COALESCE(cargue_real, ?), entrega_real=?, a_tiempo=?, costo_final=?, dias_detencion=?, estado='ENTREGADO'
                               WHERE servicio_id=?""", (fc, ent.strftime(ISO), int(ci.a_tiempo), ci.costo_final, ci.dias_detencion, ci.servicio_id))
                if ci.hubo_incidente:
                    con.execute("INSERT INTO evento_servicio (servicio_id, tipo, fecha_hora, detalle) VALUES (?,?,?,?)",
                                (ci.servicio_id, "INCIDENTE", (pd.Timestamp(fc) + (ent - pd.Timestamp(fc)) / 2).strftime(ISO), "reportado al cierre"))
                if ci.feedback_puntaje:
                    con.execute("INSERT INTO feedback VALUES (?,?,?,?)", (ci.servicio_id, "operador", ci.feedback_puntaje, ci.feedback_causa))
            return {"coherente": ent <= pd.Timestamp(plan), "entrega_real": ent}
        finally:
            con.close()

    # ---------- estadística persistida ----------
    def reemplazar_estadisticas(self, df: pd.DataFrame) -> None:
        import numpy as np
        con = self._con()
        with con:
            con.execute("DELETE FROM estadistica_proveedor")
            con.executemany(f"INSERT INTO estadistica_proveedor ({','.join(COLS_ESTADISTICA)}) VALUES ({','.join('?' * len(COLS_ESTADISTICA))})",
                            [tuple(None if (isinstance(v, float) and np.isnan(v)) else v for v in r) for r in df[COLS_ESTADISTICA].itertuples(index=False)])
        con.close()

    def contar_estadisticas(self) -> int:
        con = self._con()
        try:
            return con.execute("SELECT COUNT(*) FROM estadistica_proveedor").fetchone()[0]
        finally:
            con.close()

    def estadistica(self, proveedor_id: str, corredor_id: str, tipo_carga: str) -> Optional[dict]:
        con = self._con(); con.row_factory = sqlite3.Row
        try:
            r = con.execute("SELECT alfa, beta, n_servicios, tasa_incidente, actualizado FROM estadistica_proveedor WHERE proveedor_id=? AND corredor_id=? AND tipo_carga=?",
                            (proveedor_id, corredor_id, tipo_carga)).fetchone()
            return dict(r) if r else None
        finally:
            con.close()

    def guardar_estadistica(self, f: dict) -> None:
        con = self._con()
        with con:
            con.execute("""INSERT INTO estadistica_proveedor (proveedor_id, corredor_id, tipo_carga, alfa, beta, p_tarde, ic90_ancho, n_servicios, tasa_incidente, actualizado, nivel_respaldo)
                           VALUES (:proveedor_id,:corredor_id,:tipo_carga,:alfa,:beta,:p_tarde,:ic90_ancho,:n_servicios,:tasa_incidente,:actualizado,'corredor')
                           ON CONFLICT(proveedor_id, corredor_id, tipo_carga) DO UPDATE SET alfa=excluded.alfa, beta=excluded.beta, p_tarde=excluded.p_tarde,
                           ic90_ancho=excluded.ic90_ancho, n_servicios=excluded.n_servicios, tasa_incidente=excluded.tasa_incidente,
                           actualizado=excluded.actualizado, nivel_respaldo='corredor'""", f)
        con.close()

    def contexto_servicio(self, servicio_id: str) -> Optional[tuple[str, str, str]]:
        con = self._con()
        try:
            r = con.execute("SELECT s.proveedor_id, so.corredor_id, so.tipo_carga FROM servicio s JOIN solicitud so USING(solicitud_id) WHERE s.servicio_id=?",
                            (servicio_id,)).fetchone()
            return tuple(r) if r else None
        finally:
            con.close()


registrar_backend("sqlite", RepositorioSQLite)


# ---------- usuarios de la API (almacén propio, separado de los datos del negocio) ----------
ROLES = ("solicitante", "operador", "gerencia")
AJUSTES_DEFECTO = {"slack_activo": "1", "avisar_revision": "1", "avisar_escalamiento": "1"}
USUARIOS_DEMO = (("operador", "Operación (demostración)", "operador"), ("comercial", "Comercial (demostración)", "solicitante"))


class UsuariosSQLite:
    """Usuarios, ajustes de avisos, historial de notificaciones y autor de cada solicitud, en su propio SQLite (aparte del negocio)."""

    def __init__(self, ruta: str, hash_semilla, usuario_semilla: str, demo_roles: bool = True):
        self.ruta = ruta
        Path(ruta).parent.mkdir(parents=True, exist_ok=True)
        con = sqlite3.connect(ruta)
        con.execute("""CREATE TABLE IF NOT EXISTS usuario (usuario TEXT PRIMARY KEY, nombre TEXT NOT NULL, rol TEXT NOT NULL,
                       clave_hash TEXT NOT NULL, activo INTEGER NOT NULL DEFAULT 1)""")
        con.execute("CREATE TABLE IF NOT EXISTS ajuste (clave TEXT PRIMARY KEY, valor TEXT NOT NULL)")
        con.execute("""CREATE TABLE IF NOT EXISTS notificacion (id INTEGER PRIMARY KEY AUTOINCREMENT, fecha TEXT NOT NULL, evento TEXT NOT NULL,
                       solicitud_id TEXT, destino TEXT NOT NULL, estado TEXT NOT NULL, detalle TEXT)""")
        con.execute("CREATE TABLE IF NOT EXISTS solicitud_autor (solicitud_id TEXT PRIMARY KEY, usuario TEXT NOT NULL, fecha TEXT NOT NULL)")
        if con.execute("SELECT count(*) FROM usuario").fetchone()[0] == 0:
            con.execute("INSERT INTO usuario VALUES (?,?,?,?,1)", (usuario_semilla, "Jurado Sabana Hack", "gerencia", hash_semilla()))
            logging.getLogger("cosco.auth").warning("Usuario semilla de demostración creado: %s", usuario_semilla)
        if demo_roles:      # un usuario por rol para poder probar el flujo completo (se crean una sola vez, aunque la base ya existiera)
            h = hash_semilla()
            for u, nombre, rol in USUARIOS_DEMO:
                if not con.execute("SELECT 1 FROM usuario WHERE usuario=?", (u,)).fetchone():
                    con.execute("INSERT INTO usuario VALUES (?,?,?,?,1)", (u, nombre, rol, h))
        con.commit(); con.close()

    def _con(self):
        con = sqlite3.connect(self.ruta); con.row_factory = sqlite3.Row
        return con

    def obtener(self, usuario: str) -> Optional[dict]:
        con = self._con()
        try:
            r = con.execute("SELECT * FROM usuario WHERE usuario=? AND activo=1", (usuario,)).fetchone()
            return dict(r) if r else None
        finally:
            con.close()

    # ---- ajustes de avisos ----
    def ajustes(self) -> dict:
        con = self._con()
        try:
            a = dict(AJUSTES_DEFECTO)
            a.update({r["clave"]: r["valor"] for r in con.execute("SELECT clave, valor FROM ajuste")})
            return {k: v == "1" for k, v in a.items()}
        finally:
            con.close()

    def poner_ajustes(self, cambios: dict) -> None:
        con = self._con()
        try:
            for k, v in cambios.items():
                if k in AJUSTES_DEFECTO:
                    con.execute("INSERT INTO ajuste VALUES (?,?) ON CONFLICT(clave) DO UPDATE SET valor=excluded.valor", (k, "1" if v else "0"))
            con.commit()
        finally:
            con.close()

    # ---- historial de notificaciones ----
    def registrar_notificacion(self, fecha: str, evento: str, solicitud_id: Optional[str], destino: str, estado: str, detalle: str = "") -> None:
        con = self._con()
        try:
            con.execute("INSERT INTO notificacion (fecha, evento, solicitud_id, destino, estado, detalle) VALUES (?,?,?,?,?,?)",
                        (fecha, evento, solicitud_id, destino, estado, detalle[:300]))
            con.commit()
        finally:
            con.close()

    def ya_notificada(self, solicitud_id: str, evento: str) -> bool:
        con = self._con()
        try:
            return con.execute("SELECT 1 FROM notificacion WHERE solicitud_id=? AND evento=? AND estado IN ('enviada','pendiente') LIMIT 1", (solicitud_id, evento)).fetchone() is not None
        finally:
            con.close()

    def notificaciones(self, limite: int = 50) -> list[dict]:
        con = self._con()
        try:
            return [dict(r) for r in con.execute("SELECT * FROM notificacion ORDER BY id DESC LIMIT ?", (limite,))]
        finally:
            con.close()

    # ---- quién creó cada solicitud ----
    def registrar_autor(self, solicitud_id: str, usuario: str, fecha: str) -> None:
        con = self._con()
        try:
            con.execute("INSERT OR IGNORE INTO solicitud_autor VALUES (?,?,?)", (solicitud_id, usuario, fecha))
            con.commit()
        finally:
            con.close()

    def solicitudes_de(self, usuario: Optional[str], limite: int = 100) -> list[dict]:
        con = self._con()
        try:
            if usuario:
                q = con.execute("SELECT * FROM solicitud_autor WHERE usuario=? ORDER BY fecha DESC LIMIT ?", (usuario, limite))
            else:
                q = con.execute("SELECT * FROM solicitud_autor ORDER BY fecha DESC LIMIT ?", (limite,))
            return [dict(r) for r in q]
        finally:
            con.close()
