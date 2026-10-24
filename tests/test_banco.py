"""Paso 13 · banco de comparacion: determinismo de A y honestidad de B/C sin clave."""
import sys
from pathlib import Path
import pytest
RAIZ = Path(__file__).resolve().parent.parent
sys.path[:0] = [str(RAIZ / "bench"), str(RAIZ / "scripts"), str(RAIZ / "seed")]
from comparar import MotorB_Jev, MotorC_LLM, NoMedido, a_solicitud, cargar_solicitudes, correr, robustez_A
from engine.datos import Base, cargar_config
from engine.motor_a import MotorA


@pytest.fixture(scope="module")
def entorno(db_copia):
    cfg = cargar_config(); base = Base(db_copia)
    reqs = cargar_solicitudes(str(db_copia), 40)
    return cfg, base, reqs, [a_solicitud(r) for r in reqs]


def test_resultado_no_depende_del_orden_de_llamadas(entorno):
    cfg, base, _, sols = entorno
    caliente = MotorA(base, cfg)
    for s in sols: caliente.recomendar(s)           # llena caches con otras solicitudes del mismo dia
    for s in sols:
        frio = MotorA(base, cfg).recomendar(s).model_dump(mode="json", exclude={"latencia_ms"})
        assert caliente.recomendar(s).model_dump(mode="json", exclude={"latencia_ms"}) == frio


def test_robustez_A_total(entorno):
    cfg, base, _, sols = entorno
    assert all(v == 1.0 for v in robustez_A(base, cfg, sols, n=20).values())


def test_sin_clave_no_se_inventan_resultados(entorno, monkeypatch):
    cfg, base, reqs, sols = entorno
    monkeypatch.delenv("TYPESAFE_API_KEY", raising=False); monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    A = MotorA(base, cfg)
    with pytest.raises(NoMedido): MotorB_Jev(A).recomendar(sols[0])
    with pytest.raises(NoMedido): MotorC_LLM(A).recomendar(sols[0])
    A_ref = {s.solicitud_id: A.evaluar(s)[0] for s in sols}
    assert correr(MotorB_Jev(A), sols, reqs, cfg, A_ref)["estado"] == "no medido"
