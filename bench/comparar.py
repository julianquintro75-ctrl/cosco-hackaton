"""Paso 13 · Banco de comparacion: Motor A (propio) frente a B (Jev, TypeSafe) y C (LLM).
Todos reciben SolicitudIn y devuelven RecomendacionOut (contrato MotorDecision).
  A  · reglas duras + bayesiano + costo esperado (determinista).
  B  · Jev: recibe el estado YA RESUMIDO de los proveedores factibles (los numeros los calcula nuestro codigo) y una pregunta
       Choice; devuelve la opcion elegida, probabilidades y confianza. API oficial: POST https://api.typesafe.ai/v1/systemone,
       cabecera Authorization: Bearer $TYPESAFE_API_KEY, version fijada con $JEV_MODEL (por defecto jev-1.13.0).
  C  · LLM: NO decide el ranking. Redacta la explicacion y critica el Top-3 de A a partir del desglose.
       API de Anthropic (Messages) con $ANTHROPIC_API_KEY y modelo fijado con $LLM_MODEL.
Si falta una clave, ese motor queda «no medido»: no se inventan resultados.
Metricas sobre 500 solicitudes (fase de prueba + ultimo trimestre): arrepentimiento con la verdad oculta (solo evaluacion),
% de acuerdo entre motores, % a revision, latencia p50/p95, tokens y costo. Robustez: orden y nombres de proveedores,
proveedores irrelevantes y 20 repeticiones de la misma solicitud.
Uso: python bench/comparar.py [--n 500] [--sin-red]"""
from __future__ import annotations
import argparse, copy, json, os, random, sqlite3, string, sys, time
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ)); sys.path.insert(0, str(RAIZ / "seed")); sys.path.insert(0, str(RAIZ / "scripts"))
import numpy as np
import pandas as pd

from contratos.contracts import MotorDecision, ProveedorEvaluado, RecomendacionOut, SolicitudIn
from engine.datos import Base, DB_DEFECTO, cargar_config
from engine.motor_a import MotorA, cop
from backtest import CAMPOS, costo_real          # verdad oculta: SOLO para evaluar

def _cargar_env(ruta: Path) -> None:
    """Lee KEY=valor de .env sin pisar variables ya definidas (sin dependencias; el .env no se versiona)."""
    if not ruta.is_file():
        return
    for linea in ruta.read_text(encoding="utf-8").splitlines():
        linea = linea.strip()
        if linea and not linea.startswith("#") and "=" in linea:
            k, v = linea.split("=", 1)
            if v.strip().strip("\"'"):
                os.environ.setdefault(k.strip(), v.strip().strip("\"'"))


_cargar_env(RAIZ / ".env")

PRECIO_JEV_USD_MTOK = 0.042        # precio publicado por TypeSafe (entrada; salida gratis)
PRECIO_LLM_USD_MTOK = (3.0, 15.0)  # hipotetico (entrada, salida) hasta fijar el modelo real; ver seccion 13.4 del PDF


class NoMedido(RuntimeError):
    """El motor no se pudo ejecutar (sin clave o sin red). Se reporta como «no medido»."""


