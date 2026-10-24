"""Paso 8 · la interfaz permite recomendar y aprobar en dos clics (simulador de Streamlit)."""
import os, sqlite3
from pathlib import Path
from streamlit.testing.v1 import AppTest

UI = str(Path(__file__).resolve().parent.parent / "app" / "ui.py")


def test_aprobar_recomendacion(db_copia):
    os.environ["COSCO_DB"] = str(db_copia)
    at = AppTest.from_file(UI, default_timeout=60).run()
    assert not at.exception
    at.button[0].click().run()                    # «Recomendar» (botón del formulario)
    assert not at.exception
    assert any("Aprobar #1" in b.label for b in at.button)
    n0 = sqlite3.connect(db_copia).execute("SELECT COUNT(*) FROM decision WHERE recomendacion_id IS NOT NULL").fetchone()[0]
    next(b for b in at.button if "Aprobar #1" in b.label).click().run()
    assert not at.exception
    n1 = sqlite3.connect(db_copia).execute("SELECT COUNT(*) FROM decision WHERE recomendacion_id IS NOT NULL").fetchone()[0]
    assert n1 == n0 + 1
    assert any("Decisión guardada" in s.value or "Decisión registrada" in s.value for s in at.success)


def test_pantallas_revision_y_gerencia(db_copia):
    os.environ["COSCO_DB"] = str(db_copia)
    for pag in ("Revisión", "Gerencia", "Tableros"):
        at = AppTest.from_file(UI, default_timeout=60).run()
        at.sidebar.radio[0].set_value(pag).run()
        assert not at.exception, pag
