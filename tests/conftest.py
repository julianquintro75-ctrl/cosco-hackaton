import shutil, sqlite3, sys
from pathlib import Path
import pytest

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))
DB = RAIZ / "data" / "cosco.db"


@pytest.fixture(scope="session")
def db_copia(tmp_path_factory):
    """Copia de la base generada (las pruebas que escriben no tocan data/cosco.db)."""
    if not DB.exists():
        pytest.skip("falta data/cosco.db: corre python seed/generate.py --sucio")
    p = tmp_path_factory.mktemp("db") / "cosco.db"
    shutil.copy(DB, p)
    return p


def mini_db(path: Path, servicios: list[dict]) -> Path:
    """Base minima: 1 corredor, 1 vehiculo, 1 proveedor 'PX' y los servicios dados (a_tiempo, entrega_real)."""
    con = sqlite3.connect(path)
    con.executescript((RAIZ / "db" / "schema.sql").read_text(encoding="utf8"))
    con.execute("INSERT INTO corredor VALUES ('C1','Buenaventura','Bogota','Buenaventura',519,0.75)")
    con.execute("INSERT INTO tipo_vehiculo VALUES ('V40','Tractomula',32,'40')")
    con.execute("INSERT INTO proveedor VALUES ('PX','Prueba','1','Cali','2020-01-01',1)")
    con.execute("INSERT INTO flota VALUES ('PX','V40',5)")
    con.execute("INSERT INTO cliente VALUES ('K1','Cliente','importador',2)")
    con.execute("INSERT INTO tarifa (proveedor_id,corredor_id,tipo_vehiculo_id,precio_cop,vigente_desde,vigente_hasta) VALUES ('PX','C1','V40',3300000,'2020-01-01',NULL)")
    for i, s in enumerate(servicios):
        sid = f"R{i:03d}"
        con.execute("INSERT INTO solicitud VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
                    (sid, "K1", "C1", "V40", "general", 20, 0, s["cargue"], s["cargue"], s["plan"], "Estandar", 4000000, "historico"))
        con.execute("INSERT INTO servicio VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                    (f"S{i:03d}", sid, "PX", 3300000, s["cargue"], s["plan"], s["entrega"], s["a_tiempo"], 3300000, 0, "ENTREGADO"))
    con.commit(); con.close()
    return path
