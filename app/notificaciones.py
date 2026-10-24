"""Avisos por Slack cuando una recomendación necesita a una persona (revisión del operador o escalamiento a gerencia).

Configuración (variables de entorno; las URLs son secretos y nunca se devuelven por la API):
  COSCO_SLACK_WEBHOOK              webhook entrante de Slack para todos los avisos
  COSCO_SLACK_WEBHOOK_OPERACIONES  (opcional) canal del operador; tiene prioridad sobre el general
  COSCO_SLACK_WEBHOOK_GERENCIA     (opcional) canal de gerencia; tiene prioridad sobre el general
  COSCO_PUBLIC_URL                 dirección del frontend, para el enlace del aviso (por defecto http://localhost:4200)
Se activan o desactivan desde la pantalla Avisos (rol gerencia). Un fallo de Slack nunca interrumpe la recomendación:
se registra en el historial y el caso sigue visible en «Pendientes».
"""
from __future__ import annotations

import logging
import os
from datetime import datetime
from urllib.parse import urlparse

from contratos.contracts import RecomendacionOut

log = logging.getLogger("cosco.avisos")
HOSTS_SLACK = ("hooks.slack.com", "hooks.slack-gov.com")
DESTINOS = ("operaciones", "gerencia")


def _webhook(destino: str) -> str:
    return os.environ.get(f"COSCO_SLACK_WEBHOOK_{destino.upper()}") or os.environ.get("COSCO_SLACK_WEBHOOK") or ""


def configurados() -> dict[str, bool]:
    return {d: bool(_webhook(d)) for d in DESTINOS}


def _post(url: str, cuerpo: dict) -> tuple[int, str]:
    import httpx
    r = httpx.post(url, json=cuerpo, timeout=5.0, follow_redirects=False)
    return r.status_code, r.text[:200]


def enviar(destino: str, cuerpo: dict) -> tuple[str, str]:
    """(estado, detalle). Estados: enviada · fallo · sin_webhook. Solo se aceptan URLs https de Slack."""
    url = _webhook(destino)
    if not url:
        return "sin_webhook", "no hay webhook configurado"
    u = urlparse(url)
    if u.scheme != "https" or u.hostname not in HOSTS_SLACK:
        return "fallo", "el webhook no es una URL https de Slack"
    try:
        codigo, texto = _post(url, cuerpo)
    except Exception as e:                      # red caída, tiempo agotado…
        log.warning("No se pudo avisar a Slack: %s", type(e).__name__)
        return "fallo", type(e).__name__
    return ("enviada", "") if codigo == 200 else ("fallo", f"Slack respondió {codigo}: {texto}")


def _cop(v: float) -> str:
    return "$" + f"{v:,.0f}".replace(",", ".")


def mensaje(evento: str, sol, rec: RecomendacionOut, autor: str) -> dict:
    top = rec.ranking[0] if rec.ranking else None
    motivos = ", ".join(rec.motivos_revision) or "—"
    url = os.environ.get("COSCO_PUBLIC_URL", "http://localhost:4200").rstrip("/") + f"/recomendar/{sol.solicitud_id}"
    if evento == "escalamiento":
        titulo = f":rotating_light: *Escalamiento a gerencia* · solicitud {sol.solicitud_id}"
    else:
        titulo = f":eyes: *Revisión necesaria* · solicitud {sol.solicitud_id}"
    lineas = [titulo,
              f"Corredor {sol.corredor_id} · {sol.tipo_vehiculo_req} · nivel {sol.nivel_servicio} · pedida por {autor}",
              f"Motivos: {motivos}"]
    if top:
        lineas.append(f"Primera opción del modelo: {top.nombre} ({_cop(top.costo_esperado)} de costo esperado; margen {_cop(top.margen_esperado)})")
    else:
        lineas.append("El modelo no encontró ningún proveedor que cumpla las reglas y el plazo.")
    lineas.append(f"<{url}|Abrir el caso>")
    return {"text": "\n".join(lineas)}


def evento_de(rec: RecomendacionOut) -> tuple[str, str] | None:
    """(evento, destino) que corresponde a la recomendación, o None si no necesita a nadie."""
    if rec.escalar_gerencia:
        return "escalamiento", "gerencia"
    if rec.requiere_revision:
        return "revision", "operaciones"
    return None


def notificar(almacen, sol, rec: RecomendacionOut, autor: str) -> None:
    """Avisa (una sola vez por solicitud y evento) si los ajustes lo permiten. Pensada para correr en segundo plano."""
    try:
        par = evento_de(rec)
        if not par:
            return
        evento, destino = par
        ahora = datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
        aj = almacen.ajustes()
        if not aj["slack_activo"] or not aj["avisar_escalamiento" if evento == "escalamiento" else "avisar_revision"]:
            return                                       # apagado a propósito: no se registra ruido
        if not almacen.reclamar_aviso(sol.solicitud_id, evento):
            return                                       # ya se avisó (o lo está haciendo otro pedido simultáneo): recalcular no repite el aviso
        estado, detalle = enviar(destino, mensaje(evento, sol, rec, autor))
        if estado != "enviada":
            almacen.liberar_aviso(sol.solicitud_id, evento)   # que un próximo intento pueda volver a avisar
        almacen.registrar_notificacion(ahora, evento, sol.solicitud_id, destino, estado, detalle)
    except Exception:                                    # un aviso fallido jamás debe romper el flujo
        log.exception("Error al notificar")


def probar(almacen) -> list[dict]:
    """Manda un mensaje de prueba a cada destino configurado (lo dispara gerencia desde la pantalla Avisos)."""
    out = []
    ahora = datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
    for d in DESTINOS:
        estado, detalle = enviar(d, {"text": f":white_check_mark: Prueba de avisos del Recomendador de proveedores ({d})."})
        almacen.registrar_notificacion(ahora, "prueba", None, d, estado, detalle)
        out.append({"destino": d, "estado": estado, "detalle": detalle})
    return out
