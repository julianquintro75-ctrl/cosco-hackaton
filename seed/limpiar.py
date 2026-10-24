"""Limpieza de data/cosco_sucio.db -> data/cosco_limpio.db.
Detecta y corrige: (1) entregas anteriores al cargue, (2) a_tiempo vacio, (3) servicios duplicados (ids DUP...),
(4) nombres de proveedor con otro formato, (5) tarifas con un factor de 1000.
Uso: python seed/limpiar.py [sucio.db] [limpio.db] [--comparar data/cosco.db]"""
import argparse, re, shutil, sqlite3
from datetime import datetime, timedelta
from pathlib import Path

DATA = Path(__file__).resolve().parent.parent / "data"
ap = argparse.ArgumentParser()
ap.add_argument("sucio", nargs="?", default=str(DATA / "cosco_sucio.db"))
ap.add_argument("limpio", nargs="?", default=str(DATA / "cosco_limpio.db"))
ap.add_argument("--comparar", default=str(DATA / "cosco.db"), help="base de referencia para comparar conteos ('' para omitir)")
a = ap.parse_args()

shutil.copy(a.sucio, a.limpio)
con = sqlite3.connect(a.limpio); cur = con.cursor()
F = "%Y-%m-%dT%H:%M"
p = lambda s: datetime.fromisoformat(s)
iso = lambda d: d.strftime(F)
log = {}

# (3) duplicados: primero, para no corregir copias que se van a borrar
dups = [r[0] for r in cur.execute("SELECT servicio_id FROM servicio WHERE servicio_id LIKE 'DUP%'")]
# por si hubiera duplicados sin prefijo: misma solicitud, proveedor y cargue -> se queda el id menor
dups += [r[0] for r in cur.execute("""SELECT s.servicio_id FROM servicio s WHERE s.servicio_id NOT LIKE 'DUP%' AND s.cargue_real IS NOT NULL
    AND EXISTS (SELECT 1 FROM servicio t WHERE t.servicio_id NOT LIKE 'DUP%' AND t.solicitud_id=s.solicitud_id AND t.proveedor_id=s.proveedor_id
                AND t.cargue_real=s.cargue_real AND t.servicio_id<s.servicio_id)""")]
for sid in dups:
    cur.execute("DELETE FROM evento_servicio WHERE servicio_id=?", (sid,))
    cur.execute("DELETE FROM feedback WHERE servicio_id=?", (sid,))
    cur.execute("DELETE FROM servicio WHERE servicio_id=?", (sid,))
log["servicios duplicados eliminados"] = len(dups)

# (1) entrega antes del cargue: se reconstruye con los hitos GPS (hito k a 35 % y 70 % del viaje)
malas = cur.execute("""SELECT s.servicio_id, s.cargue_real, so.fecha_cargue FROM servicio s JOIN solicitud so USING(solicitud_id)
                       WHERE s.estado='ENTREGADO' AND s.entrega_real<=s.cargue_real""").fetchall()
rec = sin_gps = 0
for sid, cr, fc in malas:
    gps = cur.execute("SELECT fecha_hora, detalle FROM evento_servicio WHERE servicio_id=? AND tipo='GPS' ORDER BY fecha_hora", (sid,)).fetchall()
    ests = []
    for fh, det in gps:
        fr = {"hito 1": 0.35, "hito 2": 0.70}.get(det)
        if fr: ests.append((p(fh) - p(cr)) / fr)
    if ests and max(ests) > timedelta(0):
        dur = max(ests)  # el hito mas tardio tiene menos error de redondeo relativo
        # la duracion del viaje se cuenta desde el cargue programado de la solicitud (asi lo registra el sistema de origen)
        cur.execute("UPDATE servicio SET entrega_real=? WHERE servicio_id=?", (iso(p(fc) + dur), sid)); rec += 1
    else:  # sin GPS: se usa la duracion planeada y se marca
        ep = cur.execute("SELECT entrega_planeada FROM servicio WHERE servicio_id=?", (sid,)).fetchone()[0]
        cur.execute("UPDATE servicio SET entrega_real=? WHERE servicio_id=?", (ep, sid)); sin_gps += 1
log["entregas anteriores al cargue corregidas (con GPS)"] = rec
log["entregas anteriores al cargue corregidas (sin GPS, = planeada)"] = sin_gps

