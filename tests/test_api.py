"""Paso 7 · API: flujo completo y errores claros."""
import os
from datetime import datetime, timedelta
import pytest
from fastapi.testclient import TestClient


@pytest.fixture(scope="module")
def cli(db_copia):
    os.environ["COSCO_DB"] = str(db_copia)
    from app.api import app
    return TestClient(app)


def _sol(sid, nivel="Estandar", **kw):
    fc = datetime(2026, 10, 17, 8)
    d = dict(solicitud_id=sid, cliente_id="K002", corredor_id="C4", tipo_vehiculo_req="V40", tipo_carga="general", peso_ton=20,
             fecha_cargue=fc.isoformat(), plazo_entrega=(fc + timedelta(hours=37)).isoformat(), nivel_servicio=nivel,
             tarifa_cliente=7_500_000, as_of="2026-10-16T09:00")
    d.update(kw); return d


def test_salud(cli):
    r = cli.get("/salud"); assert r.status_code == 200 and r.json()["estado"] == "ok"


def test_flujo_completo(cli, db_copia):
    import sqlite3
    rec = cli.post("/recomendar", json=_sol("API-1")).json()
    top = rec["ranking"]; assert top
    r = cli.post("/decision", json=dict(recomendacion_id=rec["recomendacion_id"], solicitud_id="API-1", proveedor_elegido=top[1]["proveedor_id"], usuario="t"))
    assert r.status_code == 422 and "motivo obligatorio" in r.json()["detail"]
    d = cli.post("/decision", json=dict(recomendacion_id=rec["recomendacion_id"], solicitud_id="API-1", proveedor_elegido=top[1]["proveedor_id"], usuario="t", motivo="relacion")).json()
    assert d["acepto_recomendacion"] is False
    ent = (datetime.fromisoformat(d["entrega_planeada"]) + timedelta(hours=5)).isoformat()
    c = cli.post("/cierre", json=dict(servicio_id=d["servicio_id"], entrega_real=ent, a_tiempo=False, costo_final=d["precio_pactado"] + 450000, dias_detencion=1, feedback_puntaje=1, feedback_causa="proveedor"))
    assert c.status_code == 200 and c.json()["aviso"] is None
    assert cli.post("/cierre", json=dict(servicio_id=d["servicio_id"], entrega_real=ent, a_tiempo=False, costo_final=d["precio_pactado"])).status_code == 409
    con = sqlite3.connect(db_copia)
    assert con.execute("SELECT COUNT(*) FROM recomendacion WHERE solicitud_id='API-1'").fetchone()[0] == 1
    assert con.execute("SELECT acepto_recomendacion, motivo FROM decision WHERE solicitud_id='API-1'").fetchone() == (0, "relacion")
    assert con.execute("SELECT estado, a_tiempo FROM servicio WHERE servicio_id=?", (d["servicio_id"],)).fetchone() == ("ENTREGADO", 0)
    assert con.execute("SELECT COUNT(*) FROM feedback WHERE servicio_id=?", (d["servicio_id"],)).fetchone()[0] == 1


def test_no_se_asigna_un_descartado(cli):
    rec = cli.post("/recomendar", json=_sol("API-2", carga="peligrosa", mercancia_peligrosa=True)).json()
    desc = rec["descartados"][0]["proveedor_id"]
    r = cli.post("/decision", json=dict(solicitud_id="API-2", proveedor_elegido=desc, usuario="t", motivo="otro"))
    assert r.status_code == 422 and "regla dura" in r.json()["detail"]


def test_errores_claros(cli):
    assert cli.post("/recomendar", json=_sol("API-3", corredor_id="C99")).status_code == 422
    assert cli.post("/recomendar", json=_sol("API-4", peso_ton=50)).status_code == 422
    assert cli.post("/recomendar", json=_sol("API-5", plazo_entrega="2026-10-16T00:00")).status_code == 422
    assert cli.get("/proveedores/P99/ficha").status_code == 404
    f = cli.get("/proveedores/P03/ficha", params={"as_of": "2026-09-30"}).json()
    assert any("C1" in x or "C2" in x for x in f["debilidades"])
