"""Paso 6 · Casos dificiles del motor A. Este archivo es tambien la lista de casos de la demostracion."""
import json, random, sqlite3
from datetime import datetime, timedelta
import pytest
from contratos.contracts import RecomendacionOut, SolicitudIn
from engine.datos import Base
from engine.motor_a import MotorA

PLAZO_TIPICO_H = {"C1": 22, "C2": 12, "C3": 21.5, "C4": 37, "C5": 25.5, "C6": 34.6, "C7": 27, "C8": 27.2}


@pytest.fixture(scope="module")
def motor(db_copia):
    return MotorA(Base(db_copia))


def sol(corredor="C1", as_of="2026-09-20", nivel="Estandar", vehiculo="V40", carga="general", horas=None, sid="T1", peligrosa=False, cliente="K002"):
    fc = datetime.fromisoformat(as_of) + timedelta(days=1, hours=8)
    return SolicitudIn(solicitud_id=sid, cliente_id=cliente, corredor_id=corredor, tipo_vehiculo_req=vehiculo, tipo_carga=carga, peso_ton=18,
                       mercancia_peligrosa=peligrosa, fecha_cargue=fc, plazo_entrega=fc + timedelta(hours=horas or PLAZO_TIPICO_H[corredor]),
                       nivel_servicio=nivel, tarifa_cliente=6_000_000, as_of=as_of)


def test_refrigerada_solo_reefer(motor):
    b = motor.base
    reefer = set(b.certs[b.certs.tipo == "REEFER"].proveedor_id)
    for c in ("C4", "C5", "C7"):
        o = motor.recomendar(sol(c, vehiculo="VRF", carga="refrigerada"))
        assert o.ranking, f"debe haber candidatos reefer en {c}"
        assert {p.proveedor_id for p in o.ranking} <= reefer
        assert any(d.motivo == "sin_certificacion" or d.motivo == "sin_vehiculo" for d in o.descartados)


def test_peligrosa_solo_imo(motor):
    o = motor.recomendar(sol("C4", carga="peligrosa", peligrosa=True))
    assert [p.proveedor_id for p in o.ranking] == ["P09"], "solo Seguridad Total tiene IMO"


def test_c2_cama_baja_sin_opcion(motor):
    o = motor.recomendar(sol("C2", vehiculo="VCB", carga="sobredimensionada"))
    assert o.ranking == []
    assert len(o.descartados) == len(motor.base.proveedores)
    assert o.requiere_revision and "sin_opcion" in o.motivos_revision


def test_plazo_imposible_escala(motor):
    o = motor.recomendar(sol("C4", horas=6))
    assert o.escalar_gerencia and "sin_candidato_en_plazo" in o.motivos_revision
    assert all(any("Plazo en riesgo" in a for a in p.alertas) for p in o.ranking)
    assert all(p.p_a_tiempo < 0.5 for p in o.ranking), "con un plazo imposible no se puede prometer puntualidad"


def test_nuevo_rumbo_prudente(motor):
    o = motor.recomendar(sol("C1", as_of="2026-09-05", nivel="Flexible"))
    nr = [p for p in o.ranking if p.proveedor_id == "P04"]
    assert nr, "en Flexible Nuevo Rumbo debe aparecer"
    assert any("Poco historial" in a or "Sin historial" in a for a in nr[0].alertas)
    viejo = min((p for p in o.ranking if p.proveedor_id != "P04"), key=lambda p: p.desglose.incertidumbre)
    assert nr[0].desglose.incertidumbre > viejo.desglose.incertidumbre, "la poca evidencia se castiga"
    assert o.sugerencia_prueba and o.sugerencia_prueba.proveedor_id == "P04"
    u = motor.recomendar(sol("C1", as_of="2026-09-05", nivel="Urgente"))
    assert not u.ranking or u.ranking[0].proveedor_id != "P04", "en Urgente no se arriesga con un proveedor sin historial"
    assert u.sugerencia_prueba is None, "nunca se sugiere prueba en Urgente"


