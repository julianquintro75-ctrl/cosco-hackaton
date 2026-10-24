"""Paso 5 · Motor A (propio): filtros duros -> estadistica bayesiana -> costo total esperado en pesos -> Top-3 explicado.
Cumple la interfaz MotorDecision de contratos/contracts.py. El ranking es DETERMINISTA: no usa azar ni depende del orden
de los proveedores en la base. La exploracion (sugerencia de prueba) va aparte y nunca altera el ranking."""
from __future__ import annotations
import hashlib, json, time
from datetime import timedelta
import numpy as np
import pandas as pd

from contratos.contracts import (Descartado, DesgloseCosto, MotorDecision, Nivel, ProveedorEvaluado, RecomendacionOut,
                                 SolicitudIn, SugerenciaPrueba)
from engine.datos import Base, base_compartida, cargar_config
from engine.estadisticas import CERT_CARGA, Estadisticas


def cop(x: float) -> str:
    return "$" + f"{int(round(x)):,}".replace(",", ".")


def as_of_de(sol: SolicitudIn) -> pd.Timestamp:
    """Fecha 'ahora' del sistema. Si no viene, se asume la vispera del cargue (asi se decidia en el historico)."""
    return pd.Timestamp(sol.as_of) if sol.as_of else pd.Timestamp(sol.fecha_cargue) - timedelta(days=1)


COMP_NOMBRE = {"precio": "Precio", "retraso_esperado": "Retraso esperado", "incidente_esperado": "Incidente esperado",
               "incertidumbre": "Incertidumbre (poca evidencia)", "concentracion": "Concentración"}


