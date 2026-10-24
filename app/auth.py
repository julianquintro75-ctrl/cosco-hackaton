"""Autenticación de la API: usuarios con contraseña (PBKDF2), sesión con JWT y freno a los intentos fallidos.

Variables de entorno:
  COSCO_AUTH_REQUIRED   «1» (por defecto) exige sesión en todas las rutas salvo /salud y /auth/login; «0» solo para desarrollo/pruebas
  COSCO_JWT_SECRET      secreto de firma (≥ 32 caracteres). Sin él se genera uno aleatorio por proceso y las sesiones mueren al reiniciar
  COSCO_JWT_MINUTOS     vida de la sesión (por defecto 60)
  COSCO_AUTH_DB         archivo SQLite de usuarios (por defecto data/auth.db; independiente de la base de datos del negocio)
  COSCO_SEED_USER / COSCO_SEED_PASSWORD   usuario semilla de demostración (jurado / Cosco-2026!). Cámbialo fuera de la demo.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import logging
import os
import secrets
import threading
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

import jwt
from engine.repo_sqlite import UsuariosSQLite
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field

log = logging.getLogger("cosco.auth")
RAIZ = Path(__file__).resolve().parent.parent
ITERACIONES = 600_000          # OWASP 2023 para PBKDF2-HMAC-SHA256
INTENTOS_MAX, BLOQUEO_S = 5, 15 * 60
PUBLICAS = ("/salud", "/auth/login", "/docs", "/openapi.json", "/redoc")

SEMILLA_USUARIO = "jurado"
SEMILLA_CLAVE = "Cosco-2026!"


def hashear(clave: str, sal: Optional[bytes] = None, iteraciones: int = ITERACIONES) -> str:
    sal = sal or secrets.token_bytes(16)
    h = hashlib.pbkdf2_hmac("sha256", clave.encode(), sal, iteraciones)
    return f"pbkdf2_sha256${iteraciones}${base64.b64encode(sal).decode()}${base64.b64encode(h).decode()}"


def verificar(clave: str, guardado: str) -> bool:
    try:
        alg, it, sal, h = guardado.split("$")
        esperado = base64.b64decode(h)
        calc = hashlib.pbkdf2_hmac("sha256", clave.encode(), base64.b64decode(sal), int(it))
        return alg == "pbkdf2_sha256" and hmac.compare_digest(calc, esperado)
    except Exception:
        return False


_HASH_FALSO = hashear("no-existe")      # para igualar el tiempo cuando el usuario no existe


_ALMACEN: Optional[UsuariosSQLite] = None
_LOCK = threading.Lock()
_FALLOS: dict[tuple[str, str], list[float]] = {}
_SECRETO_ALEATORIO = secrets.token_urlsafe(48)


def almacen() -> UsuariosSQLite:
    global _ALMACEN
    ruta = os.environ.get("COSCO_AUTH_DB", str(RAIZ / "data" / "auth.db"))
    if _ALMACEN is None or _ALMACEN.ruta != ruta:
        _ALMACEN = UsuariosSQLite(ruta, lambda: hashear(os.environ.get("COSCO_SEED_PASSWORD", SEMILLA_CLAVE)), os.environ.get("COSCO_SEED_USER", SEMILLA_USUARIO))
    return _ALMACEN


def _secreto() -> str:
    s = os.environ.get("COSCO_JWT_SECRET")
    if s and len(s) < 32:
        raise RuntimeError("COSCO_JWT_SECRET debe tener al menos 32 caracteres")
    return s or _SECRETO_ALEATORIO


def exigida() -> bool:
    return os.environ.get("COSCO_AUTH_REQUIRED", "1") != "0"


def emitir(u: dict) -> tuple[str, int]:
    minutos = int(os.environ.get("COSCO_JWT_MINUTOS", "60"))
    ahora = datetime.now(timezone.utc)
    tok = jwt.encode({"sub": u["usuario"], "nom": u["nombre"], "rol": u["rol"], "iat": ahora, "exp": ahora + timedelta(minutes=minutos)}, _secreto(), algorithm="HS256")
    return tok, minutos * 60


def exigir_sesion(request: Request) -> Optional[dict]:
    """Dependencia global: devuelve el usuario de la sesión (o None si la autenticación está apagada)."""
    if request.url.path in PUBLICAS or request.method == "OPTIONS":
        return None
    if not exigida():
        return {"usuario": "dev", "nombre": "Desarrollo", "rol": "gerencia"}
    cab = request.headers.get("authorization", "")
    esquema, _, tok = cab.partition(" ")
    if esquema.lower() != "bearer" or not tok:
        raise HTTPException(401, "Sesión requerida", headers={"WWW-Authenticate": "Bearer"})
    try:
        p = jwt.decode(tok, _secreto(), algorithms=["HS256"], options={"require": ["exp", "sub"]})
    except jwt.PyJWTError:
        raise HTTPException(401, "Sesión inválida o vencida", headers={"WWW-Authenticate": "Bearer"})
    u = almacen().obtener(p["sub"])
    if not u:
        raise HTTPException(401, "Usuario inactivo", headers={"WWW-Authenticate": "Bearer"})
    return u


def sesion(u: Optional[dict] = Depends(exigir_sesion)) -> dict:
    return u or {"usuario": "dev", "nombre": "Desarrollo", "rol": "gerencia"}


class LoginIn(BaseModel):
    usuario: str = Field(min_length=1, max_length=64)
    clave: str = Field(min_length=1, max_length=256)


router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login")
def login(datos: LoginIn, request: Request):
    ip = request.client.host if request.client else "?"
    llave = (datos.usuario.lower(), ip)
    ahora = time.time()
    with _LOCK:
        f = [t for t in _FALLOS.get(llave, []) if ahora - t < BLOQUEO_S]
        _FALLOS[llave] = f
        if len(f) >= INTENTOS_MAX:
            raise HTTPException(429, "Demasiados intentos. Espera unos minutos.", headers={"Retry-After": str(int(BLOQUEO_S - (ahora - f[0])))})
    u = almacen().obtener(datos.usuario)
    ok = verificar(datos.clave, u["clave_hash"] if u else _HASH_FALSO)
    if not (u and ok):
        with _LOCK:
            _FALLOS.setdefault(llave, []).append(ahora)
        raise HTTPException(401, "Usuario o contraseña incorrectos")
    with _LOCK:
        _FALLOS.pop(llave, None)
    tok, exp = emitir(u)
    return {"access_token": tok, "token_type": "bearer", "expira_en": exp, "usuario": {"usuario": u["usuario"], "nombre": u["nombre"], "rol": u["rol"]}}


@router.get("/yo")
def yo(u: dict = Depends(sesion)):
    return {"usuario": u["usuario"], "nombre": u["nombre"], "rol": u["rol"]}