# ---------------------------------------------------------------- Motor B · Jev
class MotorB_Jev(MotorDecision):
    nombre = "B_jev"
    URL = "https://api.typesafe.ai/v1/systemone"

    def __init__(self, motor_a: MotorA, modelo: str | None = None, timeout: float = 10.0):
        self.a = motor_a
        self.modelo = modelo or os.environ.get("JEV_MODEL", "jev-1.13.0")    # version FIJADA
        self.clave = os.environ.get("TYPESAFE_API_KEY")
        self.timeout = timeout
        self.tokens = 0

    def estado(self, sol: SolicitudIn, factibles: list[dict], etiquetas: list[str]) -> str:
        """Estado en texto: solo hechos ya calculados por nuestro codigo (Jev no es calculadora)."""
        nivel = sol.nivel_servicio.value if hasattr(sol.nivel_servicio, "value") else sol.nivel_servicio
        ctx = {"H": (sol.plazo_entrega - sol.fecha_cargue).total_seconds() / 3600, "as_of": pd.Timestamp(sol.as_of or sol.fecha_cargue)}
        alertas = lambda f: (f"; alertas: {'; '.join(a)}" if (a := self.a._alertas(f, ctx)) else "")
        lin = [f"Solicitud de transporte terrestre en Colombia. Corredor {sol.corredor_id}, vehículo {sol.tipo_vehiculo_req}, carga {sol.tipo_carga}, "
               f"nivel de servicio {nivel} (un retraso cuesta {cop(self.a.cfg['costo_retraso'][nivel])}). "
               f"Plazo de entrega: {(sol.plazo_entrega - sol.fecha_cargue).total_seconds() / 3600:.0f} horas.",
               "Proveedores que cumplen las reglas duras (vehículo, certificación, cobertura y capacidad):"]
        for et, f in zip(etiquetas, factibles):
            st = f["st"]
            lin.append(f"- {et}: precio {cop(f['des'].precio)}; probabilidad de llegar a tiempo {1 - f['p_nc']:.0%} "
                       f"(intervalo 90 % {f['ic_at'][0]:.0%}–{f['ic_at'][1]:.0%}); tránsito típico {st['transito_p50_h']:.0f} h y pesimista P90 {st['transito_p90_h']:.0f} h; "
                       f"{st['n_servicios']} servicios previos en el corredor; tasa de incidentes {st['tasa_incidente']:.1%}; "
                       f"participación en el volumen del último mes {f['cuota']:.0%}" + alertas(f))
        return "\n".join(lin)

    def preguntar(self, estado: str, etiquetas: list[str]) -> dict:
        if not self.clave:
            raise NoMedido("falta TYPESAFE_API_KEY")
        import httpx
        body = {"model": self.modelo, "state": estado, "questions": {"proveedor": {
            "type": "choice",
            "instructions": "¿Qué proveedor conviene asignar para minimizar el costo total esperado (precio más el costo esperado de retrasos e incidentes), respetando el nivel de servicio?",
            "criteria": {e: None for e in etiquetas}}}}
        try:
            r = httpx.post(self.URL, json=body, headers={"Authorization": f"Bearer {self.clave}"}, timeout=self.timeout)
        except httpx.HTTPError as e:
            raise NoMedido(f"sin conexión con TypeSafe: {e}") from e
        if r.status_code != 200:
            raise NoMedido(f"TypeSafe respondió {r.status_code}: {r.text[:200]}")
        j = r.json()
        self.tokens += int(j.get("usage", {}).get("input_tokens", 0))
        return j

    def recomendar(self, sol: SolicitudIn, permutar: int | None = None, renombrar: bool = False) -> RecomendacionOut:
        t0 = time.perf_counter()
        factibles, descartados, ctx = self.a.evaluar(sol)          # filtros duros: los mismos para todos los motores
        orden = list(range(len(factibles)))
        if permutar is not None:
            random.Random(permutar).shuffle(orden)
        fs = [factibles[i] for i in orden]
        etiquetas = ([f"Opción {string.ascii_uppercase[i]}" for i in range(len(fs))] if renombrar else [f["nombre"] for f in fs])
        if not fs:
            return self.a.recomendar(sol).model_copy(update={"motor": "B_jev"})
        j = self.preguntar(self.estado(sol, fs, etiquetas), etiquetas)
        ans = j["answers"]["proveedor"]
        probs = ans.get("probabilities", {})
        if isinstance(probs, list):
            probs = dict(zip(etiquetas, probs))
        rank = sorted(range(len(fs)), key=lambda i: (-float(probs.get(etiquetas[i], 0)), etiquetas[i] != ans["choice"]))
        ranking = []
        for pos, i in enumerate(rank[:3], 1):
            f = fs[i]; st = f["st"]
            ranking.append(ProveedorEvaluado(posicion=pos, proveedor_id=f["pid"], nombre=f["nombre"], costo_esperado=f["total"], desglose=f["des"],
                                             margen_esperado=int(sol.tarifa_cliente - f["total"]), p_a_tiempo=round(1 - f["p_nc"], 4), ic90_p_a_tiempo=f["ic_at"],
                                             transito_p50_h=st["transito_p50_h"], transito_p90_h=st["transito_p90_h"], n_servicios_corredor=int(st["n_servicios"]),
                                             factores_clave=[f"Jev P={float(probs.get(etiquetas[i], 0)):.2f}"]))
        conf = float(ans.get("confidence", 0))
        return RecomendacionOut(recomendacion_id=f"JEV-{sol.solicitud_id}", solicitud_id=sol.solicitud_id, modelo_version=j.get("model", self.modelo),
                                motor="B_jev", ranking=ranking, descartados=descartados, requiere_revision=conf < 0.6,
                                motivos_revision=["confianza_baja"] if conf < 0.6 else [], confianza=min(max(conf, 0), 1),
                                latencia_ms=round((time.perf_counter() - t0) * 1000, 2), generado_en=ctx["as_of"].to_pydatetime())