class MotorA(MotorDecision):
    nombre = "A_propio"

    def __init__(self, base: Base | None = None, cfg: dict | None = None, db=None, **sobrescribir):
        self.base = base or (Base(db) if db else base_compartida())
        self.cfg = dict(cfg or cargar_config()); self.cfg.update(sobrescribir)
        self.est = Estadisticas(self.base, self.cfg)
        self._cuota_cache = {}

    @property
    def modelo_version(self) -> str:
        c = self.cfg
        return f"A-bayes-vm{c['vida_media_dias']:g}-l{c['lambda_incertidumbre']:g}-{c['version_pesos']}"

    # ---------- piezas ----------
    def cuotas(self, as_of) -> dict:
        """Participacion de cada proveedor en los servicios asignados de los ultimos N dias (concentracion)."""
        k = pd.Timestamp(as_of).floor("D")
        if k not in self._cuota_cache:
            s = self.base.servicios_todos
            m = s[(s.fecha_cargue <= as_of) & (s.fecha_cargue > as_of - timedelta(days=self.cfg["concentracion_ventana_dias"]))]
            self._cuota_cache[k] = (m.proveedor_id.value_counts(normalize=True)).to_dict() if len(m) else {}
        return self._cuota_cache[k]

    def prob_no_cumplir(self, as_of, pid, cor, carga, horas_plazo, p_bayes) -> float:
        """P(no cumplir ESTE plazo). Si el plazo es igual o mas holgado que el tipico del corredor, es la P(tarde) bayesiana;
        si es mas apretado, se usa la fraccion (ponderada y suavizada) de transitos historicos que lo habrian superado."""
        E = self.est
        ec = E.indices_corredor(as_of, cor)
        plan_tipico = E._ctx(as_of)["plan"].get(cor, np.inf)
        if horas_plazo >= 0.98 * plan_tipico:
            return p_bayes
        sub = ec[E._cor[ec] == cor]
        ip = E._antes(E._g1.get(pid), E._ctx(as_of)["k"])
        sub = np.intersect1d(ec, ip, assume_unique=True)
        k = 5.0
        base_exc = float((E._tr[ec] > horas_plazo).mean()) if len(ec) else 0.5
        w = E._w(sub, E._ctx(as_of)["as_d"], self.cfg["vida_media_dias"], E._dias)
        exc = (float((w * (E._tr[sub] > horas_plazo)).sum()) + k * base_exc) / (float(w.sum()) + k)
        return float(max(p_bayes, exc))

    # ---------- evaluacion completa (la usan backtest y banco) ----------
    def evaluar(self, sol: SolicitudIn):
        cfg, b = self.cfg, self.base
        as_of = as_of_de(sol)
        f_cargue = pd.Timestamp(sol.fecha_cargue)
        H = (pd.Timestamp(sol.plazo_entrega) - f_cargue).total_seconds() / 3600
        nivel = sol.nivel_servicio.value if isinstance(sol.nivel_servicio, Nivel) else str(sol.nivel_servicio)
        CR = cfg["costo_retraso"][nivel]
        cert_req = set()
        if sol.tipo_carga in CERT_CARGA: cert_req.add(CERT_CARGA[sol.tipo_carga])
        if sol.mercancia_peligrosa: cert_req.add("IMO")
        cuotas = self.cuotas(as_of)
        factibles, descartados = [], []
        flota = b.flota.set_index(["proveedor_id", "tipo_vehiculo_id"]).cantidad.to_dict()
        tar_cor = b.tarifas[(b.tarifas.corredor_id == sol.corredor_id)]
        for p in b.proveedores.sort_values("proveedor_id").itertuples():   # orden fijo: el resultado no depende del orden de entrada
            pid = p.proveedor_id
            if not p.activo or pd.Timestamp(p.fecha_alta) > f_cargue:
                descartados.append(Descartado(proveedor_id=pid, motivo="inactivo", detalle=f"activo desde {p.fecha_alta}")); continue
            if tar_cor[tar_cor.proveedor_id == pid].empty:
                descartados.append(Descartado(proveedor_id=pid, motivo="sin_cobertura", detalle=f"no cubre el corredor {sol.corredor_id}")); continue
            if flota.get((pid, sol.tipo_vehiculo_req), 0) <= 0:
                descartados.append(Descartado(proveedor_id=pid, motivo="sin_vehiculo", detalle=f"no tiene {sol.tipo_vehiculo_req} en su flota")); continue
            precio = b.tarifa_vigente(pid, sol.corredor_id, sol.tipo_vehiculo_req, f_cargue)
            if precio is None:
                descartados.append(Descartado(proveedor_id=pid, motivo="sin_vehiculo", detalle=f"sin tarifa vigente para {sol.tipo_vehiculo_req} en {sol.corredor_id}")); continue
            falta = cert_req - b.certificaciones(pid, f_cargue)
            if falta:
                descartados.append(Descartado(proveedor_id=pid, motivo="sin_certificacion", detalle="le falta " + ", ".join(sorted(falta)))); continue
            unid, f_cap = b.capacidad_en(pid, sol.tipo_vehiculo_req, as_of)
            if unid is not None and unid <= 0:
                descartados.append(Descartado(proveedor_id=pid, motivo="sin_capacidad", detalle=f"0 unidades {sol.tipo_vehiculo_req} en el reporte del {f_cap.date()}")); continue
            st = self.est.combo(as_of, pid, sol.corredor_id, sol.tipo_carga)
            p_nc = self.prob_no_cumplir(as_of, pid, sol.corredor_id, sol.tipo_carga, H, st["p_tarde"])
            lo, hi = st["ic90_p_tarde"]; d = p_nc - st["p_tarde"]
            ic_at = (float(np.clip(1 - hi - d, 0, 1)), float(np.clip(1 - lo - d, 0, 1)))
            cuota = cuotas.get(pid, 0.0)
            pen_conc = max(0.0, (cuota - cfg["concentracion_umbral"]) * 100) * cfg["concentracion_cop_por_punto"]
            des = DesgloseCosto(precio=int(precio), retraso_esperado=int(round(p_nc * CR)),
                                incidente_esperado=int(round(st["tasa_incidente"] * cfg["costo_incidente"])),
                                incertidumbre=int(round(cfg["lambda_incertidumbre"] * st["ic90_ancho"] * CR)),
                                concentracion=int(round(pen_conc)))
            factibles.append(dict(pid=pid, nombre=p.nombre, st=st, p_nc=p_nc, ic_at=ic_at, des=des, total=des.total, cuota=cuota,
                                  unid=unid, f_cap=f_cap, cumple90=st["transito_p90_h"] <= H, tend=self.est.tendencia(as_of, pid, sol.corredor_id, sol.tipo_carga)))
        factibles.sort(key=lambda x: (x["total"], -(1 - x["p_nc"]), x["pid"]))   # desempate determinista
        return factibles, descartados, dict(as_of=as_of, H=H, nivel=nivel, CR=CR)

    # ---------- textos ----------
    def _alertas(self, f, ctx):
        cfg, st, a = self.cfg, f["st"], []
        if st["nivel_respaldo"] != "corredor":
            a.append(f"Sin historial en este corredor y carga: estimación con respaldo «{st['nivel_respaldo']}»")
        elif st["n_servicios"] < cfg["pocos_datos_n"]:
            a.append(f"Poco historial: {st['n_servicios']} servicios en el corredor")
        if f["tend"] > cfg["tendencia_umbral"]:
            a.append(f"Tendencia a empeorar: retrasos de los últimos {cfg.get('tendencia_ventana_dias', 30)} días +{f['tend']*100:.0f} pts frente a su año anterior")
        if st["transito_p90_h"] > ctx["H"]:
            a.append(f"Plazo en riesgo: P90 del tránsito {st['transito_p90_h']:.0f} h > plazo {ctx['H']:.0f} h")
        if f["cuota"] > cfg["concentracion_umbral"]:
            a.append(f"Concentración: {f['cuota']*100:.0f} % del volumen de {cfg['concentracion_ventana_dias']} días")
        if f["unid"] is None:
            a.append("Capacidad no confirmada: sin reporte del proveedor")
        else:
            dias = (ctx["as_of"] - f["f_cap"]).days
            if dias > cfg["capacidad_vieja_dias"]:
                a.append(f"Capacidad no confirmada: último reporte hace {dias} días")
            elif f["unid"] == 1:
                a.append("Capacidad justa: 1 unidad disponible")
        return a

    def _factores(self, f, otro, pos_otro):
        filas = []
        for k, nom in COMP_NOMBRE.items():
            d = getattr(f["des"], k) - getattr(otro["des"], k)
            if abs(d) >= 20_000:
                filas.append((abs(d), f"{nom}: {cop(abs(d))} {'menos' if d < 0 else 'más'} que #{pos_otro} ({otro['nombre']})"))
        filas.sort(key=lambda x: (-x[0], x[1]))
        dt = f["total"] - otro["total"]
        return [f"Costo esperado {cop(abs(dt))} {'menor' if dt <= 0 else 'mayor'} que #{pos_otro} ({otro['nombre']})"] + [t for _, t in filas[:3]]

    # ---------- interfaz MotorDecision ----------
    def recomendar(self, sol: SolicitudIn) -> RecomendacionOut:
        t0 = time.perf_counter()
        cfg = self.cfg
        factibles, descartados, ctx = self.evaluar(sol)
        top = factibles[:3]
        ranking = []
        for i, f in enumerate(top):
            st = f["st"]
            otro, pos = (factibles[i + 1], i + 2) if i + 1 < len(factibles) else ((factibles[i - 1], i) if i > 0 else (None, None))
            ranking.append(ProveedorEvaluado(
                posicion=i + 1, proveedor_id=f["pid"], nombre=f["nombre"], costo_esperado=f["total"], desglose=f["des"],
                margen_esperado=int(sol.tarifa_cliente - f["total"]), p_a_tiempo=round(1 - f["p_nc"], 4),
                ic90_p_a_tiempo=(round(f["ic_at"][0], 4), round(f["ic_at"][1], 4)),
                transito_p50_h=round(st["transito_p50_h"], 1), transito_p90_h=round(st["transito_p90_h"], 1),
                n_servicios_corredor=int(st["n_servicios"]), indice_dureza=st["indice_dureza"], banda_dureza=st["banda_dureza"],
                capacidad_unidades=f["unid"], alertas=self._alertas(f, ctx),
                factores_clave=self._factores(f, otro, pos) if otro else ["Único proveedor factible"]))
        motivos, escalar = [], False
        if ctx["nivel"] == "Urgente": motivos.append("urgente")
        if not top:
            motivos.append("sin_opcion"); escalar = True
        else:
            if len(top) > 1 and (top[1]["total"] - top[0]["total"]) / top[0]["total"] < cfg["empate_tecnico_pct"]:
                motivos.append("empate_tecnico")
            if not any(f["cumple90"] for f in factibles):
                motivos.append("sin_candidato_en_plazo"); escalar = True
            if sol.tarifa_cliente - top[0]["total"] < 0:
                motivos.append("margen_negativo"); escalar = True
        # confianza: evidencia del Top-1 y separacion frente al Top-2
        if top:
            n1 = top[0]["st"]["n_servicios"] if top[0]["st"]["nivel_respaldo"] == "corredor" else 0
            gap = (top[1]["total"] - top[0]["total"]) / top[0]["total"] if len(top) > 1 else 1.0
            confianza = round(0.6 * n1 / (n1 + cfg["pocos_datos_n"]) + 0.4 * min(1.0, gap / (2 * cfg["empate_tecnico_pct"])), 3)
        else:
            confianza = 0.0
        if top and confianza < cfg["confianza_baja"]: motivos.append("confianza_baja")
        sug = self._sugerencia(sol, factibles, ctx)
        out = RecomendacionOut(
            recomendacion_id=self._id(sol), solicitud_id=sol.solicitud_id, modelo_version=self.modelo_version, motor="A_propio",
            ranking=ranking, descartados=descartados, requiere_revision=bool(motivos), motivos_revision=motivos,
            escalar_gerencia=escalar, sugerencia_prueba=sug, confianza=confianza, explicacion_texto=self._texto(top, factibles, descartados, ctx, sol),
            latencia_ms=None, generado_en=ctx["as_of"].to_pydatetime())
        out.latencia_ms = round((time.perf_counter() - t0) * 1000, 2)
        return out

    def _sugerencia(self, sol, factibles, ctx):
        cfg = self.cfg
        if ctx["nivel"] != "Flexible" or sol.tipo_carga != "general" or len(factibles) < 2:
            return None
        cli = self.base.clientes.prioridad.get(sol.cliente_id, 3)
        if cli == 1:          # cliente clave: no se experimenta
            return None
        tope = factibles[0]["total"] * (1 + cfg["sugerencia_max_sobrecosto_pct"])
        cand = [f for f in factibles[1:] if f["st"]["n_servicios"] < cfg["pocos_datos_n"] and f["total"] <= tope and f["cumple90"] is not None]
        if not cand:
            return None
        f = cand[0]
        return SugerenciaPrueba(proveedor_id=f["pid"], razon=(
            f"{f['nombre']} tiene solo {f['st']['n_servicios']} servicios en este corredor; asignarle este servicio Flexible de bajo riesgo "
            f"cuesta {cop(f['total'] - factibles[0]['total'])} más en costo esperado y ayudaría a evaluarlo. Decide la persona."))

    def _texto(self, top, factibles, descartados, ctx, sol):
        if not top:
            return (f"Ningún proveedor puede atender la solicitud: {len(descartados)} descartados por reglas duras. "
                    "Se requiere gestión de la excepción (vehículo alterno, dividir la carga o mover la fecha).")
        a = top[0]
        t = f"Se recomienda {a['nombre']} con costo esperado {cop(a['total'])} y P(a tiempo) {1 - a['p_nc']:.0%} ({a['st']['n_servicios']} servicios en el corredor)."
        if len(top) > 1:
            b = top[1]
            comps = sorted(COMP_NOMBRE, key=lambda k: getattr(a["des"], k) - getattr(b["des"], k))
            k = comps[0]
            t += (f" Supera a {b['nombre']} por {cop(b['total'] - a['total'])}, sobre todo por {COMP_NOMBRE[k].lower()}"
                  f" ({cop(getattr(b['des'], k) - getattr(a['des'], k))}).")
        barato = min(factibles, key=lambda x: (x["des"].precio, x["pid"]))
        if barato["pid"] != a["pid"]:
            t += f" El más barato ({barato['nombre']}, {cop(barato['des'].precio)}) sale más caro en costo esperado por su riesgo de retraso o incertidumbre."
        t += f" Nivel {ctx['nivel']}: un retraso cuesta {cop(ctx['CR'])}."
        return t

    def _id(self, sol):
        d = sol.model_dump(mode="json")
        h = hashlib.sha1((json.dumps(d, sort_keys=True) + self.modelo_version).encode()).hexdigest()[:12]
        return f"REC-{h}"


