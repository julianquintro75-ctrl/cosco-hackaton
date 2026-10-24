"""Paso 14 · el guion de la demo (docs/guion_demo.md) sigue siendo cierto con la base de semilla 7."""
import sqlite3
import pytest
from contratos.contracts import SolicitudIn
from engine.datos import Base
from engine.motor_a import MotorA

K = ("solicitud_id", "cliente_id", "corredor_id", "tipo_vehiculo_req", "tipo_carga", "peso_ton", "fecha_cargue", "plazo_entrega", "tarifa_cliente")


@pytest.fixture(scope="module")
def caso(db_copia):
    con = sqlite3.connect(db_copia); con.row_factory = sqlite3.Row
    m = MotorA(Base(db_copia))
    def f(sid, nivel=None):
        r = con.execute("SELECT * FROM solicitud WHERE solicitud_id=?", (sid,)).fetchone()
        if r is None: pytest.skip(f"{sid} no existe: la base no es la de semilla 7")
        r = dict(r)
        return m.recomendar(SolicitudIn(**{k: r[k] for k in K}, mercancia_peligrosa=bool(r["mercancia_peligrosa"]), nivel_servicio=nivel or r["nivel_servicio"]))
    return f


def top1(o): return o.ranking[0].nombre


def test_escena1_estandar_un_clic(caso):
    o = caso("R005909")
    assert top1(o) == "TransPacifico" and not o.requiere_revision


def test_escena2_cambia_el_ganador_por_nivel(caso):
    assert top1(caso("R005909", "Flexible")) == "Economica del Sur"
    u = caso("R005909", "Urgente")
    assert top1(u) == "TransPacifico" and "urgente" in u.motivos_revision


def test_escena3_mejor_sin_capacidad(caso):
    o = caso("R005923")
    assert any(d.proveedor_id == "P12" and d.motivo == "sin_capacidad" for d in o.descartados)
    assert top1(o) == "Premium Logistics" and not o.escalar_gerencia


def test_escena3_escalamiento_a_gerencia(caso):
    o = caso("R005907")
    assert o.escalar_gerencia and "margen_negativo" in o.motivos_revision


def test_escena4_sugerencia_de_prueba(caso):
    o = caso("R005913")
    assert o.sugerencia_prueba and o.sugerencia_prueba.proveedor_id == "P04"
    assert "P04" not in [p.proveedor_id for p in o.ranking[:1]]


def test_escena5_peligrosa_filtro_duro(caso):
    o = caso("R005949")
    assert [p.nombre for p in o.ranking] == ["Seguridad Total"]
    assert sum(d.motivo == "sin_certificacion" for d in o.descartados) == 9