# ---------------------------------------------------------------- Motor C · LLM
class MotorC_LLM(MotorDecision):
    """Solo explica y critica el Top-3 que calculó A. Nunca cambia el ranking."""
    nombre = "C_llm"

    def __init__(self, motor_a: MotorA, modelo: str | None = None, timeout: float = 60.0):
        self.a = motor_a
        self.modelo = modelo or os.environ.get("LLM_MODEL", "claude-haiku-5-5")
        self.clave = os.environ.get("ANTHROPIC_API_KEY")
        self.timeout = timeout
        self.tokens_in = self.tokens_out = 0

    def recomendar(self, sol: SolicitudIn) -> RecomendacionOut:
        t0 = time.perf_counter()
        base = self.a.recomendar(sol)
        if not self.clave:
            raise NoMedido("falta ANTHROPIC_API_KEY")
        import httpx
        datos = {"ranking": [p.model_dump(include={"posicion", "nombre", "costo_esperado", "desglose", "p_a_tiempo", "n_servicios_corredor", "alertas"}) for p in base.ranking],
                 "descartados": [d.model_dump() for d in base.descartados], "motivos_revision": base.motivos_revision}
        prompt = ("Eres analista de operaciones de transporte terrestre. Con el desglose de costo esperado (en pesos colombianos) que calculó el sistema, "
                  "escribe en español: (1) una explicación de 3 frases de por qué el #1 queda por encima del #2 y del #3; (2) una crítica: "
                  "contradicciones o riesgos que la persona debería revisar. No recalcules ni cambies el orden.\n\n" + json.dumps(datos, ensure_ascii=False, default=str))
        try:
            r = httpx.post(os.environ.get("ANTHROPIC_BASE_URL", "https://api.anthropic.com").rstrip("/") + "/v1/messages",
                           headers={"x-api-key": self.clave, "anthropic-version": "2023-06-01"},
                           json={"model": self.modelo, "max_tokens": 500, "messages": [{"role": "user", "content": prompt}]}, timeout=self.timeout)
        except httpx.HTTPError as e:
            raise NoMedido(f"sin conexión con el LLM: {e}") from e
        if r.status_code != 200:
            raise NoMedido(f"el LLM respondió {r.status_code}: {r.text[:200]}")
        j = r.json()
        self.tokens_in += j["usage"]["input_tokens"]; self.tokens_out += j["usage"]["output_tokens"]
        texto = "".join(b.get("text", "") for b in j["content"])
        return base.model_copy(update={"motor": "C_llm", "explicacion_texto": texto, "modelo_version": f"{base.modelo_version}+{j.get('model', self.modelo)}",
                                       "latencia_ms": round((time.perf_counter() - t0) * 1000, 2)})


# ---------------------------------------------------------------- banco
def cargar_solicitudes(db, n, semilla=7):
    con = sqlite3.connect(db); con.row_factory = sqlite3.Row
    prueba = [dict(r) for r in con.execute("SELECT * FROM solicitud WHERE fase='prueba' ORDER BY solicitud_id")]
    trim = [dict(r) for r in con.execute("SELECT * FROM solicitud WHERE fase='historico' AND substr(fecha_solicitud,1,10) BETWEEN '2026-07-01' AND '2026-09-30' ORDER BY solicitud_id")]
    resto = max(n - len(prueba), 0)
    elegidos = prueba[:n] + sorted(random.Random(semilla).sample(trim, min(resto, len(trim))), key=lambda r: r["solicitud_id"])
    return elegidos


def a_solicitud(r) -> SolicitudIn:
    return SolicitudIn(**{k: r[k] for k in CAMPOS}, mercancia_peligrosa=bool(r["mercancia_peligrosa"]), as_of=r["fecha_solicitud"])


