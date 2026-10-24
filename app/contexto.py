"""Contexto de solo lectura que usan las interfaces: referencias, configuración y estadísticas, obtenidos por la API
(no abre la base de datos). Se cachea unos minutos en Streamlit."""
from __future__ import annotations

from types import SimpleNamespace

from app import cliente_api as cli
from engine.datos import Base
from engine.estadisticas import Estadisticas


def cargar() -> SimpleNamespace:
    base = Base(tablas=cli.tablas())
    return SimpleNamespace(base=base, cfg=cli.config(), motor=SimpleNamespace(est=Estadisticas(base)), origen=cli.modo())
