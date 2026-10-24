"""Sesión: solo entra quien tiene credenciales; la clave no se guarda en claro; hay freno a la fuerza bruta."""
import pytest
from fastapi.testclient import TestClient

from app import api, auth


@pytest.fixture()
def cli(monkeypatch, tmp_path, db_copia):
    monkeypatch.setenv("COSCO_AUTH_REQUIRED", "1")
    monkeypatch.setenv("COSCO_AUTH_DB", str(tmp_path / "auth.db"))
    monkeypatch.setenv("COSCO_JWT_SECRET", "x" * 40)
    monkeypatch.setenv("COSCO_DB", str(db_copia))
    auth._FALLOS.clear()
    return TestClient(api.app)


def test_sin_sesion_401_y_salud_publica(cli):
    assert cli.get("/pendientes").status_code == 401
    assert cli.get("/salud").status_code == 200


def test_login_semilla_y_acceso(cli):
    r = cli.post("/auth/login", json={"usuario": "jurado", "clave": auth.SEMILLA_CLAVE})
    assert r.status_code == 200
    h = {"Authorization": f"Bearer {r.json()['access_token']}"}
    assert cli.get("/auth/yo", headers=h).json()["usuario"] == "jurado"
    assert cli.get("/config", headers=h).status_code == 200


def test_clave_mala_y_token_falso(cli):
    assert cli.post("/auth/login", json={"usuario": "jurado", "clave": "mal"}).status_code == 401
    assert cli.post("/auth/login", json={"usuario": "nadie", "clave": "mal"}).status_code == 401
    assert cli.get("/config", headers={"Authorization": "Bearer basura"}).status_code == 401


def test_bloqueo_tras_cinco_fallos(cli):
    for _ in range(5):
        cli.post("/auth/login", json={"usuario": "jurado", "clave": "mal"})
    r = cli.post("/auth/login", json={"usuario": "jurado", "clave": auth.SEMILLA_CLAVE})
    assert r.status_code == 429 and "Retry-After" in r.headers


def test_hash_no_es_texto_plano():
    h = auth.hashear("secreto")
    assert "secreto" not in h and auth.verificar("secreto", h) and not auth.verificar("otro", h)


def test_decision_toma_el_autor_de_la_sesion(cli, db_copia):
    h = {"Authorization": "Bearer " + cli.post("/auth/login", json={"usuario": "jurado", "clave": auth.SEMILLA_CLAVE}).json()["access_token"]}
    sol = cli.get("/solicitudes/prueba", headers=h).json()[3]
    cuerpo = {k: sol[k] for k in ("solicitud_id", "cliente_id", "corredor_id", "tipo_vehiculo_req", "tipo_carga", "peso_ton", "fecha_cargue", "plazo_entrega", "tarifa_cliente", "nivel_servicio")}
    rec = cli.post("/recomendar", json=cuerpo, headers=h).json()
    assert rec["ranking"], "la solicitud elegida debe tener Top"
    cli.post("/decision", json={"recomendacion_id": rec["recomendacion_id"], "solicitud_id": sol["solicitud_id"],
                                "proveedor_elegido": rec["ranking"][0]["proveedor_id"], "usuario": "suplantado"}, headers=h)
    assert cli.get(f"/decisiones/{sol['solicitud_id']}", headers=h).json()["usuario"] == "jurado"