def correr(motor, sols, reqs, cfg, A_ref):
    """Ejecuta un motor. Devuelve dict de metricas o {'estado': 'no medido', 'motivo': ...}."""
    filas, lat = [], []
    for s, r in zip(sols, reqs):
        try:
            o = motor.recomendar(s)
        except NoMedido as e:
            return {"estado": "no medido", "motivo": str(e)}
        fact = A_ref[s.solicitud_id]
        if not fact or not o.ranking:
            continue
        d = pd.Timestamp(r["fecha_cargue"]).date()
        reales = {f["pid"]: costo_real(f["pid"], r["corredor_id"], d, f["des"].precio, r["nivel_servicio"], cfg) for f in fact}
        top1 = o.ranking[0].proveedor_id
        filas.append(dict(sid=s.solicitud_id, nivel=r["nivel_servicio"], top1=top1, regret=reales[top1] - min(reales.values()),
                          optimo=reales[top1] - min(reales.values()) < 1, revision=o.requiere_revision))
        lat.append(o.latencia_ms or 0)
    df = pd.DataFrame(filas)
    return {"estado": "medido", "df": df, "regret": df.regret.mean(), "pct_optimo": df.optimo.mean() * 100, "pct_revision": df.revision.mean() * 100,
            "lat_p50": float(np.percentile(lat, 50)), "lat_p95": float(np.percentile(lat, 95)), "n": len(df)}


def robustez_A(base: Base, cfg, sols, n=60):
    """Orden y nombres de proveedores, proveedores irrelevantes y 20 repeticiones: ¿cambia el Top-3 de A?"""
    ref = MotorA(base, cfg)
    top = lambda m, s: [p.proveedor_id for p in m.recomendar(s).ranking]
    muestra = sols[:n]
    base_top = {s.solicitud_id: top(ref, s) for s in muestra}
    res = {}
    # 1) orden distinto de los proveedores en la base
    b2 = copy.copy(base); b2.proveedores = base.proveedores.sample(frac=1, random_state=3).reset_index(drop=True)
    res["Orden de proveedores cambiado"] = np.mean([top(MotorA(b2, cfg), s) == base_top[s.solicitud_id] for s in muestra])
    # 2) nombres distintos (mismos ids)
    b3 = copy.copy(base); b3.proveedores = base.proveedores.assign(nombre=[f"Proveedor {i:02d}" for i in range(len(base.proveedores))])
    res["Nombres de proveedores cambiados"] = np.mean([top(MotorA(b3, cfg), s) == base_top[s.solicitud_id] for s in muestra])
    # 3) proveedores irrelevantes (sin cobertura ni flota): deben salir como descartados sin mover el ranking
    extra = pd.DataFrame([dict(proveedor_id=f"PX{i}", nombre=f"Irrelevante {i}", nit=None, ciudad_base="-", fecha_alta="2020-01-01", activo=1) for i in range(5)])
    b4 = copy.copy(base); b4.proveedores = pd.concat([base.proveedores, extra], ignore_index=True)
    res["5 proveedores irrelevantes añadidos"] = np.mean([top(MotorA(b4, cfg), s) == base_top[s.solicitud_id] for s in muestra])
    # 4) misma solicitud repetida 20 veces
    rep = []
    for s in muestra[:20]:
        outs = {json.dumps(ref.recomendar(s).model_dump(mode="json", exclude={"latencia_ms"}), sort_keys=True) for _ in range(20)}
        rep.append(len(outs) == 1)
    res["Misma solicitud ×20 (JSON idéntico)"] = np.mean(rep)
    return res


