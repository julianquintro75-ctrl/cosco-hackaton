"""Roles (solicitante · operador · gerencia) y avisos por Slack: permisos, escalamiento, ajustes y tolerancia a fallos."""
import shutil

import pytest
from fastapi.testclient import TestClient

from app import api, auth, notificaciones

HOOK = "https://hooks.slack.com/services/T000/B000/xxxx"
CAMPOS = ("solicitud_id", "cliente_id", "corredor_id", "tipo_vehiculo_req", "tipo_carga", "peso_ton", "mercancia_peligrosa", "fecha_cargue", "plazo_entrega", "nivel_servicio", "tarifa_cliente")


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
    envios = []
    monkeypatch.setattr(notificaciones, "_post", lambda url, cuerpo: (envios.append((url, cuerpo)) or (200, "ok")))
    auth._FALLOS.clear()
    c = TestClient(api.app)
    c.envios = envios
    return c


def entrar(c, usuario):
    r = c.post("/auth/login", json={"usuario": usuario, "clave": auth.SEMILLA_CLAVE})
    assert r.status_code == 200, r.text
    return {"Authorization": "Bearer " + r.json()["access_token"]}


def cuerpo(c, h, sid):
    s = c.get(f"/solicitudes/{sid}", headers=h).json()
    return {k: (bool(s[k]) if k == "mercancia_peligrosa" else s[k]) for k in CAMPOS}


def buscar(c, h, escalado):
    """Primera solicitud de prueba que requiere revisión (escalada o no). Devuelve (id, recomendación)."""
    for s in c.get("/solicitudes/prueba", headers=h).json():
        r = c.post("/recomendar", json=cuerpo(c, h, s["solicitud_id"]), headers=h)
        j = r.json()
        if j["requiere_revision"] and j["escalar_gerencia"] == escalado:
            return s["solicitud_id"], j
    pytest.skip("no hay un caso así en la muestra")


def test_cada_rol_tiene_su_usuario_semilla(cli):
    roles = {u: cli.get("/auth/yo", headers=entrar(cli, u)).json()["rol"] for u in ("jurado", "operador", "comercial")}
    assert roles == {"jurado": "gerencia", "operador": "operador", "comercial": "solicitante"}


def test_solicitante_pide_pero_no_decide_ni_ve_pendientes(cli):
    h = entrar(cli, "comercial")
    sid = cli.get("/solicitudes/prueba", headers=h).json()[0]["solicitud_id"]
    r = cli.post("/recomendar", json=cuerpo(cli, h, sid), headers=h)
    assert r.status_code == 200
    d = {"recomendacion_id": r.json()["recomendacion_id"], "solicitud_id": sid, "proveedor_elegido": r.json()["ranking"][0]["proveedor_id"], "usuario": "x"}
    assert cli.post("/decision", json=d, headers=h).status_code == 403
    assert cli.get("/pendientes", headers=h).status_code == 403
    assert cli.get("/tableros/decisiones", headers=h).status_code == 403
    assert cli.get("/notificaciones/ajustes", headers=h).status_code == 403


def test_operador_decide_revision_pero_no_lo_escalado(cli):
    ho, hg = entrar(cli, "operador"), entrar(cli, "jurado")
    sid, rec = buscar(cli, hg, escalado=True)
    d = {"recomendacion_id": rec["recomendacion_id"], "solicitud_id": sid, "proveedor_elegido": rec["ranking"][0]["proveedor_id"], "usuario": "x"}
    assert cli.get("/pendientes?filtro=gerencia", headers=ho).status_code == 403
    assert cli.post("/decision", json=d, headers=ho).status_code == 403
    assert cli.post("/decision", json=d, headers=hg).status_code == 200


def test_operador_si_decide_un_caso_de_revision(cli):
    ho = entrar(cli, "operador")
    sid, rec = buscar(cli, ho, escalado=False)
    assert any(p["solicitud"]["solicitud_id"] == sid for p in cli.get("/pendientes", headers=ho).json())
    d = {"recomendacion_id": rec["recomendacion_id"], "solicitud_id": sid, "proveedor_elegido": rec["ranking"][0]["proveedor_id"], "usuario": "x"}
    assert cli.post("/decision", json=d, headers=ho).status_code == 200


