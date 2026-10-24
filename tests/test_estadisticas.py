"""Paso 4 · pruebas de las estadisticas bayesianas con decaimiento."""
import sqlite3
import pandas as pd
from conftest import mini_db
from engine.datos import Base
from engine.estadisticas import Estadisticas, calcular, actualizar_con_servicio


def _tres_a_tiempo(tmp_path):
    s = [dict(cargue=f"2026-05-0{d}T08:00", plan=f"2026-05-0{d}T20:00", entrega=f"2026-05-0{d}T18:00", a_tiempo=1) for d in (1, 2, 3)]
    return Base(mini_db(tmp_path / "m.db", s))


def test_tres_de_tres_no_es_perfecto(tmp_path):
    e = Estadisticas(_tres_a_tiempo(tmp_path))
    r = e.combo("2026-05-10", "PX", "C1")
    assert r["n_servicios"] == 3
    assert r["p_tarde"] >= 0.10, "con 3 de 3 a tiempo el prior debe evitar una puntualidad de 100 %"
    assert r["ic90_ancho"] > 0.15, "con poca evidencia el intervalo debe ser ancho"


def test_as_of_no_ve_el_futuro(tmp_path):
    e = Estadisticas(_tres_a_tiempo(tmp_path))
    r = e.combo("2026-05-02T19:00", "PX", "C1")      # solo la entrega del 1 y la del 2 (18:00) ya ocurrieron
    assert r["n_servicios"] == 2
    r0 = e.combo("2026-04-30", "PX", "C1")            # antes de todo: prior global
    assert r0["n_servicios"] == 0 and r0["nivel_respaldo"] == "global"
    assert abs(r0["p_tarde"] - 3 / 20) < 1e-9


def test_decaimiento_pesa_menos_lo_viejo(tmp_path):
    s = [dict(cargue="2026-01-01T08:00", plan="2026-01-01T20:00", entrega="2026-01-02T08:00", a_tiempo=0)]
    e = Estadisticas(Base(mini_db(tmp_path / "d.db", s)))
    reciente = e.combo("2026-01-03", "PX", "C1")["p_tarde"]
    viejo = e.combo("2026-06-01", "PX", "C1")["p_tarde"]
    assert reciente > viejo > 3 / 20


def test_calcular_llena_tabla_y_andina_baja(db_copia):
    b = Base(db_copia)
    df = calcular("2026-09-30", base=b)
    n = sqlite3.connect(db_copia).execute("SELECT COUNT(*) FROM estadistica_proveedor").fetchone()[0]
    assert n == len(df) > 50
    jul = Estadisticas(b).combo("2026-07-15", "P01", "C1")["indice_dureza"]
    sep = df[(df.proveedor_id == "P01") & (df.corredor_id == "C1") & (df.tipo_carga == "general")].indice_dureza.iloc[0]
    assert sep < jul, "Andina Cargo debe bajar de dureza en septiembre"


def test_actualizacion_incremental(db_copia):
    b = Base(db_copia)
    calcular("2026-09-30", base=b)
    sid, pid, cor = sqlite3.connect(db_copia).execute(
        "SELECT s.servicio_id, s.proveedor_id, so.corredor_id FROM servicio s JOIN solicitud so USING(solicitud_id) WHERE so.tipo_carga='general' AND estado='ENTREGADO' LIMIT 1").fetchone()
    antes = sqlite3.connect(db_copia).execute("SELECT p_tarde, n_servicios FROM estadistica_proveedor WHERE proveedor_id=? AND corredor_id=? AND tipo_carga='general'", (pid, cor)).fetchone()
    r = actualizar_con_servicio(dict(servicio_id=sid, entrega_real="2026-10-01T10:00", a_tiempo=False, hubo_incidente=False), base=b)
    assert r["n_servicios"] == antes[1] + 1 and r["p_tarde"] > antes[0]