def robustez_B(motorB: MotorB_Jev, sols, n=30):
    try:
        ok_orden, ok_nombre, ok_rep = [], [], []
        for s in sols[:n]:
            t0 = motorB.recomendar(s).ranking[0].proveedor_id
            ok_orden.append(motorB.recomendar(s, permutar=11).ranking[0].proveedor_id == t0)
            ok_nombre.append(motorB.recomendar(s, renombrar=True).ranking[0].proveedor_id == t0)
        for s in sols[:5]:
            ok_rep.append(len({motorB.recomendar(s).ranking[0].proveedor_id for _ in range(20)}) == 1)
        return {"Orden de proveedores cambiado": np.mean(ok_orden), "Nombres de proveedores cambiados": np.mean(ok_nombre),
                "Misma solicitud ×20 (mismo Top-1)": np.mean(ok_rep)}
    except NoMedido:
        return None


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--n", type=int, default=500); ap.add_argument("--db", default=str(DB_DEFECTO))
    a = ap.parse_args()
    cfg = cargar_config(); base = Base(a.db)
    reqs = cargar_solicitudes(a.db, a.n); sols = [a_solicitud(r) for r in reqs]
    A = MotorA(base, cfg)
    A_ref = {s.solicitud_id: A.evaluar(s)[0] for s in sols}
    print(f"{len(sols)} solicitudes ({sum(r['fase'] == 'prueba' for r in reqs)} de la fase de prueba)")

    R = {"A · Nuestro (bayesiano + costo esperado)": correr(A, sols, reqs, cfg, A_ref)}
    B = MotorB_Jev(A); C = MotorC_LLM(A)
    R[f"B · Jev ({B.modelo})"] = correr(B, sols, reqs, cfg, A_ref)
    R[f"C · LLM ({C.modelo}, solo explica)"] = correr(C, sols, reqs, cfg, A_ref)

    # referencias simples (mismos factibles)
    class _Pol(MotorDecision):
        def __init__(s, f): s.f = f
        def recomendar(s, sol):
            fact = A_ref[sol.solicitud_id]; o = A.recomendar(sol)
            if not fact: return o
            p = s.f(sol, fact)
            orden = sorted(o.ranking, key=lambda x: x.proveedor_id != p)
            if p not in [x.proveedor_id for x in o.ranking]:
                f = next(x for x in fact if x["pid"] == p)
                orden = [o.ranking[0].model_copy(update={"proveedor_id": p, "nombre": f["nombre"]})]
            return o.model_copy(update={"ranking": orden, "requiere_revision": False})
    R["Siempre el más barato"] = correr(_Pol(lambda s, f: min(f, key=lambda x: (x["des"].precio, x["pid"]))["pid"]), sols, reqs, cfg, A_ref)
    rng = random.Random(1)
    R["Aleatorio"] = correr(_Pol(lambda s, f: rng.choice(f)["pid"]), sols, reqs, cfg, A_ref)
    for k in ("Siempre el más barato", "Aleatorio"):
        R[k]["pct_revision"] = None

    # acuerdo con A
    dA = R["A · Nuestro (bayesiano + costo esperado)"]["df"].set_index("sid").top1
    for k, v in R.items():
        if v["estado"] == "medido":
            v["acuerdo_A"] = (v["df"].set_index("sid").top1.reindex(dA.index) == dA).mean() * 100

    rob_A = robustez_A(base, cfg, sols)
    rob_B = robustez_B(B, sols) if R[f"B · Jev ({B.modelo})"]["estado"] == "medido" else None

    # costo
    costo = {"A · Nuestro (bayesiano + costo esperado)": "≈ 0 (cómputo propio)"}
    kB, kC = f"B · Jev ({B.modelo})", f"C · LLM ({C.modelo}, solo explica)"
    if R[kB]["estado"] == "medido":
        costo[kB] = f"{B.tokens / R[kB]['n']:.0f} tokens/decisión · US$ {B.tokens * PRECIO_JEV_USD_MTOK / 1e6 / R[kB]['n'] * 1000:.4f} por 1.000"
    if R[kC]["estado"] == "medido":
        usd = (C.tokens_in * PRECIO_LLM_USD_MTOK[0] + C.tokens_out * PRECIO_LLM_USD_MTOK[1]) / 1e6
        costo[kC] = f"{(C.tokens_in + C.tokens_out) / R[kC]['n']:.0f} tokens/decisión · US$ {usd / R[kC]['n'] * 1000:.2f} por 1.000 (precio hipotético)"

    escribir(R, rob_A, rob_B, costo, len(sols), sum(r["fase"] == "prueba" for r in reqs))


