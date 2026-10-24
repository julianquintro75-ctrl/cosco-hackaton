"""Seguimiento en ruta: el simulador (adaptador de engine.ubicacion.FuenteUbicacion) y GET /seguimiento por rol."""
from datetime import datetime, timedelta

import pytest

from engine import ubicacion as U
from tests.test_concurrencia import cli, entrar, formulario  # noqa: F401  (fixture y ayudas compartidas)


def servicio(sid="SV-1", corredor="C1", llegada=None, p_tarde=0.0):
    salida = datetime(2026, 10, 30, 8, 0)
    return U.ServicioEnRuta(sid, corredor, salida, llegada, transito_p50_h=20, transito_p90_h=28, p_tarde=p_tarde,
                            entrega_planeada=salida + timedelta(hours=26))


@pytest.mark.parametrize("cor", sorted(U.RUTAS))
def test_cada_corredor_tiene_ruta_de_origen_a_destino(cor, db_copia):
    import sqlite3
    o, d = sqlite3.connect(db_copia).execute("SELECT origen, destino FROM corredor WHERE corredor_id=?", (cor,)).fetchone()
    n = U.RUTAS[cor]
    assert n[0] == o and n[-1] == d
    tr = U.SimuladorUbicacion().traza(servicio(corredor=cor))
    assert (tr.puntos[0].lat, tr.puntos[0].lon) == pytest.approx(U.CIUDADES[o], abs=1e-4)
    assert (tr.puntos[-1].lat, tr.puntos[-1].lon) == pytest.approx(U.CIUDADES[d], abs=1e-4)


def test_simulador_determinista_y_tiempo_creciente():
    a, b = U.SimuladorUbicacion().traza(servicio()), U.SimuladorUbicacion().traza(servicio())
    assert [(p.t, p.lat, p.lon) for p in a.puntos] == [(p.t, p.lat, p.lon) for p in b.puntos]
    ts = [p.t for p in a.puntos]
    assert ts == sorted(ts) and a.simulado and a.fuente == "simulador"


def test_sin_riesgo_llega_cerca_del_tipico_y_con_riesgo_se_detiene():
    sim = U.SimuladorUbicacion()
    ok = sim.traza(servicio(p_tarde=0.0))
    horas = (datetime.fromisoformat(ok.puntos[-1].t) - datetime.fromisoformat(ok.puntos[0].t)).total_seconds() / 3600
    assert 17 <= horas <= 23 and not any(p.evento == "parada" for p in ok.puntos)
    tarde = sim.traza(servicio(p_tarde=1.0))
    assert any(p.evento == "parada" for p in tarde.puntos)
    assert tarde.puntos[-1].t >= (datetime(2026, 10, 30, 8) + timedelta(hours=28)).strftime(U.ISO)


def test_servicio_entregado_respeta_la_hora_real():
    llegada = datetime(2026, 10, 31, 15, 7)
    tr = U.SimuladorUbicacion().traza(servicio(llegada=llegada))
    assert tr.puntos[-1].t == "2026-10-31T15:07" and any(p.evento == "parada" for p in tr.puntos)   # llegó tarde: hubo parada


def test_fuente_desconocida_falla_claro():
    with pytest.raises(ValueError, match="simulador"):
        U.crear_fuente("gps-inexistente")


def test_endpoint_por_rol(cli):  # noqa: F811
    hc, ho = entrar(cli, "comercial"), entrar(cli, "operador")
    base = cli.get("/seguimiento", headers=ho).json()
    rep = [s for s in base if s["tipo"] == "repeticion"]
    assert rep and all(s["simulado"] for s in base)                                          # repeticiones de la fase de prueba
    assert len({s["corredor_id"] for s in rep}) == len(rep)                                  # una por corredor
    assert cli.get("/seguimiento", headers=hc).json() == []                                 # el solicitante no ve servicios ajenos
    assert cli.get("/seguimiento").status_code == 401

    rec = cli.post("/solicitudes", json=formulario(), headers=hc).json()
    d = {"recomendacion_id": rec["recomendacion_id"], "solicitud_id": rec["solicitud_id"], "proveedor_elegido": rec["ranking"][0]["proveedor_id"], "usuario": "x"}
    assert cli.post("/decision", json=d, headers=ho).status_code == 200
    mio = cli.get("/seguimiento", headers=hc).json()
    assert [s["solicitud_id"] for s in mio] == [rec["solicitud_id"]] and mio[0]["tipo"] == "en_curso"
    s = mio[0]
    assert s["paradas"][0]["nombre"] == "Buenaventura" and s["paradas"][-1]["nombre"] == "Bogota"
    assert s["puntos"][0]["evento"] == "salida" and s["puntos"][-1]["evento"] == "llegada"
    assert isinstance(s["a_tiempo"], bool)
    assert rec["solicitud_id"] in {x["solicitud_id"] for x in cli.get("/seguimiento", headers=ho).json() if x["tipo"] == "en_curso"}
