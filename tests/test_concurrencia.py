"""Solicitud nueva, devolución al solicitante y casos borde con pedidos simultáneos.
Los hilos usan un cliente HTTP cada uno y una barrera para que los pedidos arranquen a la vez."""
import shutil
import sqlite3
import threading
from datetime import datetime, timedelta

import pytest
from fastapi.testclient import TestClient

from app import api, auth, notificaciones
from engine.repositorio import ErrorNegocio, crear_repositorio

HOOK = "https://hooks.slack.com/services/T000/B000/xxxx"


@pytest.fixture()
def cli(monkeypatch, tmp_path, db_copia):
    db = tmp_path / "cosco.db"
    shutil.copy(db_copia, db)
    monkeypatch.setenv("COSCO_AUTH_REQUIRED", "1")
    monkeypatch.setenv("COSCO_AUTH_DB", str(tmp_path / "auth.db"))
    monkeypatch.setenv("COSCO_JWT_SECRET", "x" * 40)
    monkeypatch.setenv("COSCO_DB", str(db))
    monkeypatch.delenv("COSCO_REPO", raising=False)
    monkeypatch.delenv("COSCO_SLACK_WEBHOOK", raising=False)
    monkeypatch.setenv("COSCO_SLACK_WEBHOOK_OPERACIONES", HOOK + "ops")
    monkeypatch.setenv("COSCO_SLACK_WEBHOOK_GERENCIA", HOOK + "ger")
    envios, cierre = [], threading.Lock()

    def falso(url, cuerpo):
        with cierre:
            envios.append((url, cuerpo))
        return 200, "ok"
    monkeypatch.setattr(notificaciones, "_post", falso)
    auth._FALLOS.clear()
    c = TestClient(api.app)
    c.envios, c.db = envios, db
    return c


def entrar(c, usuario):
    r = c.post("/auth/login", json={"usuario": usuario, "clave": auth.SEMILLA_CLAVE})
    assert r.status_code == 200, r.text
    return {"Authorization": "Bearer " + r.json()["access_token"]}


def formulario(dias=6, **extra):
    cargue = (datetime.now() + timedelta(days=dias)).replace(hour=8, minute=0, second=0, microsecond=0)
    f = {"cliente_id": "K001", "corredor_id": "C1", "tipo_vehiculo_req": "V40", "tipo_carga": "general", "peso_ton": 20,
         "fecha_cargue": cargue.isoformat(), "plazo_entrega": (cargue + timedelta(days=3)).isoformat(), "nivel_servicio": "Estandar", "tarifa_cliente": 5_500_000}
    f.update(extra)
    return f


def en_paralelo(n, tarea):
    """Lanza `n` hilos que arrancan juntos; devuelve sus resultados en orden."""
    barrera, out = threading.Barrier(n), [None] * n

    def correr(i):
        c = TestClient(api.app)
        barrera.wait()
        out[i] = tarea(c, i)
    hilos = [threading.Thread(target=correr, args=(i,)) for i in range(n)]
    [h.start() for h in hilos]
    [h.join(120) for h in hilos]
    return out


# ---------------------------------------------------------------- solicitud nueva
def test_solicitud_nueva_se_recomienda_y_queda_a_nombre_de_quien_la_pidio(cli):
    h = entrar(cli, "comercial")
    r = cli.post("/solicitudes", json=formulario(), headers=h)
    assert r.status_code == 200, r.text
    j = r.json()
    assert j["solicitud_id"].startswith("W") and j["ranking"]
    mias = cli.get("/mis-solicitudes", headers=h).json()
    assert [m["solicitud_id"] for m in mias] == [j["solicitud_id"]]
    assert cli.get("/mis-solicitudes", headers=entrar(cli, "operador")).json()[0]["solicitante"] == "comercial"


