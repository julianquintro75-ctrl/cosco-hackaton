"""Contrato del puerto Repositorio: cualquier implementación nueva (PostgreSQL, etc.) debe pasar estas pruebas
(agregar su fábrica a FABRICAS). Además verifica que las capas altas no hablen SQL."""
import re
from pathlib import Path

import pandas as pd
import pytest

from engine.repositorio import TABLAS_BASE, ErrorNegocio, Repositorio, crear_repositorio, registrar_backend

RAIZ = Path(__file__).resolve().parent.parent
FABRICAS = {"sqlite": lambda db: crear_repositorio(str(db))}


@pytest.fixture(params=list(FABRICAS))
def repo(request, db_copia):
    return FABRICAS[request.param](db_copia)


def test_cumple_el_protocolo(repo):
    assert isinstance(repo, Repositorio)


def test_tablas_base(repo):
    T = repo.tablas_base()
    assert set(TABLAS_BASE) <= set(T) and all(isinstance(v, pd.DataFrame) and len(v) for v in T.values())
    assert {"incidente", "a_tiempo", "entrega_real", "fecha_cargue"} <= set(T["servicios"].columns)


def test_consultas(repo):
    assert repo.conteos()["proveedor"] == 12
    prueba = repo.solicitudes_prueba()
    assert prueba and repo.solicitud(prueba[0]["solicitud_id"])["solicitud_id"] == prueba[0]["solicitud_id"]
    assert repo.solicitud("NO-EXISTE") is None
    assert isinstance(repo.recomendaciones_sin_decision(), list)


def test_reglas_de_negocio_se_elevan(repo):
    class D:  # decisión sobre una solicitud inexistente
        solicitud_id, recomendacion_id, proveedor_elegido, usuario, motivo = "NO-EXISTE", None, "P01", "t", None
    with pytest.raises(ErrorNegocio) as e:
        repo.registrar_decision(D, lambda *a: 1)
    assert e.value.codigo == 404


def test_destino_desconocido():
    with pytest.raises(ValueError):
        crear_repositorio("mongodb://x")


def test_backend_nuevo_se_registra(db_copia):
    class Falso:
        def __init__(self, destino): self.destino = destino
    registrar_backend("falso", Falso)
    assert crear_repositorio("falso://algo").destino == "falso://algo"


def test_capas_altas_no_hablan_sql():
    """app/ y engine/ (salvo repo_sqlite) no importan sqlite3 ni escriben SQL."""
    mal = []
    for f in list((RAIZ / "app").glob("*.py")) + [p for p in (RAIZ / "engine").glob("*.py") if p.name != "repo_sqlite.py"]:
        t = f.read_text(encoding="utf8")
        if re.search(r"\bsqlite3\b", t.replace("sqlite3 directo", "")) or re.search(r"\b(SELECT|INSERT INTO|UPDATE \w+ SET|DELETE FROM)\b", t):
            mal.append(f.name)
    assert not mal, f"SQL fuera del repositorio: {mal}"
