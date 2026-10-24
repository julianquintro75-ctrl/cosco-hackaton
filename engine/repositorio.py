"""Puerto de persistencia: lo único que el resto del sistema sabe de «la base de datos».

El motor, la API y las interfaces dependen de `Repositorio`, no de SQLite. Para usar otra base de datos:
  1. Crear una clase que cumpla `Repositorio` (p. ej. engine/repo_postgres.py).
  2. Registrarla:  registrar_backend("postgresql", RepositorioPostgres)
  3. Apuntar la configuración:  COSCO_REPO=postgresql://usuario:clave@host/db   (COSCO_DB sigue sirviendo para SQLite)
Ninguna otra capa cambia. `tests/test_repositorio.py` define el contrato que toda implementación debe pasar.
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Optional, Protocol, runtime_checkable

import pandas as pd

RAIZ = Path(__file__).resolve().parent.parent
DB_DEFECTO = RAIZ / "data" / "cosco.db"

TABLAS_BASE = ("proveedor", "corredor", "tipo_vehiculo", "certificacion", "flota", "cliente", "tarifa", "capacidad_snapshot", "servicios")


class ErrorNegocio(Exception):
    """Regla de negocio violada al escribir; la API la traduce a HTTP (`codigo`)."""

    def __init__(self, codigo: int, detalle: str):
        super().__init__(detalle)
        self.codigo, self.detalle, self.detail = codigo, detalle, detalle


@runtime_checkable
class Repositorio(Protocol):
    descripcion: str

    # ---- lectura masiva (alimenta el snapshot en memoria `Base`) ----
    def tablas_base(self) -> dict[str, pd.DataFrame]:
        """TABLAS_BASE → DataFrame. «servicios» une servicio+solicitud y trae la columna `incidente` (0/1)."""

    # ---- consultas puntuales ----
    def conteos(self) -> dict[str, int]: ...
    def solicitud(self, solicitud_id: str) -> Optional[dict]: ...
    def solicitudes_prueba(self) -> list[dict]: ...
    def recomendacion(self, solicitud_id: str, recomendacion_id: Optional[str] = None) -> Optional[tuple[str, str]]:
        """(recomendacion_id, json) de la indicada o de la más reciente de la solicitud."""
    def decision_de(self, solicitud_id: str) -> Optional[dict]: ...
    def recomendaciones_sin_decision(self, limite: int = 200) -> list[str]:
        """JSON de las recomendaciones aún sin decisión humana, más recientes primero."""
    def decisiones_tablero(self) -> pd.DataFrame: ...
    def cierres_tablero(self) -> pd.DataFrame: ...

    # ---- escritura ----
    def registrar_modelo(self, version: str, descripcion: str, params_json: str, fecha: str, aprobado_por: Optional[str], reemplazar: bool = False) -> None: ...
    def guardar_recomendacion(self, sol: Any, rec: Any, as_of_iso: str) -> None:
        """Inserta la solicitud (si no existe, fase «vivo») y guarda la recomendación."""
    def registrar_decision(self, d: Any, precio_de: Any, proveedores_validos: Any = None, ventana_flex_h: float = 72) -> dict:
        """Valida y guarda decisión + servicio EN_CURSO en una transacción. `proveedores_validos`: ids permitidos. `precio_de(proveedor, corredor, vehiculo, fecha_cargue)` da la tarifa.
        Lanza ErrorNegocio. Devuelve decision_id, servicio_id, acepto_recomendacion, top1, precio_pactado, entrega_planeada."""
    def cerrar_servicio(self, ci: Any) -> dict:
        """Cierra el servicio y guarda feedback/incidente. Lanza ErrorNegocio. Devuelve {coherente, entrega_real}."""

    def rechazar(self, solicitud_id: str, usuario: str, motivo: str, nota: Optional[str], fecha: str) -> dict:
        """Devuelve la solicitud al solicitante. Excluyente con la decisión y atómico frente a una decisión simultánea (ErrorNegocio 409/404)."""
    def rechazo_de(self, solicitud_id: str) -> Optional[dict]: ...
    def reservas_en_curso(self) -> list[tuple[str, str, str]]:
        """(proveedor_id, tipo_vehiculo, fecha de decisión) de los servicios en curso: capacidad ya comprometida."""

    # ---- estadística bayesiana persistida ----
    def reemplazar_estadisticas(self, df: pd.DataFrame) -> None: ...
    def contar_estadisticas(self) -> int: ...
    def estadistica(self, proveedor_id: str, corredor_id: str, tipo_carga: str) -> Optional[dict]: ...
    def guardar_estadistica(self, fila: dict) -> None: ...
    def contexto_servicio(self, servicio_id: str) -> Optional[tuple[str, str, str]]:
        """(proveedor_id, corredor_id, tipo_carga) del servicio."""


_BACKENDS: dict[str, type] = {}


def registrar_backend(esquema: str, clase: type) -> None:
    _BACKENDS[esquema] = clase


def crear_repositorio(destino: str | Path | None = None) -> Repositorio:
    """`destino`: ruta de archivo (SQLite) o URL «esquema://…». Por omisión: COSCO_REPO, luego COSCO_DB, luego data/cosco.db."""
    destino = str(destino or os.environ.get("COSCO_REPO") or os.environ.get("COSCO_DB") or DB_DEFECTO)
    esquema = destino.split("://", 1)[0] if "://" in destino else "sqlite"
    if esquema not in _BACKENDS:
        from engine import repo_sqlite  # noqa: F401  (se registra al importarse)
    if esquema not in _BACKENDS:
        raise ValueError(f"No hay repositorio registrado para «{esquema}». Disponibles: {sorted(_BACKENDS)}")
    return _BACKENDS[esquema](destino)
