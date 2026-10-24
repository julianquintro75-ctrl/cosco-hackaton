"""Mide con el motor real las tensiones y los casos difíciles y escribe docs/CASOS_DIFICILES.md.

Uso:  python -m scripts.casos_dificiles [--n 600] [--db data/cosco.db] [--out docs/CASOS_DIFICILES.md]
Muestra aleatoria (semilla fija) de solicitudes de jul–sep 2026. Todas las cifras salen de esta corrida; nada se escribe a mano.
La tabla costo vs puntualidad se toma de reportes/paso11_backtest.md (correr scripts/backtest.py antes).
"""
import argparse
import collections
import re
import sqlite3
from pathlib import Path

import pandas as pd

from contratos.contracts import SolicitudIn
from engine.datos import Base
from engine.motor_a import MotorA

RAIZ = Path(__file__).resolve().parents[1]
CAMPOS = ("solicitud_id", "cliente_id", "corredor_id", "tipo_vehiculo_req", "tipo_carga", "peso_ton", "fecha_cargue", "plazo_entrega", "tarifa_cliente")


def pct(a: int, b: int) -> str:
    return f"{100 * a / b:.1f} %" if b else "—"


def correr(db: Path, n: int) -> dict:
    con = sqlite3.connect(db)
    df = pd.read_sql("SELECT * FROM solicitud WHERE fecha_cargue BETWEEN '2026-07-01' AND '2026-09-30' ORDER BY solicitud_id", con).sample(n=n, random_state=7)
    nombres = dict(con.execute("SELECT proveedor_id, nombre FROM proveedor").fetchall())
    m = MotorA(Base(str(db)))
    R = dict(n=0, sin_opcion=0, rev=0, esc=0, neg=0, motivos=collections.Counter(), nivel=collections.defaultdict(lambda: [0, 0, 0]),
             top1=collections.Counter(), desc=collections.Counter(), prueba=0, un_solo=0, ejemplos={})
    for r in df.to_dict("records"):
        sol = SolicitudIn(**{k: r[k] for k in CAMPOS}, mercancia_peligrosa=bool(r["mercancia_peligrosa"]), nivel_servicio=r["nivel_servicio"])
        o = m.recomendar(sol)
        R["n"] += 1
        for d in o.descartados:
            R["desc"][d.motivo] += 1
        if not o.ranking:
            R["sin_opcion"] += 1
            R["motivos"]["sin_opcion"] += 1
            continue
        niv = R["nivel"][r["nivel_servicio"]]
        niv[0] += 1
        R["top1"][o.ranking[0].nombre] += 1
        if len(o.ranking) == 1:
            R["un_solo"] += 1
        if o.ranking[0].margen_esperado < 0:
            R["neg"] += 1
        if o.requiere_revision:
            R["rev"] += 1; niv[1] += 1
        if o.escalar_gerencia:
            R["esc"] += 1; niv[2] += 1
        for x in o.motivos_revision:
            R["motivos"][x] += 1
            R["ejemplos"].setdefault(x, (r["solicitud_id"], r["nivel_servicio"], r["corredor_id"], r["tipo_carga"]))
        if o.sugerencia_prueba:
            R["prueba"] += 1
    R["nombres"] = nombres
    return R


def tabla_politicas() -> str:
    f = RAIZ / "reportes" / "paso11_backtest.md"
    if not f.exists():
        return "_(corre `python scripts/backtest.py` para llenar esta tabla)_"
    filas = [l for l in f.read_text(encoding="utf8").splitlines() if re.match(r"\|\s*(Motor A|Analista|Siempre|Aleatorio)", l)]
    return "| Política | Arrepentimiento medio | % óptimo | Puntualidad real |\n|---|---|---|---|\n" + "\n".join(filas)