def test_aviso_de_revision_va_a_operaciones_una_sola_vez(cli):
    h = entrar(cli, "comercial")
    sid, _ = buscar(cli, h, escalado=False)
    ops = [e for e in cli.envios if e[0].endswith("ops")]
    assert len(ops) == 1 and sid in ops[0][1]["text"] and "comercial" in ops[0][1]["text"]
    cli.post("/recomendar", json=cuerpo(cli, h, sid), headers=h)            # recalcular no repite el aviso
    assert len([e for e in cli.envios if e[0].endswith("ops") and sid in e[1]["text"]]) == 1


def test_escalamiento_avisa_a_gerencia(cli):
    h = entrar(cli, "comercial")
    sid, _ = buscar(cli, h, escalado=True)
    assert any(e[0].endswith("ger") and sid in e[1]["text"] and "gerencia" in e[1]["text"].lower() for e in cli.envios)


def test_apagar_slack_no_envia_nada(cli):
    hg = entrar(cli, "jurado")
    r = cli.put("/notificaciones/ajustes", json={"slack_activo": False}, headers=hg)
    assert r.status_code == 200 and r.json()["ajustes"]["slack_activo"] is False
    buscar(cli, hg, escalado=False)
    assert cli.envios == []


def test_solo_gerencia_cambia_ajustes_y_nunca_se_expone_la_url(cli):
    assert cli.put("/notificaciones/ajustes", json={"slack_activo": False}, headers=entrar(cli, "operador")).status_code == 403
    r = cli.get("/notificaciones/ajustes", headers=entrar(cli, "operador"))
    assert r.status_code == 200 and "hooks.slack.com" not in r.text and r.json()["webhooks"] == {"operaciones": True, "gerencia": True}


def test_si_slack_falla_la_recomendacion_sigue_y_queda_en_el_historial(cli, monkeypatch):
    def cae(url, cuerpo):
        raise ConnectionError("sin red")
    monkeypatch.setattr(notificaciones, "_post", cae)
    h = entrar(cli, "jurado")
    sid, _ = buscar(cli, h, escalado=False)
    hist = cli.get("/notificaciones/historial", headers=h).json()
    assert hist and hist[0]["estado"] == "fallo" and hist[0]["solicitud_id"] == sid


def test_solo_se_acepta_un_webhook_de_slack(cli, monkeypatch):
    monkeypatch.setenv("COSCO_SLACK_WEBHOOK_OPERACIONES", "https://malo.example.com/hook")
    h = entrar(cli, "jurado")
    buscar(cli, h, escalado=False)
    assert not [e for e in cli.envios if "malo.example" in e[0]]
    assert cli.get("/notificaciones/historial", headers=h).json()[0]["estado"] == "fallo"


def test_probar_avisos_solo_gerencia(cli):
    assert cli.post("/notificaciones/probar", headers=entrar(cli, "operador")).status_code == 403
    r = cli.post("/notificaciones/probar", headers=entrar(cli, "jurado"))
    assert r.status_code == 200 and {x["estado"] for x in r.json()} == {"enviada"}


def test_mis_solicitudes_separa_por_rol(cli):
    hc, ho = entrar(cli, "comercial"), entrar(cli, "operador")
    sid = cli.get("/solicitudes/prueba", headers=hc).json()[0]["solicitud_id"]
    cli.post("/recomendar", json=cuerpo(cli, hc, sid), headers=hc)
    otro = cli.get("/solicitudes/prueba", headers=ho).json()[1]["solicitud_id"]
    cli.post("/recomendar", json=cuerpo(cli, ho, otro), headers=ho)
    suyas = {x["solicitud_id"] for x in cli.get("/mis-solicitudes", headers=hc).json()}
    todas = {x["solicitud_id"] for x in cli.get("/mis-solicitudes", headers=ho).json()}
    assert suyas == {sid} and todas == {sid, otro}


def test_tablas_ligeras_solo_traen_referencias(cli):
    h = entrar(cli, "comercial")
    lig = cli.get("/datos/tablas?ligero=true", headers=h).json()
    assert set(lig) == {"proveedor", "corredor", "tipo_vehiculo", "cliente"} and lig["corredor"][0]["origen"]
    assert "servicios" in cli.get("/datos/tablas", headers=h).json()