@pytest.mark.parametrize("cambio,codigo", [
    ({"peso_ton": 80}, 422),                                    # supera la capacidad del vehículo
    ({"peso_ton": 0}, 422),
    ({"cliente_id": "NO"}, 422), ({"corredor_id": "C99"}, 422), ({"tipo_vehiculo_req": "VXX"}, 422),
    ({"tarifa_cliente": 0}, 422), ({"tipo_carga": "radiactiva"}, 422),
])
def test_solicitud_nueva_rechaza_datos_invalidos(cli, cambio, codigo):
    assert cli.post("/solicitudes", json=formulario(**cambio), headers=entrar(cli, "comercial")).status_code == codigo


def test_plazo_antes_del_cargue_o_demasiado_largo(cli):
    h = entrar(cli, "comercial")
    f = formulario()
    assert cli.post("/solicitudes", json={**f, "plazo_entrega": f["fecha_cargue"]}, headers=h).status_code == 422
    largo = (datetime.fromisoformat(f["fecha_cargue"]) + timedelta(days=45)).isoformat()
    assert cli.post("/solicitudes", json={**f, "plazo_entrega": largo}, headers=h).status_code == 422


def test_repetir_el_envio_no_duplica_la_solicitud(cli):
    h = entrar(cli, "comercial")
    a = cli.post("/solicitudes", json=formulario(clave_envio="abc-123"), headers=h).json()
    b = cli.post("/solicitudes", json=formulario(clave_envio="abc-123"), headers=h).json()
    assert a["solicitud_id"] == b["solicitud_id"]
    assert len(cli.get("/mis-solicitudes", headers=h).json()) == 1
    # la misma clave con otros datos no se acepta en silencio
    assert cli.post("/solicitudes", json=formulario(clave_envio="abc-123", peso_ton=10), headers=h).status_code == 409


def test_ocho_solicitudes_simultaneas_son_ocho_solicitudes_distintas(cli):
    entrar(cli, "comercial")
    res = en_paralelo(8, lambda c, i: c.post("/solicitudes", json=formulario(peso_ton=10 + i), headers=entrar(c, "comercial")))
    assert [r.status_code for r in res] == [200] * 8
    assert len({r.json()["solicitud_id"] for r in res}) == 8
    assert len(cli.get("/mis-solicitudes", headers=entrar(cli, "comercial")).json()) == 8


def test_el_mismo_envio_desde_dos_pestanas_a_la_vez_es_una_sola_solicitud_y_un_solo_aviso(cli):
    entrar(cli, "comercial")
    f = formulario(nivel_servicio="Urgente", clave_envio="doble-clic")      # «Urgente» siempre pasa por una persona
    res = en_paralelo(2, lambda c, i: c.post("/solicitudes", json=f, headers=entrar(c, "comercial")))
    assert [r.status_code for r in res] == [200, 200] and res[0].json()["solicitud_id"] == res[1].json()["solicitud_id"]
    assert len([e for e in cli.envios if e[0].endswith("ops")]) == 1
    assert len(cli.get("/mis-solicitudes", headers=entrar(cli, "comercial")).json()) == 1


# ---------------------------------------------------------------- decisiones simultáneas
def _pedir(cli, **extra):
    h = entrar(cli, "comercial")
    return cli.post("/solicitudes", json=formulario(**extra), headers=h).json()


def _decision(rec, proveedor=None, usuario="x"):
    return {"recomendacion_id": rec["recomendacion_id"], "solicitud_id": rec["solicitud_id"],
            "proveedor_elegido": proveedor or rec["ranking"][0]["proveedor_id"], "usuario": usuario}


def test_dos_operadores_deciden_la_misma_solicitud_gana_uno(cli):
    rec = _pedir(cli)
    entrar(cli, "operador"); entrar(cli, "jurado")
    res = en_paralelo(2, lambda c, i: c.post("/decision", json=_decision(rec), headers=entrar(c, ["operador", "jurado"][i])))
    assert sorted(r.status_code for r in res) == [200, 409]
    assert "ya fue decidida" in [r for r in res if r.status_code == 409][0].json()["detail"]
    con = sqlite3.connect(cli.db)
    assert con.execute("SELECT count(*) FROM servicio WHERE solicitud_id=?", (rec["solicitud_id"],)).fetchone()[0] == 1     # un solo servicio