def escribir(R, rob_A, rob_B, costo, n, n_prueba):
    pct = lambda x: "—" if x is None else f"{x:.1f} %"
    L = ["# Paso 13 · Banco de comparación: Motor A frente a Jev y un LLM", "",
         f"{n} solicitudes ({n_prueba} de la fase de prueba, 1–15 oct 2026, y el resto muestreadas con semilla fija de jul–sep 2026). Datos **sintéticos**.",
         "Arrepentimiento = costo real esperado del Top-1 − costo del mejor proveedor factible, con la verdad oculta del simulador (solo evaluación).",
         "Todos los motores ven los mismos proveedores factibles: las reglas duras las aplica nuestro código.", "",
         "| Motor | Arrepentimiento medio | Elige el óptimo | Acuerdo con A (Top-1) | % a revisión | Latencia p50 / p95 | Costo |",
         "|---|---|---|---|---|---|---|"]
    for k, v in R.items():
        if v["estado"] != "medido":
            L.append(f"| {k} | no medido | no medido | no medido | no medido | no medido | no medido ({v['motivo']}) |")
        else:
            lat = f"{v['lat_p50']:.1f} / {v['lat_p95']:.1f} ms" if not k.startswith(("Siempre", "Aleatorio")) else "—"
            L.append(f"| {k} | {cop(v['regret'])} | {v['pct_optimo']:.1f} % | {v['acuerdo_A']:.1f} % | {pct(v['pct_revision'])} | {lat} | {costo.get(k, '—')} |")
    vA = next(iter(R.values()))
    L += ["", "### Motor A por nivel de servicio", "", "| Nivel | n | Arrepentimiento medio | Elige el óptimo | % a revisión |", "|---|---|---|---|---|"]
    for nv, g in vA["df"].groupby("nivel"):
        L.append(f"| {nv} | {len(g)} | {cop(g.regret.mean())} | {g.optimo.mean() * 100:.1f} % | {g.revision.mean() * 100:.1f} % |")
    L += ["", "## Robustez", "", "| Prueba | A · Nuestro | B · Jev |", "|---|---|---|"]
    for k, v in rob_A.items():
        vb = "no medido" if rob_B is None else (f"{rob_B[k] * 100:.0f} % igual" if k in rob_B else ("no aplica" if "irrelevantes" in k else f"{rob_B.get(k.replace('JSON idéntico', 'mismo Top-1'), float('nan')) * 100:.0f} % igual"))
        L.append(f"| {k} | {v * 100:.0f} % igual | {vb} |")
    sin_medir = [k.split(" (")[0] for k, v in R.items() if v["estado"] != "medido"]
    L += ["", "## Lectura", ""]
    if sin_medir:
        L.append("- No medidos en esta corrida: " + ", ".join(sin_medir) + ". **No se afirma ninguna ventaja ni desventaja de un motor hasta medirlo** con esta misma batería.")
        L.append("- Para medirlos: `TYPESAFE_API_KEY` (y opcionalmente `JEV_MODEL=jev-1.13.0`) para Jev; `ANTHROPIC_API_KEY` y `LLM_MODEL` para el LLM; luego `python bench/comparar.py`.")
    else:
        L.append("- Todos los motores se midieron con la misma batería de solicitudes.")
    L += [
          "- El motor A es determinista: el Top-3 no depende del orden ni de los nombres de los proveedores, y los proveedores irrelevantes salen como descartados con motivo.",
          "- Los datos simulados siguen una estructura parecida a la que supone el motor A, así que su ventaja frente a las referencias probablemente está exagerada respecto a datos reales.",
          "", "![Comparación](../bench/comparacion.png)"]
    out = RAIZ / "reportes" / "paso13_banco.md"; out.write_text("\n".join(L) + "\n", encoding="utf8")
    print("\n".join(L))
    grafica(R)


def grafica(R):
    import matplotlib; matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    nombres = list(R); vals = [R[k]["regret"] if R[k]["estado"] == "medido" else 0 for k in nombres]
    fig, ax = plt.subplots(figsize=(9, 3.8), dpi=150)
    y = np.arange(len(nombres))[::-1]
    col = ["#2a6fdb" if k.startswith("A ") else "#b9b6ad" for k in nombres]
    ax.barh(y, vals, color=col, height=0.6)
    for yi, k, v in zip(y, nombres, vals):
        ax.text(v + max(vals) * 0.01, yi, "no medido" if R[k]["estado"] != "medido" else cop(v), va="center", fontsize=9, color="#333")
    ax.set_yticks(y, [k.split(" (")[0] for k in nombres], fontsize=9)
    ax.set_xlabel("Arrepentimiento medio por servicio (COP, verdad oculta)")
    sin = [k.split(" ·")[0] for k in nombres if R[k]["estado"] != "medido"]
    ax.set_title("Arrepentimiento por motor (menor es mejor)" + (f"; sin medir: {', '.join(sin)} (falta clave de API)" if sin else ""), fontsize=10, loc="left")
    for s in ("top", "right"): ax.spines[s].set_visible(False)
    ax.xaxis.set_major_formatter(matplotlib.ticker.FuncFormatter(lambda v, _: f"{v/1000:,.0f} mil".replace(",", ".")))
    fig.tight_layout(); fig.savefig(RAIZ / "bench" / "comparacion.png"); plt.close(fig)


if __name__ == "__main__":
    main()
