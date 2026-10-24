"""El cliente en modo HTTP devuelve lo mismo que la lógica en proceso."""
import importlib
from datetime import datetime, timedelta

import httpx
import pytest
from fastapi.testclient import TestClient

from contratos.contracts import SolicitudIn


def _sol():
    fc = datetime(2026, 10, 2, 15)
    return SolicitudIn(solicitud_id="T-cli-1", cliente_id="K027", corredor_id="C1", tipo_vehiculo_req="V20", tipo_carga="general", peso_ton=10.9,
                       mercancia_peligrosa=False, fecha_cargue=fc, plazo_entrega=fc + timedelta(hours=22), nivel_servicio="Estandar",
                       tarifa_cliente=3_002_000, as_of=datetime(2026, 10, 1, 15))


def test_http_igual_a_en_proceso(db_copia, monkeypatch):
    monkeypatch.setenv("COSCO_DB", str(db_copia))
    from app import api, cliente_api
    cliente_api = importlib.reload(cliente_api)
    local = cliente_api.recomendar(_sol())
    tc = TestClient(api.app)
    monkeypatch.setattr(cliente_api, "URL", "http://test")
    monkeypatch.setattr(httpx, "request", lambda metodo, url, timeout=None, **kw: tc.request(metodo, url.replace("http://test", ""), **kw))
    remoto = cliente_api.recomendar(_sol().model_copy(update={"solicitud_id": "T-cli-2"}))
    assert [t.proveedor_id for t in local.ranking] == [t.proveedor_id for t in remoto.ranking]
    # lecturas para la interfaz por HTTP == en proceso
    t_http = cliente_api.tablas()
    monkeypatch.setattr(cliente_api, "URL", "")
    t_loc = cliente_api.tablas()
    assert set(t_http) == set(t_loc) and len(t_http["servicios"]) == len(t_loc["servicios"])
    monkeypatch.setattr(cliente_api, "URL", "http://test")
    assert cliente_api.config()["vida_media_dias"] == 30 and cliente_api.solicitud("NO-EXISTE") is None
    assert len(cliente_api.solicitudes_prueba()) > 0


def test_error_http_se_eleva(monkeypatch):
    from fastapi import HTTPException
    from app import cliente_api
    monkeypatch.setattr(cliente_api, "URL", "http://test")
    monkeypatch.setattr(httpx, "request", lambda *a, **k: httpx.Response(422, json={"detail": "corredor desconocido: X"}))
    with pytest.raises(HTTPException) as e:
        cliente_api.recomendar(_sol())
    assert e.value.status_code == 422