def test_la_base_impide_la_doble_decision_aunque_falle_el_candado_de_la_api(cli):
    """Dos procesos distintos (sin compartir el candado de la API) tampoco pueden decidir dos veces."""
    rec = _pedir(cli)
    prov = rec["ranking"][0]["proveedor_id"]
    precio = lambda *a: 3_000_000
    resultados = []

    class D:
        solicitud_id, recomendacion_id, proveedor_elegido, usuario, motivo = rec["solicitud_id"], rec["recomendacion_id"], prov, "t", None

    barrera = threading.Barrier(2)

    def tarea():
        repo = crear_repositorio(str(cli.db))
        barrera.wait()
        try:
            repo.registrar_decision(D, precio)
            resultados.append("ok")
        except ErrorNegocio as e:
            resultados.append(e.codigo)
    hilos = [threading.Thread(target=tarea) for _ in range(2)]
    [h.start() for h in hilos]
    [h.join(60) for h in hilos]
    assert sorted(map(str, resultados)) == ["409", "ok"]


def test_decidir_y_devolver_a_la_vez_no_dejan_las_dos_cosas(cli):
    rec = _pedir(cli)
    entrar(cli, "operador")
    dev = {"solicitud_id": rec["solicitud_id"], "motivo": "cliente_cancelo"}
    res = en_paralelo(2, lambda c, i: c.post("/decision", json=_decision(rec), headers=entrar(c, "operador")) if i == 0
                      else c.post("/rechazo", json=dev, headers=entrar(c, "operador")))
    assert sorted(r.status_code for r in res) == [200, 409]
    con = sqlite3.connect(cli.db)
    hay_decision = con.execute("SELECT count(*) FROM decision WHERE solicitud_id=? AND recomendacion_id IS NOT NULL", (rec["solicitud_id"],)).fetchone()[0]
    hay_rechazo = con.execute("SELECT count(*) FROM rechazo WHERE solicitud_id=?", (rec["solicitud_id"],)).fetchone()[0]
    assert hay_decision + hay_rechazo == 1


# ---------------------------------------------------------------- devolver al solicitante
def test_devolver_una_solicitud(cli):
    rec = _pedir(cli, nivel_servicio="Urgente")
    sid = rec["solicitud_id"]
    ho, hc = entrar(cli, "operador"), entrar(cli, "comercial")
    assert cli.post("/rechazo", json={"solicitud_id": sid, "motivo": "datos_incompletos"}, headers=hc).status_code == 403          # solicitante no devuelve
    assert cli.post("/rechazo", json={"solicitud_id": sid, "motivo": "otro"}, headers=ho).status_code == 422                          # «otro» exige nota
    assert any(p["solicitud"]["solicitud_id"] == sid for p in cli.get("/pendientes", headers=ho).json())
    r = cli.post("/rechazo", json={"solicitud_id": sid, "motivo": "datos_incompletos", "nota": "falta el contacto de la bodega"}, headers=ho)
    assert r.status_code == 200
    mia = cli.get("/mis-solicitudes", headers=hc).json()[0]
    assert mia["estado"] == "devuelta" and mia["motivo_devolucion"] == "datos_incompletos" and mia["devuelta_por"] == "operador" and "contacto" in mia["nota_devolucion"]
    assert not any(p["solicitud"]["solicitud_id"] == sid for p in cli.get("/pendientes", headers=ho).json())     # sale de la cola
    assert cli.post("/decision", json=_decision(rec), headers=ho).status_code == 409                              # ya no se puede asignar
    assert cli.post("/rechazo", json={"solicitud_id": sid, "motivo": "otro", "nota": "x"}, headers=ho).status_code == 409   # ni devolver dos veces
    assert cli.post("/solicitudes", json=formulario(clave_envio=sid[10:]), headers=hc).status_code in (200, 409)
    assert cli.get(f"/rechazos/{sid}", headers=hc).json()["motivo"] == "datos_incompletos"