def _andina(motor, dias, nivel):
    top1 = top3 = n = 0
    for d in dias:
        for c in ("C1", "C2", "C3", "C4", "C5"):
            for v in ("V40", "V20"):
                o = motor.recomendar(sol(c, as_of=d, nivel=nivel, vehiculo=v))
                if "P01" in {x.proveedor_id for x in o.descartados}:
                    continue
                ids = [p.proveedor_id for p in o.ranking]; n += 1
                top1 += ids[:1] == ["P01"]; top3 += "P01" in ids
    return top1 / n, top3 / n


def test_andina_detecta_deterioro(motor):
    julio = [f"2026-07-{d:02d}" for d in range(5, 29, 4)]
    sep = [f"2026-09-{d:02d}" for d in range(14, 29, 3)]
    u_jul, _ = _andina(motor, julio, "Urgente")
    u_sep, _ = _andina(motor, sep, "Urgente")
    _, e_jul3 = _andina(motor, julio, "Estandar")
    _, e_sep3 = _andina(motor, sep, "Estandar")
    assert u_jul >= 0.6, f"en julio Andina debe ser Top-1 frecuente en Urgente ({u_jul:.0%})"
    assert e_jul3 >= 0.8, f"en julio Andina debe estar casi siempre en el Top-3 Estandar ({e_jul3:.0%})"
    assert u_sep <= 0.25 and e_sep3 <= 0.6, f"en septiembre debe perder posiciones (Urgente top1 {u_sep:.0%}, Estandar top3 {e_sep3:.0%})"
    for c in ("C1", "C2", "C3", "C4", "C5"):
        o = motor.recomendar(sol(c, as_of="2026-09-20", nivel="Estandar"))
        assert o.ranking[0].proveedor_id != "P01", f"el 2026-09-20 Andina no debe ser Top-1 en Estandar ({c})"


def _json(o: RecomendacionOut):
    return json.dumps(o.model_dump(mode="json", exclude={"latencia_ms"}), sort_keys=True)


def test_orden_de_proveedores_no_importa(db_copia):
    s = sol("C1")
    a = MotorA(Base(db_copia)).recomendar(s)
    b2 = Base(db_copia)
    random.seed(3)
    for attr in ("proveedores", "flota", "tarifas", "certs"):
        df = getattr(b2, attr)
        setattr(b2, attr, df.sample(frac=1, random_state=3).reset_index(drop=True))
    b = MotorA(b2).recomendar(s)
    assert _json(a) == _json(b)


def test_determinismo(motor):
    s = sol("C4", nivel="Urgente")
    assert len({_json(motor.recomendar(s)) for _ in range(100)}) == 1


def test_tres_niveles_cambian_razonablemente(motor):
    s = {n: motor.recomendar(sol("C1", as_of="2026-07-15", nivel=n)) for n in ("Flexible", "Estandar", "Urgente")}
    # cuanto mas caro el retraso, mas peso tiene la puntualidad: el ganador no puede ser menos puntual
    assert s["Flexible"].ranking[0].p_a_tiempo <= s["Estandar"].ranking[0].p_a_tiempo <= s["Urgente"].ranking[0].p_a_tiempo
    assert s["Flexible"].ranking[0].desglose.precio <= s["Urgente"].ranking[0].desglose.precio
    assert "urgente" in s["Urgente"].motivos_revision


def test_ningun_descartado_en_top3_y_contrato(motor, db_copia):
    con = sqlite3.connect(db_copia); con.row_factory = sqlite3.Row
    filas = con.execute("SELECT * FROM solicitud WHERE fase='prueba' ORDER BY solicitud_id LIMIT 200").fetchall()
    for r in filas:
        s = SolicitudIn(**{k: r[k] for k in ("solicitud_id", "cliente_id", "corredor_id", "tipo_vehiculo_req", "tipo_carga", "peso_ton",
                                             "fecha_cargue", "plazo_entrega", "tarifa_cliente", "nivel_servicio")},
                        mercancia_peligrosa=bool(r["mercancia_peligrosa"]))
        o = motor.recomendar(s)
        RecomendacionOut.model_validate(o.model_dump())
        assert not ({p.proveedor_id for p in o.ranking} & {d.proveedor_id for d in o.descartados})
        assert [p.costo_esperado for p in o.ranking] == sorted(p.costo_esperado for p in o.ranking)
        for p in o.ranking:
            assert p.costo_esperado == p.desglose.total and p.margen_esperado == s.tarifa_cliente - p.costo_esperado
