"""Cliente de la API para las interfaces: la UI no abre la base de datos, solo habla con este módulo.

- Sin COSCO_API_URL: ejecuta la lógica de app.api en proceso (útil para desarrollo y pruebas).
- Con COSCO_API_URL (p. ej. http://api:8000): llama por HTTP; cualquier otro frontend o servicio puede hacer lo mismo.
Los errores se elevan como HTTPException en ambos modos.
"""
from __future__ import annotations

import io
import os

import httpx
import pandas as pd
from fastapi import HTTPException

from contratos.contracts import DecisionIn, RecomendacionOut, SolicitudIn

URL = os.environ.get("COSCO_API_URL", "").rstrip("/")
TIMEOUT = float(os.environ.get("COSCO_API_TIMEOUT", "60"))


def modo() -> str:
    return f"http ({URL})" if URL else "en proceso"


def _error(r: httpx.Response) -> HTTPException:
    try:
        detalle = r.json().get("detail", r.text)
    except ValueError:
        detalle = r.text
    return HTTPException(r.status_code, detalle)


_TOKEN: dict[str, str] = {}


def _token(renovar: bool = False) -> dict[str, str]:
    """Sesión de servicio de esta UI: COSCO_API_USER / COSCO_API_PASSWORD (si la API exige autenticación)."""
    u, c = os.environ.get("COSCO_API_USER"), os.environ.get("COSCO_API_PASSWORD")
    if not (u and c):
        return {}
    if renovar or "t" not in _TOKEN:
        r = httpx.post(f"{URL}/auth/login", json={"usuario": u, "clave": c}, timeout=TIMEOUT)
        if r.status_code >= 400:
            raise _error(r)
        _TOKEN["t"] = r.json()["access_token"]
    return {"Authorization": f"Bearer {_TOKEN['t']}"}


def _http(metodo: str, ruta: str, **kw) -> httpx.Response:
    try:
        for intento in (0, 1):
            h = {**kw.get("headers", {}), **_token(renovar=intento == 1)}
            r = httpx.request(metodo, f"{URL}{ruta}", timeout=TIMEOUT, **{**kw, "headers": h})
            if r.status_code != 401 or intento == 1 or not os.environ.get("COSCO_API_USER"):
                break
    except httpx.HTTPError as e:
        raise HTTPException(503, f"No se pudo contactar la API en {URL}: {e}") from e
    if r.status_code >= 400:
        raise _error(r)
    return r


def _api():
    from app import api
    return api


def recomendar(sol: SolicitudIn) -> RecomendacionOut:
    if not URL:
        return _api().recomendar(sol)
    return RecomendacionOut.model_validate(_http("POST", "/recomendar", content=sol.model_dump_json(), headers={"Content-Type": "application/json"}).json())


def decision(d: DecisionIn) -> dict:
    if not URL:
        return _api().decision(d, {"usuario": d.usuario})
    return _http("POST", "/decision", content=d.model_dump_json(), headers={"Content-Type": "application/json"}).json()


def salud() -> dict:
    return _api().salud() if not URL else _http("GET", "/salud").json()


def config() -> dict:
    return _api().config() if not URL else _http("GET", "/config").json()


def tablas() -> dict[str, pd.DataFrame]:
    """Tablas de referencia y servicios (para construir la instantánea que usan tableros y formularios)."""
    if not URL:
        return _api().estado().repo.tablas_base()
    return {k: pd.DataFrame(v) for k, v in _http("GET", "/datos/tablas").json().items()}


def solicitudes_prueba() -> list[dict]:
    return _api().solicitudes_prueba() if not URL else _http("GET", "/solicitudes/prueba").json()


def solicitud(sid: str) -> dict | None:
    try:
        return _api().solicitud(sid) if not URL else _http("GET", f"/solicitudes/{sid}").json()
    except HTTPException as e:
        if e.status_code == 404:
            return None
        raise


def decision_de(sid: str) -> dict | None:
    return _api().decision_de(sid) if not URL else _http("GET", f"/decisiones/{sid}").json()


def pendientes(filtro: str) -> list[tuple[RecomendacionOut, dict]]:
    filas = _api().pendientes(filtro) if not URL else _http("GET", "/pendientes", params={"filtro": filtro}).json()
    return [(RecomendacionOut.model_validate(f["recomendacion"]), f["solicitud"]) for f in filas]


def _df(ruta: str) -> pd.DataFrame:
    return pd.read_json(io.StringIO(_http("GET", ruta).text), orient="records")


def tablero_decisiones() -> pd.DataFrame:
    return _api().estado().repo.decisiones_tablero() if not URL else _df("/tableros/decisiones")


def tablero_cierres() -> pd.DataFrame:
    return _api().estado().repo.cierres_tablero() if not URL else _df("/tableros/cierres")