def test_no_se_puede_devolver_lo_ya_decidido(cli):
    rec = _pedir(cli)
    ho = entrar(cli, "operador")
    assert cli.post("/decision", json=_decision(rec), headers=ho).status_code == 200
    assert cli.post("/rechazo", json={"solicitud_id": rec["solicitud_id"], "motivo": "cliente_cancelo"}, headers=ho).status_code == 409


def test_lo_escalado_solo_lo_devuelve_gerencia(cli):
    hc, ho, hg = entrar(cli, "comercial"), entrar(cli, "operador"), entrar(cli, "jurado")
    sid = None
    for t in (1, 2, 3, 4, 5, 6):              # busca un envío que quede escalado: tarifa muy baja ⇒ margen negativo
        r = cli.post("/solicitudes", json=formulario(tarifa_cliente=500_000, peso_ton=10 + t), headers=hc).json()
        if r["escalar_gerencia"]:
            sid = r["solicitud_id"]; break
    assert sid, "una tarifa tan baja debería escalar a gerencia"
    assert cli.post("/rechazo", json={"solicitud_id": sid, "motivo": "precio_fuera_de_rango"}, headers=ho).status_code == 403
    assert cli.post("/rechazo", json={"solicitud_id": sid, "motivo": "precio_fuera_de_rango"}, headers=hg).status_code == 200


# ---------------------------------------------------------------- capacidad: la última unidad
def _dejar_una_unidad(cli, proveedor):
    con = sqlite3.connect(cli.db)
    con.execute("INSERT INTO capacidad_snapshot (proveedor_id, tipo_vehiculo_id, fecha_hora, unidades_disponibles) VALUES (?,?,?,1)", (proveedor, "V40", "2026-10-12T06:00"))
    con.commit(); con.close()
    api.estado().recargar()


def test_la_ultima_unidad_no_se_asigna_dos_veces(cli):
    hc, ho = entrar(cli, "comercial"), entrar(cli, "operador")
    primera = cli.post("/solicitudes", json=formulario(), headers=hc).json()
    x = primera["ranking"][0]["proveedor_id"]
    _dejar_una_unidad(cli, x)
    a = cli.post("/solicitudes", json=formulario(peso_ton=21), headers=hc).json()
    b = cli.post("/solicitudes", json=formulario(peso_ton=22), headers=hc).json()
    assert x in [p["proveedor_id"] for p in a["ranking"]] and x in [p["proveedor_id"] for p in b["ranking"]]       # ambas veían la unidad libre
    assert cli.post("/decision", json=_decision(a, x), headers=ho).status_code == 200
    r = cli.post("/decision", json=_decision(b, x), headers=ho)                                                 # la segunda ya no tiene unidad
    assert r.status_code == 409 and "ya no tiene unidades" in r.json()["detail"]
    nueva = cli.post("/solicitudes", json=formulario(peso_ton=23), headers=hc).json()                           # y las próximas ya no lo proponen
    assert x not in [p["proveedor_id"] for p in nueva["ranking"]]
    assert any(d["proveedor_id"] == x and d["motivo"] == "sin_capacidad" and "comprometidas" in d["detalle"] for d in nueva["descartados"])


def test_dos_decisiones_simultaneas_por_la_ultima_unidad_gana_una(cli):
    hc = entrar(cli, "comercial"); entrar(cli, "operador")
    x = cli.post("/solicitudes", json=formulario(), headers=hc).json()["ranking"][0]["proveedor_id"]
    _dejar_una_unidad(cli, x)
    a = cli.post("/solicitudes", json=formulario(peso_ton=21), headers=hc).json()
    b = cli.post("/solicitudes", json=formulario(peso_ton=22), headers=hc).json()
    res = en_paralelo(2, lambda c, i: c.post("/decision", json=_decision([a, b][i], x), headers=entrar(c, "operador")))
    assert sorted(r.status_code for r in res) == [200, 409]
