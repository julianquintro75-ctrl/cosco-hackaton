"""El importador acepta la plantilla completa, rechaza llaves rotas y deja la base utilizable."""
import sqlite3

import pandas as pd
import pytest

from scripts.importar_datos import importar

HOJAS = ["cliente", "corredor", "tipo_vehiculo", "proveedor", "certificacion", "flota", "tarifa",
         "capacidad_snapshot", "solicitud", "servicio", "feedback"]


@pytest.fixture(scope="module")
def xlsx(db_copia, tmp_path_factory):
    p = tmp_path_factory.mktemp("xl") / "datos.xlsx"
    con = sqlite3.connect(db_copia)
    with pd.ExcelWriter(p) as w:
        for h in HOJAS:
            pd.read_sql(f"SELECT * FROM {h}" + (" LIMIT 300" if h == "servicio" else ""), con).to_excel(w, sheet_name=h, index=False)
    con.close()
    return p


def test_importa_y_cuenta(xlsx, tmp_path):
    # servicio recortado deja huérfanos en feedback: se recorta también
    df = pd.read_excel(xlsx, sheet_name=None)
    ids = set(df["servicio"]["servicio_id"]); sol = set(df["servicio"]["solicitud_id"])
    df["feedback"] = df["feedback"][df["feedback"]["servicio_id"].isin(ids)]
    df["solicitud"] = df["solicitud"][df["solicitud"]["solicitud_id"].isin(sol)]
    p = tmp_path / "ok.xlsx"
    with pd.ExcelWriter(p) as w:
        for h, d in df.items():
            d.to_excel(w, sheet_name=h, index=False)
    conteo, errores = importar(p, tmp_path / "real.db")
    assert errores == [] and conteo["servicio"] == 300
    con = sqlite3.connect(tmp_path / "real.db")
    assert con.execute("SELECT count(*) FROM servicio").fetchone()[0] == 300
    assert con.execute("PRAGMA foreign_key_check").fetchall() == []


def test_rechaza_llave_rota_sin_crear_base(xlsx, tmp_path):
    df = pd.read_excel(xlsx, sheet_name=None)
    df["tarifa"].loc[0, "proveedor_id"] = "P99"
    p = tmp_path / "mal.xlsx"
    with pd.ExcelWriter(p) as w:
        for h, d in df.items():
            d.to_excel(w, sheet_name=h, index=False)
    conteo, errores = importar(p, tmp_path / "x.db")
    assert any("tarifa.proveedor_id" in e for e in errores) and not (tmp_path / "x.db").exists()


def test_falta_hoja_obligatoria(xlsx, tmp_path):
    df = pd.read_excel(xlsx, sheet_name=None); df.pop("tarifa")
    p = tmp_path / "sin.xlsx"
    with pd.ExcelWriter(p) as w:
        for h, d in df.items():
            d.to_excel(w, sheet_name=h, index=False)
    _, errores = importar(p, tmp_path / "y.db")
    assert any("falta la hoja obligatoria 'tarifa'" in e for e in errores)