if __name__ == "__main__":   # demostracion rapida
    import sqlite3, sys
    from engine.datos import DB_DEFECTO
    sid = sys.argv[1] if len(sys.argv) > 1 else None
    con = sqlite3.connect(DB_DEFECTO)
    q = "SELECT * FROM solicitud WHERE fase='prueba' AND tipo_carga='general' AND corredor_id='C1' ORDER BY solicitud_id LIMIT 1" if not sid else f"SELECT * FROM solicitud WHERE solicitud_id='{sid}'"
    r = dict(zip([c[0] for c in con.execute(q).description], con.execute(q).fetchone()))
    m = MotorA()
    for nivel in ("Flexible", "Estandar", "Urgente"):
        sol = SolicitudIn(**{k: r[k] for k in ("solicitud_id", "cliente_id", "corredor_id", "tipo_vehiculo_req", "tipo_carga", "peso_ton", "fecha_cargue", "plazo_entrega", "tarifa_cliente")},
                          mercancia_peligrosa=bool(r["mercancia_peligrosa"]), nivel_servicio=nivel)
        o = m.recomendar(sol)
        print(f"\n== {nivel} · {sol.solicitud_id} {sol.corredor_id} {sol.tipo_vehiculo_req} · {o.latencia_ms} ms · revisión={o.motivos_revision} · confianza={o.confianza}")
        for p in o.ranking:
            d = p.desglose
            print(f"  {p.posicion}. {p.nombre:20s} total {cop(p.costo_esperado):>12s} = precio {cop(d.precio)} + retraso {cop(d.retraso_esperado)} + inc {cop(d.incidente_esperado)} + incert {cop(d.incertidumbre)} + conc {cop(d.concentracion)} | P(a tiempo) {p.p_a_tiempo:.0%} n={p.n_servicios_corredor} {p.banda_dureza}")
        print("  ", o.explicacion_texto)
