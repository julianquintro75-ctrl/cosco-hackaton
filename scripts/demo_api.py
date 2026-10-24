"""Demostracion de punta a punta de la API: salud -> recomendar -> decision -> cierre -> ficha.
Uso:
  python scripts/demo_api.py                      # en proceso (no hace falta levantar uvicorn), sobre COSCO_DB o data/cosco.db
  python scripts/demo_api.py --url http://127.0.0.1:8000   # contra una API ya corriendo
Toma una solicitud real de la fase de prueba, la vuelve a pedir como solicitud nueva (id DEMO-...) e imprime cada respuesta."""
import argparse, json, sqlite3, sys, uuid
from datetime import datetime, timedelta
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))
ap = argparse.ArgumentParser(); ap.add_argument("--url"); ap.add_argument("--db", default=None); ap.add_argument("--elegir-otro", action="store_true")
a = ap.parse_args()
if a.db:
    import os; os.environ["COSCO_DB"] = a.db

if a.url:
    import httpx
    cli = httpx.Client(base_url=a.url, timeout=30)
else:
    from fastapi.testclient import TestClient
    from app.api import app
    cli = TestClient(app)


def paso(titulo, r):
    print(f"\n=== {titulo} · HTTP {r.status_code} ===")
    print(json.dumps(r.json(), indent=1, ensure_ascii=False)[:2500])
    if r.status_code >= 400:
        sys.exit(f"falló: {titulo}")
    return r.json()


db = a.db or str(RAIZ / "data" / "cosco.db")
paso("GET /salud", cli.get("/salud"))
con = sqlite3.connect(db); con.row_factory = sqlite3.Row
r = con.execute("SELECT * FROM solicitud WHERE fase='prueba' AND tipo_carga='general' AND nivel_servicio='Estandar' ORDER BY solicitud_id LIMIT 1").fetchone()
sol = {k: r[k] for k in ("cliente_id", "corredor_id", "tipo_vehiculo_req", "tipo_carga", "peso_ton", "fecha_cargue", "plazo_entrega", "nivel_servicio", "tarifa_cliente")}
sol.update(solicitud_id=f"DEMO-{uuid.uuid4().hex[:6]}", mercancia_peligrosa=bool(r["mercancia_peligrosa"]),
           as_of=(datetime.fromisoformat(r["fecha_cargue"]) - timedelta(days=1)).isoformat())
print(f"\nSolicitud basada en {r['solicitud_id']} (fase de prueba): {sol['corredor_id']} {sol['tipo_vehiculo_req']} {sol['nivel_servicio']}")
rec = paso("POST /recomendar", cli.post("/recomendar", json=sol))
top = rec["ranking"]
if a.elegir_otro and len(top) > 1:
    dec = {"recomendacion_id": rec["recomendacion_id"], "solicitud_id": sol["solicitud_id"], "proveedor_elegido": top[1]["proveedor_id"], "usuario": "demo", "motivo": "relacion"}
else:
    dec = {"recomendacion_id": rec["recomendacion_id"], "solicitud_id": sol["solicitud_id"], "proveedor_elegido": top[0]["proveedor_id"], "usuario": "demo"}
d = paso("POST /decision", cli.post("/decision", json=dec))
plan = datetime.fromisoformat(d["entrega_planeada"])
cierre = {"servicio_id": d["servicio_id"], "entrega_real": (plan - timedelta(hours=2)).isoformat(), "a_tiempo": True,
          "costo_final": d["precio_pactado"], "dias_detencion": 0, "hubo_incidente": False, "feedback_puntaje": 3}
paso("POST /cierre", cli.post("/cierre", json=cierre))
paso(f"GET /proveedores/{dec['proveedor_elegido']}/ficha", cli.get(f"/proveedores/{dec['proveedor_elegido']}/ficha"))
s = paso("GET /salud (después)", cli.get("/salud"))
fila = con.execute("SELECT s.estado, s.a_tiempo, d.acepto_recomendacion, r.recomendacion_id FROM servicio s JOIN decision d USING(solicitud_id) JOIN recomendacion r USING(solicitud_id) WHERE s.solicitud_id=?",
                   (sol["solicitud_id"],)).fetchone()
print("\nTablas pobladas para", sol["solicitud_id"], "->", dict(fila) if fila else "NADA")
print("OK: solicitud -> recomendación -> decisión -> cierre recorrido completo.")
