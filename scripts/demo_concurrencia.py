"""Demostración en vivo de pedidos simultáneos contra la API en marcha (usa los usuarios de demostración por rol).

  python scripts/demo_concurrencia.py                     # API en http://localhost:8000
  COSCO_API_URL=http://localhost:8000 COSCO_DEMO_PASSWORD='Cosco-2026!' python scripts/demo_concurrencia.py

Crea solicitudes nuevas (quedan en la base): úsalo con la base de demostración. Muestra tres cosas:
  1. ocho solicitudes que llegan a la vez → ocho solicitudes distintas;
  2. el mismo envío desde dos pestañas a la vez → una sola solicitud;
  3. dos personas deciden la misma solicitud a la vez → gana una, la otra recibe un aviso claro;
  4. una persona decide y otra devuelve a la vez → solo una de las dos cosas queda.
"""
import os
import threading
from datetime import datetime, timedelta

import httpx

URL = os.environ.get("COSCO_API_URL", "http://localhost:8000").rstrip("/")
CLAVE = os.environ.get("COSCO_DEMO_PASSWORD", "Cosco-2026!")


def entrar(usuario: str) -> dict:
    r = httpx.post(f"{URL}/auth/login", json={"usuario": usuario, "clave": CLAVE}, timeout=30)
    r.raise_for_status()
    return {"Authorization": "Bearer " + r.json()["access_token"]}


def formulario(peso=20, **extra) -> dict:
    c = (datetime.now() + timedelta(days=6)).replace(hour=8, minute=0, second=0, microsecond=0)
    f = {"cliente_id": "K001", "corredor_id": "C1", "tipo_vehiculo_req": "V40", "tipo_carga": "general", "peso_ton": peso,
         "fecha_cargue": c.isoformat(), "plazo_entrega": (c + timedelta(days=3)).isoformat(), "nivel_servicio": "Estandar", "tarifa_cliente": 5_500_000}
    f.update(extra)
    return f


def a_la_vez(n, tarea):
    barrera, out = threading.Barrier(n), [None] * n

    def correr(i):
        barrera.wait()
        out[i] = tarea(i)
    hilos = [threading.Thread(target=correr, args=(i,)) for i in range(n)]
    [h.start() for h in hilos]
    [h.join(120) for h in hilos]
    return out


def nueva(h, **kw):
    return httpx.post(f"{URL}/solicitudes", json=formulario(**kw), headers=h, timeout=60)


def main():
    hc, ho, hg = entrar("comercial"), entrar("operador"), entrar("jurado")

    print("1) Ocho solicitudes a la vez")
    res = a_la_vez(8, lambda i: nueva(hc, peso=10 + i))
    ids = {r.json()["solicitud_id"] for r in res if r.status_code == 200}
    print(f"   respuestas {sorted({r.status_code for r in res})} · solicitudes distintas: {len(ids)} de 8")

    print("2) El mismo envío dos veces a la vez (doble clic)")
    res = a_la_vez(2, lambda i: nueva(hc, peso=19, clave_envio="demo" + datetime.now().strftime("%H%M%S")))
    mismos = {r.json()["solicitud_id"] for r in res if r.status_code == 200}
    print(f"   respuestas {[r.status_code for r in res]} · solicitudes creadas: {len(mismos)}")

    print("3) Dos personas deciden la misma solicitud a la vez")
    rec = nueva(hc, peso=17).json()
    d = {"recomendacion_id": rec["recomendacion_id"], "solicitud_id": rec["solicitud_id"], "proveedor_elegido": rec["ranking"][0]["proveedor_id"], "usuario": "x"}
    res = a_la_vez(2, lambda i: httpx.post(f"{URL}/decision", json=d, headers=[ho, hg][i], timeout=60))
    for quien, r in zip(("operador", "gerencia"), res):
        print(f"   {quien}: {r.status_code} {'' if r.status_code == 200 else r.json().get('detail', '')}")

    print("4) Una persona decide y otra devuelve a la vez")
    rec = nueva(hc, peso=16).json()
    d = {"recomendacion_id": rec["recomendacion_id"], "solicitud_id": rec["solicitud_id"], "proveedor_elegido": rec["ranking"][0]["proveedor_id"], "usuario": "x"}
    dev = {"solicitud_id": rec["solicitud_id"], "motivo": "cliente_cancelo"}
    res = a_la_vez(2, lambda i: httpx.post(f"{URL}/decision", json=d, headers=ho, timeout=60) if i == 0 else httpx.post(f"{URL}/rechazo", json=dev, headers=hg, timeout=60))
    for quien, r in zip(("decidir", "devolver"), res):
        print(f"   {quien}: {r.status_code} {'' if r.status_code == 200 else r.json().get('detail', '')}")


if __name__ == "__main__":
    main()