# (2) a_tiempo vacio o incoherente -> se recalcula con entrega_real <= entrega_planeada
n_null = cur.execute("SELECT COUNT(*) FROM servicio WHERE estado='ENTREGADO' AND a_tiempo IS NULL").fetchone()[0]
n_inc = cur.execute("SELECT COUNT(*) FROM servicio WHERE estado='ENTREGADO' AND a_tiempo IS NOT NULL AND a_tiempo<>(entrega_real<=entrega_planeada)").fetchone()[0]
cur.execute("UPDATE servicio SET a_tiempo=(entrega_real<=entrega_planeada) WHERE estado='ENTREGADO' AND (a_tiempo IS NULL OR a_tiempo<>(entrega_real<=entrega_planeada))")
log["a_tiempo vacio recalculado"] = n_null
log["a_tiempo incoherente recalculado (tras corregir entregas)"] = n_inc

# (4) nombres de proveedor: quitar sufijos societarios, espacios y MAYUSCULAS
def normalizar(n):
    if not n.strip().isupper():          # solo se tocan nombres en MAYUSCULAS (formato distinto al maestro)
        return re.sub(r"\s+", " ", n).strip()
    n = re.sub(r"\s*\b(S\.?\s?A\.?\s?S\.?|S\.?\s?A\.?|LTDA\.?)\s*$", "", n.strip(), flags=re.I)
    n = re.sub(r"\s+", " ", n).strip()
    n = " ".join(w.capitalize() for w in n.split())
    return n
cambios = 0
for pid, nom in cur.execute("SELECT proveedor_id, nombre FROM proveedor").fetchall():
    nn = normalizar(nom)
    if nn != nom:
        cur.execute("UPDATE proveedor SET nombre=? WHERE proveedor_id=?", (nn, pid)); cambios += 1
        print(f"   nombre {pid}: '{nom}' -> '{nn}'")
log["nombres de proveedor normalizados"] = cambios

# (5) tarifas x1000: precio por km fuera de [2.000, 25.000] y que al dividir por 1000 queda dentro
malas = cur.execute("""SELECT t.tarifa_id, t.precio_cop, c.distancia_km FROM tarifa t JOIN corredor c USING(corredor_id)
                       WHERE t.precio_cop/c.distancia_km > 25000""").fetchall()
fix = 0
for tid, pr, km in malas:
    if 2000 <= (pr / 1000) / km <= 25000:
        cur.execute("UPDATE tarifa SET precio_cop=? WHERE tarifa_id=?", (int(round(pr / 1000)), tid)); fix += 1
log["tarifas con factor 1000 corregidas"] = fix

con.commit()
print("\n== Correcciones ==")
for k, v in log.items(): print(f"  {k:62s} {v:6d}")

if a.comparar and Path(a.comparar).exists():
    ref = sqlite3.connect(a.comparar)
    tablas = [r[0] for r in ref.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name")]
    print(f"\n== Conteos: limpia vs referencia ({Path(a.comparar).name}) ==")
    ok = True
    for t in tablas:
        n1 = cur.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]; n0 = ref.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
        ok &= n1 == n0
        print(f"  {t:24s} {n1:7d} {n0:7d}  {'OK' if n1 == n0 else 'DIFIERE'}")
    # exactitud de valores reconstruidos
    ref.execute(f"ATTACH DATABASE '{a.limpio}' AS l")
    d_at = ref.execute("SELECT COUNT(*) FROM servicio r JOIN l.servicio x USING(servicio_id) WHERE r.a_tiempo IS NOT x.a_tiempo").fetchone()[0]
    d_ent = ref.execute("SELECT MAX(ABS(julianday(r.entrega_real)-julianday(x.entrega_real))*24*60) FROM servicio r JOIN l.servicio x USING(servicio_id)").fetchone()[0]
    d_tar = ref.execute("SELECT COUNT(*) FROM tarifa r JOIN l.tarifa x USING(tarifa_id) WHERE r.precio_cop<>x.precio_cop").fetchone()[0]
    d_nom = ref.execute("SELECT COUNT(*) FROM proveedor r JOIN l.proveedor x USING(proveedor_id) WHERE r.nombre<>x.nombre").fetchone()[0]
    print(f"\n  a_tiempo distinto de la referencia: {d_at} · error max. en entrega_real: {d_ent:.0f} min · tarifas distintas: {d_tar} · nombres distintos: {d_nom}")
    print("  RESULTADO:", "conteos iguales a la referencia" if ok else "HAY DIFERENCIAS DE CONTEO")
print(f"\nGuardado: {a.limpio}")