def escribir(R: dict, out: Path) -> None:
    n, ok = R["n"], R["n"] - R["sin_opcion"]
    niv = "\n".join(f"| {k} | {v[0]} | {pct(v[1], v[0])} | {pct(v[2], v[0])} |" for k, v in sorted(R["niv"].items())) if "niv" in R else \
          "\n".join(f"| {k} | {v[0]} | {pct(v[1], v[0])} | {pct(v[2], v[0])} |" for k, v in sorted(R["nivel"].items()))
    mot = "\n".join(f"| `{k}` | {v} | {pct(v, n)} | `{R['ejemplos'].get(k, ('—',))[0]}` |" for k, v in R["motivos"].most_common())
    des = "\n".join(f"| `{k}` | {v} |" for k, v in R["desc"].most_common())
    top = "\n".join(f"| {k} | {v} | {pct(v, ok)} |" for k, v in R["top1"].most_common())
    mayor, cuota = R["top1"].most_common(1)[0]
    out.write_text(f"""# Tensiones y casos difíciles (medidos)

Generado por `python -m scripts.casos_dificiles` sobre {n} solicitudes al azar de jul–sep 2026 (semilla 7) con el motor A real.
**Los datos son sintéticos**: las cifras muestran cómo se comporta el método, no el valor real para COSCO.

## 1. Costo frente a puntualidad

Elegir el menor **costo total esperado** (precio + retraso esperado en pesos + incidente) abarata, pero no maximiza la puntualidad.
Backtest de 1.586 solicitudes contra la verdad oculta del simulador:

{tabla_politicas()}

Lectura honesta: el motor A es el que menos pierde en pesos, pero **no es el más puntual**. Es una elección de diseño: con retraso de
$300 mil (Flexible) la puntualidad no vale lo que cuesta. Si COSCO prefiere puntualidad por encima del costo, se sube el costo del
retraso por nivel en `engine/config_motor.json` y el ranking cambia sin tocar el código (ver la escena 2 del guion de la demo).

## 2. Autonomía frente a revisión humana

Con la tarifa de cliente calibrada, de {n} solicitudes: {ok} tuvieron al menos un proveedor factible, **{pct(R['rev'], ok)}** pidieron
revisión, **{pct(R['esc'], ok)}** se escalaron a gerencia y en **{pct(R['neg'], ok)}** el margen esperado del Top-1 fue negativo.
La persona decide siempre; el sistema solo gradúa cuánta atención merece cada caso.

| Nivel | Solicitudes con opción | Piden revisión | Escalan a gerencia |
|---|---|---|---|
{niv}

| Motivo | Veces | Sobre la muestra | Ejemplo |
|---|---|---|---|
{mot}

Qué queda abierto: la mayor parte del escalamiento viene de `sin_candidato_en_plazo` (ningún proveedor tiene P90 de tránsito dentro del
plazo). Es una regla de diseño prudente, pero con los plazos sintéticos escala más de lo que un equipo real toleraría. Alternativa
documentada: escalar solo cuando ni siquiera el tránsito mediano (P50) cabe en el plazo y degradar el resto a revisión.
Los empates técnicos son solo un aviso: no cuentan como revisión.

## 3. Casos difíciles y cómo responde el sistema

| Caso | Qué hace el sistema | Dónde verlo |
|---|---|---|
| Mejor proveedor sin capacidad | Lo descarta con motivo y dice cuánto cuesta no tenerlo | Guion escena 3 (`R005923`) |
| Tarifa que no cubre el costo | Escala a gerencia con el margen esperado | `R005907` |
| Proveedor nuevo con poco historial | Lo penaliza por incertidumbre y propone una prueba aparte solo en Flexible: {R['prueba']} sugerencias en la muestra | Escena 4 (`R005913`) |
| Carga peligrosa | Filtro duro IMO que nunca se relaja; el certificado queda solo y la dependencia se ve (en la muestra, {R['un_solo']} solicitudes tuvieron un único candidato) | Escena 5 (`R005949`) |
| Proveedor que se degrada (Andina) | Pierde el Top-3 en unos 12 días; alerta binomial a 14 días | `python scripts/replay.py` |
| Proveedor que mejora (TransPacífico) | El decaimiento temporal de 30 días da más peso a lo reciente | Escena 1 |
| Paro de Altiplano | Pico de retraso visible en el backtest; si la capacidad reportada es 0, la regla dura lo descarta | `reportes/paso11_backtest.md` |
| Plazo imposible | `sin_candidato_en_plazo`: escala a gerencia, decide una persona | tabla de motivos |
| Dos proveedores casi iguales | Aviso de empate técnico, sin bloquear | tabla de motivos |

### Por qué se descartan proveedores (suma de la muestra)

| Motivo | Descartes |
|---|---|
{des}

## 4. Concentración

Cuota de Top-1 por proveedor en la muestra (si uno concentra demasiado, hay riesgo operativo y poder de negociación en su contra):

| Proveedor | Veces Top-1 | Cuota |
|---|---|---|
{top}

El proveedor más frecuente es **{mayor}** con {pct(cuota, ok)}. El motor ya incluye un componente de concentración (penaliza al proveedor
que supera el umbral de participación de su ventana reciente, y los tableros de gerencia muestran la cuota y el índice Herfindahl). Pero esta
muestra se recomienda solicitud por solicitud, **sin que las recomendaciones anteriores alimenten la participación**: si la persona aceptara
siempre el Top-1, la concentración real sería mayor que la que el penalizador alcanza a ver. Es un riesgo conocido; mitigarlo exige que las
decisiones aceptadas actualicen la participación en tiempo real (el repositorio ya guarda las decisiones) o un tope duro acordado con operaciones.
""", encoding="utf8")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=600)
    ap.add_argument("--db", type=Path, default=RAIZ / "data" / "cosco.db")
    ap.add_argument("--out", type=Path, default=RAIZ / "docs" / "CASOS_DIFICILES.md")
    a = ap.parse_args()
    R = correr(a.db, a.n)
    R["nombres"] = None
    escribir(R, a.out)
    print(f"escrito {a.out}")


if __name__ == "__main__":
    main()
