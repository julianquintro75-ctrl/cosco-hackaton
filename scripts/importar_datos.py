"""Importa datos reales desde la plantilla Excel (docs/referencia/plantilla_datos.xlsx) a una base nueva.

Uso:  python -m scripts.importar_datos datos.xlsx --out data/real.db [--as-of 2026-09-30] [--sin-estadisticas]

Valida hojas, columnas y llaves foráneas ANTES de escribir; si hay errores no crea la base.
Luego calcula las estadísticas por proveedor (mismo paso que scripts/init_datos.py).
Las hojas recomendacion, decision, estadistica_proveedor y modelo_version las llena el sistema.
"""
import argparse
import os
import sqlite3
import subprocess
import sys
from pathlib import Path

import pandas as pd

RAIZ = Path(__file__).resolve().parents[1]
# (hoja, obligatoria, columnas clave de referencia {columna: (tabla_padre, columna_padre)})
ORDEN = [
    ("cliente", False, {}),
    ("corredor", True, {}),
    ("tipo_vehiculo", True, {}),
    ("proveedor", True, {}),
    ("certificacion", True, {"proveedor_id": ("proveedor", "proveedor_id")}),
    ("flota", True, {"proveedor_id": ("proveedor", "proveedor_id"), "tipo_vehiculo_id": ("tipo_vehiculo", "tipo_vehiculo_id")}),
    ("tarifa", True, {"proveedor_id": ("proveedor", "proveedor_id"), "corredor_id": ("corredor", "corredor_id"),
                      "tipo_vehiculo_id": ("tipo_vehiculo", "tipo_vehiculo_id")}),
    ("capacidad_snapshot", False, {"proveedor_id": ("proveedor", "proveedor_id"), "tipo_vehiculo_id": ("tipo_vehiculo", "tipo_vehiculo_id")}),
    ("solicitud", True, {"cliente_id": ("cliente", "cliente_id"), "corredor_id": ("corredor", "corredor_id"),
                         "tipo_vehiculo_req": ("tipo_vehiculo", "tipo_vehiculo_id")}),
    ("servicio", True, {"solicitud_id": ("solicitud", "solicitud_id"), "proveedor_id": ("proveedor", "proveedor_id")}),
    ("evento_servicio", False, {"servicio_id": ("servicio", "servicio_id")}),
    ("feedback", False, {"servicio_id": ("servicio", "servicio_id")}),
]


def leer(xlsx: Path) -> tuple[dict[str, pd.DataFrame], list[str]]:
    errores: list[str] = []
    libro = pd.read_excel(xlsx, sheet_name=None, dtype=object)
    tablas: dict[str, pd.DataFrame] = {}
    for hoja, obligatoria, _ in ORDEN:
        if hoja not in libro:
            if obligatoria:
                errores.append(f"falta la hoja obligatoria '{hoja}'")
            continue
        df = libro[hoja].dropna(how="all")
        df = df.astype(object).where(df.notna(), None)
        tablas[hoja] = df
    return tablas, errores


def validar(tablas: dict[str, pd.DataFrame], con: sqlite3.Connection) -> list[str]:
    errores: list[str] = []
    for hoja, _, refs in ORDEN:
        if hoja not in tablas:
            continue
        df = tablas[hoja]
        cols = [r[1] for r in con.execute(f"PRAGMA table_info({hoja})")]
        sobran = [c for c in df.columns if c not in cols]
        faltan = [c for c in cols if c not in df.columns and c not in ("tarifa_id", "evento_id")]
        if sobran:
            errores.append(f"{hoja}: columnas desconocidas {sobran}")
        if faltan:
            errores.append(f"{hoja}: faltan columnas {faltan}")
        if len(df) == 0:
            errores.append(f"{hoja}: la hoja está vacía")
        for col, (padre, colp) in refs.items():
            if col in df.columns and padre in tablas:
                validos = set(tablas[padre][colp])
                malos = sorted({str(v) for v in df[col] if v not in validos})
                if malos:
                    errores.append(f"{hoja}.{col}: {len(malos)} valor(es) sin {padre}: {malos[:5]}")
    return errores


def importar(xlsx: Path, out: Path) -> tuple[dict[str, int], list[str]]:
    """Devuelve (filas por tabla, errores). Si hay errores no deja base escrita."""
    tablas, errores = leer(xlsx)
    tmp = out.with_suffix(".tmp")
    tmp.unlink(missing_ok=True)
    con = sqlite3.connect(tmp)
    con.executescript((RAIZ / "db" / "schema.sql").read_text(encoding="utf-8"))
    errores += validar(tablas, con)
    if "cliente" not in tablas and "solicitud" in tablas:   # cliente es deseable: se crea mínimo para no romper la llave
        ids = sorted(set(tablas["solicitud"]["cliente_id"]))
        tablas["cliente"] = pd.DataFrame({"cliente_id": ids, "nombre": ids, "segmento": "mixto", "prioridad": 3})
        tablas = {k: tablas[k] for k in ["cliente"] + [h for h, _, _ in ORDEN if h in tablas and h != "cliente"]}
    conteo: dict[str, int] = {}
    if not errores:
        try:
            for hoja, df in tablas.items():
                cols = list(df.columns)
                con.executemany(f"INSERT INTO {hoja} ({','.join(cols)}) VALUES ({','.join('?' * len(cols))})",
                                [tuple(None if v is None else (v.item() if hasattr(v, 'item') else v) for v in fila)
                                 for fila in df.itertuples(index=False)])
                conteo[hoja] = len(df)
            con.commit()
        except sqlite3.Error as e:    # CHECK/NOT NULL del esquema: mensaje claro, sin base a medias
            errores.append(f"el esquema rechazó los datos: {e}")
    con.close()
    if errores:
        tmp.unlink(missing_ok=True)
        return {}, errores
    out.unlink(missing_ok=True)
    tmp.rename(out)
    return conteo, []


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("xlsx", type=Path)
    ap.add_argument("--out", type=Path, default=RAIZ / "data" / "real.db")
    ap.add_argument("--as-of", help="fecha de corte de las estadísticas (por defecto, la última entrega)")
    ap.add_argument("--sin-estadisticas", action="store_true")
    a = ap.parse_args()
    a.out.parent.mkdir(parents=True, exist_ok=True)
    conteo, errores = importar(a.xlsx, a.out)
    if errores:
        print("NO se importó. Corrige estos problemas en el Excel:")
        for e in errores:
            print("  -", e)
        sys.exit(1)
    print(f"Base creada: {a.out}")
    for t, n in conteo.items():
        print(f"  {t:20s} {n:>7d} filas")
    if not a.sin_estadisticas:
        as_of = a.as_of
        if not as_of:
            con = sqlite3.connect(a.out)
            as_of = (con.execute("SELECT max(substr(entrega_real,1,10)) FROM servicio").fetchone()[0])
            con.close()
        subprocess.run([sys.executable, "-m", "engine.estadisticas", "--as-of", as_of], cwd=RAIZ, check=True, env={**os.environ, "COSCO_DB": str(a.out.resolve())})
    print(f"Listo. Para usarla: COSCO_DB={a.out} make api  (o COSCO_DB en .env)")


if __name__ == "__main__":
    main()
