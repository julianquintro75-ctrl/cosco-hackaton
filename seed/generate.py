"""Generador de datos semilla con VERDAD OCULTA.
Uso: python generate.py [--seed 7] [--out ../data] [--sucio]
Produce: cosco.db (limpia), verdad_oculta.csv (para evaluar, el modelo NUNCA la lee), y opcionalmente cosco_sucio.db."""
import argparse, csv, math, shutil, sqlite3
from datetime import date, datetime, timedelta
from pathlib import Path
import numpy as np
import config as C

ap = argparse.ArgumentParser()
ap.add_argument("--seed", type=int, default=7)
ap.add_argument("--out", default=str(Path(__file__).resolve().parent.parent / "data"))
ap.add_argument("--sucio", action="store_true")
ap.add_argument("--append", action="store_true", help="continuar sobre una base existente (simulacion en vivo)")
ap.add_argument("--desde"); ap.add_argument("--hasta")
ap.add_argument("--evento", action="append", default=[], help="PID:valor:desde[:hasta] fuerza P(tarde) real, p.ej. P03:0.45:2026-10-20")
ap.add_argument("--lam", type=float, default=22, help="solicitudes promedio por dia habil")
a = ap.parse_args()
rng = np.random.default_rng(a.seed)
out = Path(a.out); out.mkdir(parents=True, exist_ok=True)
dbp = out / "cosco.db"
if dbp.exists() and not a.append: dbp.unlink()
con = sqlite3.connect(dbp)
if not a.append: con.executescript((Path(__file__).parent.parent / "db" / "schema.sql").read_text(encoding="utf8"))
iso = lambda d: d.isoformat(timespec="minutes") if isinstance(d, datetime) else d.isoformat()

# ---------- maestros ----------
cor = {c[0]: c for c in C.CORREDORES}
veh = {v[0]: v for v in C.VEHICULOS}
tarifa = {}
prov = {p[0]: p for p in C.PROVEEDORES}
n_cli = 40
if not a.append:
    con.executemany("INSERT INTO corredor VALUES (?,?,?,?,?,?)", [(c[0], c[1], c[2], c[3], c[4], c[5]) for c in C.CORREDORES])
    con.executemany("INSERT INTO tipo_vehiculo VALUES (?,?,?,?)", [(v[0], v[1], v[2], v[3]) for v in C.VEHICULOS])
    con.executemany("INSERT INTO proveedor VALUES (?,?,?,?,?,1)",
                    [(p[0], p[1], f"9{rng.integers(10**8, 10**9-1)}-{rng.integers(0,9)}", p[2], iso(p[3])) for p in C.PROVEEDORES])
    for p in C.PROVEEDORES:
        for t in p[10]: con.execute("INSERT INTO certificacion VALUES (?,?,?)", (p[0], t, "2027-12-31"))
        for v, n in p[9].items(): con.execute("INSERT INTO flota VALUES (?,?,?)", (p[0], v, n))
    con.executemany("INSERT INTO cliente VALUES (?,?,?,?)", [
        (f"K{i:03d}", f"Cliente {i:03d}", str(rng.choice(["importador", "exportador", "mixto"], p=[.5, .3, .2])), int(rng.choice([1, 2, 3], p=[.15, .35, .5])))
        for i in range(1, n_cli + 1)])

    # tarifas: 4 vigencias trimestrales
    trims = [(date(2025,11,1), date(2026,1,31)), (date(2026,2,1), date(2026,4,30)), (date(2026,5,1), date(2026,7,31)), (date(2026,8,1), None)]
    base_precio = lambda c, v: (cor[c][4] * C.PRECIO_KM + C.PRECIO_FIJO) * veh[v][4]
    tarifa = {}   # (prov, corr, veh) -> [(desde, hasta, precio)]
    for p in C.PROVEEDORES:
        for c in p[11]:
            for v in p[9]:
                if v == "VRF" and "REEFER" not in p[10] and v not in p[9]: continue
                noise = rng.uniform(.96, 1.04)
                for k, (d0, d1) in enumerate(trims):
                    precio = int(round(base_precio(c, v) * p[4] * noise * (1 + C.INFLACION_TRIM) ** k, -3))
                    tarifa.setdefault((p[0], c, v), []).append((d0, d1, precio))
                    con.execute("INSERT INTO tarifa (proveedor_id,corredor_id,tipo_vehiculo_id,precio_cop,vigente_desde,vigente_hasta) VALUES (?,?,?,?,?,?)",
                                (p[0], c, v, precio, iso(d0), iso(d1) if d1 else None))
    def precio_en(pid, c, v, d):
        for d0, d1, pr in tarifa[(pid, c, v)]:
            if d >= d0 and (d1 is None or d <= d1): return pr
        return tarifa[(pid, c, v)][-1][2]
else:
    for r in con.execute("SELECT proveedor_id,corredor_id,tipo_vehiculo_id,precio_cop,vigente_desde,vigente_hasta FROM tarifa ORDER BY vigente_desde"):
        tarifa.setdefault((r[0], r[1], r[2]), []).append((date.fromisoformat(r[4][:10]), date.fromisoformat(r[5][:10]) if r[5] else None, r[3]))
def precio_en(pid, c, v, d):
    for d0, d1, pr in tarifa[(pid, c, v)]:
        if d >= d0 and (d1 is None or d <= d1): return pr
    return tarifa[(pid, c, v)][-1][2]


# ---------- verdad oculta ----------
EVT = []
for e in a.evento:
    pp = e.split(":"); EVT.append((pp[0], float(pp[1]), date.fromisoformat(pp[2]), date.fromisoformat(pp[3]) if len(pp) > 3 else date(2100, 1, 1)))
def p_tarde(pid, c, d):
    for ep, ev, e0, e1 in EVT:
        if ep == pid and e0 <= d <= e1: return ev
    p = prov[pid][5](d, c)
    if cor[c][7] and d.month in C.LLUVIA_MESES: p += 0.05 * C.PESO_LLUVIA.get(pid, 1.0)
    return float(min(max(p, 0.01), 0.85))
hab_base = {p[0]: p[12] for p in C.PROVEEDORES}
def habito(pid, d):                       # Mulas del Valle gana cuota con el tiempo (concentracion)
    w = hab_base[pid]
    if pid == "P07": w *= 1 + 1.2 * (d - C.INICIO).days / 365
    return w
def activo(pid, d): return prov[pid][3] <= d

# ---------- simulacion ----------
cap_hoy = {}
def disponibles(pid, v, d):
    key = (pid, v, d)
    if key not in cap_hoy:
        n = prov[pid][9].get(v, 0)
        cap_hoy[key] = max(0, n - int(rng.poisson(0.55 * n)))
    return cap_hoy[key]
w_cor = np.array([c[6] for c in C.CORREDORES]); w_cor = w_cor / w_cor.sum()
niv = list(C.NIVEL_PROB); w_niv = list(C.NIVEL_PROB.values())
sol_rows, srv_rows, evt_rows, fb_rows, dec_rows, gt_rows = [], [], [], [], [], []
n_sol = n_srv = 0
dia = C.INICIO; fin = C.FIN
if a.append:
    n_sol = int(con.execute("SELECT COALESCE(MAX(CAST(SUBSTR(solicitud_id,2) AS INT)),0) FROM solicitud").fetchone()[0])
    n_srv = int(con.execute("SELECT COALESCE(MAX(CAST(SUBSTR(servicio_id,2) AS INT)),0) FROM servicio WHERE servicio_id LIKE 'S%'").fetchone()[0])
    ult = con.execute("SELECT MAX(substr(fecha_solicitud,1,10)) FROM solicitud").fetchone()[0]
    dia = date.fromisoformat(a.desde) if a.desde else date.fromisoformat(ult) - timedelta(days=0) + timedelta(days=1)
    fin = date.fromisoformat(a.hasta) if a.hasta else dia
    a_seed = a.seed + int(dia.strftime("%j")) + 1000; rng = np.random.default_rng(a_seed)
while dia <= fin:
    lam = a.lam * (0.3 if dia.weekday() >= 5 else 1.0)
    for _ in range(int(rng.poisson(lam))):
        n_sol += 1; sid = f"R{n_sol:06d}"
        c = C.CORREDORES[int(rng.choice(len(C.CORREDORES), p=w_cor))][0]
        r = rng.random()
        if r < .08:   carga, v, ton, ph = "refrigerada", "VRF", float(rng.uniform(14, 26)), 0
        elif r < .13: carga, v, ton, ph = "peligrosa", "V40", float(rng.uniform(10, 26)), 1
        elif r < .17: carga, v, ton, ph = "sobredimensionada", "VCB", float(rng.uniform(20, 34)), 0
        else:
            v = str(rng.choice(["V40", "V20", "VSE"], p=[.62, .28, .10])); carga, ph = "general", 0
            ton = float(rng.uniform(6, 30 if v == "V40" else (20 if v == "V20" else 9)))
        nivel = str(rng.choice(niv, p=w_niv))
        cargue = datetime.combine(dia + timedelta(days=int(rng.integers(1, 5))), datetime.min.time()) + timedelta(hours=int(rng.integers(6, 16)))
        T0 = cor[c][4] / 42 + 6
        planeada_h = T0 * C.HOLGURA[nivel]
        entrega_plan = cargue + timedelta(hours=planeada_h)
        plazo = entrega_plan + (timedelta(hours=C.VENTANA_FLEX_H) if nivel == "Flexible" else timedelta(0))
        # tarifa al cliente: referencia de mercado del corredor/vehiculo
        refs = [precio_en(pid, c, v, dia) for (pid, cc, vv) in tarifa if cc == c and vv == v]
        if not refs: n_sol -= 1; continue
        tarifa_cli = int(round(np.median(refs) * C.MARGEN_BASE * C.PRIMA_NIVEL[nivel], -3))
        fase = "vivo" if a.append else ("prueba" if dia > C.FIN_HISTORICO else "historico")
        cli = f"K{int(rng.integers(1, n_cli + 1)):03d}"
        sol_rows.append((sid, cli, c, v, carga, round(ton, 1), ph, iso(datetime.combine(dia, datetime.min.time()) + timedelta(hours=int(rng.integers(7, 18)))),
                         iso(cargue), iso(plazo), nivel, tarifa_cli, fase))
        # --- politica historica humana (sesgo): barato + habito + algo de azar ---
        tried = set(); asignado = False
        for intento in range(2):
            fact = []
            for pid, cc, vv in tarifa:
                if cc != c or vv != v or pid in tried or not activo(pid, dia): continue
                if carga == "refrigerada" and "REEFER" not in prov[pid][10]: continue
                if carga == "peligrosa" and "IMO" not in prov[pid][10]: continue
                if carga == "sobredimensionada" and "SOBREDIMENSIONADA" not in prov[pid][10]: continue
                if disponibles(pid, v, dia) <= 0: continue
                fact.append(pid)
            if not fact: break
            prs = np.array([precio_en(pid, c, v, dia) for pid in fact], float)
            w = np.array([habito(pid, dia) for pid in fact]) * np.exp(-4 * (prs / prs.min() - 1))
            pid = str(rng.choice(fact, p=w / w.sum())); tried.add(pid)
            precio = precio_en(pid, c, v, dia)
            n_srv += 1; vid = f"S{n_srv:06d}"
            if intento == 0:
                dec_rows.append((f"D{n_srv:06d}", sid, None, pid, "analista", None, None, iso(cargue - timedelta(days=1))))
            # cancelacion del proveedor -> se reasigna
            if rng.random() < prov[pid][7]:
                srv_rows.append((vid, sid, pid, precio, None, iso(entrega_plan), None, None, None, 0, "CANCELADO"))
                continue
            pt = p_tarde(pid, c, cargue.date())
            tarde = rng.random() < pt
            spread = prov[pid][8]
            if tarde:
                real_h = planeada_h + 0.5 + float(rng.exponential(0.18 * planeada_h + 6))
            else:
                real_h = planeada_h * float(rng.uniform(1 - spread - 0.02, 0.98))
            cargue_real = cargue + timedelta(minutes=int(rng.integers(-30, 90)))
            entrega_real = cargue + timedelta(hours=real_h)
            incidente = rng.random() < prov[pid][6]
            det = int(rng.poisson(0.5 + max(0, real_h - planeada_h) / 24)) if tarde else 0
            costo = precio + det * 450_000 + (int(rng.uniform(2e6, 12e6)) if incidente else 0)
            srv_rows.append((vid, sid, pid, precio, iso(cargue_real), iso(entrega_plan), iso(entrega_real), int(not tarde), costo, det, "ENTREGADO"))
            for k, fr in enumerate((0.35, 0.7)):
                evt_rows.append((vid, "GPS", iso(cargue_real + timedelta(hours=real_h * fr)), f"hito {k+1}"))
            if tarde: evt_rows.append((vid, "NOVEDAD", iso(cargue_real + timedelta(hours=real_h * 0.6)), "demora en ruta"))
            if incidente: evt_rows.append((vid, str(rng.choice(["INCIDENTE", "DANO"])), iso(cargue_real + timedelta(hours=real_h * 0.5)), "evento reportado"))
            # feedback sin formularios: muestra, mas probable si hubo problema
            if rng.random() < (0.7 if (tarde or incidente) else 0.22):
                if tarde or incidente: puntaje = int(rng.choice([1, 2], p=[.6, .4])); causa = str(rng.choice(["proveedor", "puerto", "clima", "cliente"], p=[.7, .12, .12, .06]))
                else: puntaje = int(rng.choice([2, 3], p=[.15, .85])); causa = None
                fb_rows.append((vid, "WhatsApp" if rng.random() < .9 else "operador", puntaje, causa))
            gt_rows.append((cargue.date().isoformat(), pid, c, round(pt, 4)))
            asignado = True; break
    dia += timedelta(days=1)

# capacidad semanal
d = (dia - timedelta(days=0)) if False else C.INICIO
if a.append: d = date.fromisoformat(a.desde) if a.desde else fin
while d <= fin:
    for p in C.PROVEEDORES:
        if not activo(p[0], d): continue
        for v, n in p[9].items():
            con.execute("INSERT INTO capacidad_snapshot VALUES (?,?,?,?)", (p[0], v, iso(datetime.combine(d, datetime.min.time()) + timedelta(hours=6)), max(0, n - int(rng.poisson(0.55 * n)))))
    d += timedelta(days=7)

con.executemany("INSERT INTO solicitud VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)", sol_rows)
con.executemany("INSERT INTO servicio VALUES (?,?,?,?,?,?,?,?,?,?,?)", srv_rows)
con.executemany("INSERT INTO evento_servicio (servicio_id,tipo,fecha_hora,detalle) VALUES (?,?,?,?)", evt_rows)
con.executemany("INSERT INTO feedback VALUES (?,?,?,?)", fb_rows)
con.executemany("INSERT INTO decision VALUES (?,?,?,?,?,?,?,?)", dec_rows)
con.commit()
# verdad oculta semanal por proveedor x corredor (para evaluar; nunca para entrenar)
semanas = {}
for f, pid, c, pt in gt_rows:
    wk = (date.fromisoformat(f) - timedelta(days=date.fromisoformat(f).weekday())).isoformat()
    semanas.setdefault((wk, pid, c), []).append(pt)
vo = out / "verdad_oculta.csv"; nuevo = not (a.append and vo.exists())
with open(vo, "w" if nuevo else "a", newline="", encoding="utf8") as fh:
    w = csv.writer(fh)
    if nuevo: w.writerow(["semana", "proveedor_id", "corredor_id", "p_tarde_real", "n_servicios"])
    for (wk, pid, c), v in sorted(semanas.items()): w.writerow([wk, pid, c, round(float(np.mean(v)), 4), len(v)])
con.close()

# ---------- version con datos sucios (para practicar limpieza) ----------
if a.sucio and not a.append:
    sp = out / "cosco_sucio.db"; shutil.copy(dbp, sp)
    s = sqlite3.connect(sp); cur = s.cursor()
    ids = [r[0] for r in cur.execute("SELECT servicio_id FROM servicio WHERE estado='ENTREGADO' ORDER BY RANDOM() LIMIT ?", (int(n_srv * 0.02),))]
    for i, sid in enumerate(ids[: len(ids) // 3]):      # entrega antes del cargue (imposible)
        cur.execute("UPDATE servicio SET entrega_real = datetime(cargue_real,'-5 hours') WHERE servicio_id=?", (sid,))
    for sid in ids[len(ids) // 3: 2 * len(ids) // 3]:   # a_tiempo vacio
        cur.execute("UPDATE servicio SET a_tiempo=NULL WHERE servicio_id=?", (sid,))
    for sid in ids[2 * len(ids) // 3:]:                 # duplicado
        cur.execute("INSERT INTO servicio SELECT 'DUP'||servicio_id,solicitud_id,proveedor_id,precio_pactado,cargue_real,entrega_planeada,entrega_real,a_tiempo,costo_final,dias_detencion,estado FROM servicio WHERE servicio_id=?", (sid,))
    cur.execute("UPDATE proveedor SET nombre='ANDINA CARGO S.A.S.' WHERE proveedor_id='P01'")
    cur.execute("UPDATE tarifa SET precio_cop = precio_cop*1000 WHERE tarifa_id IN (SELECT tarifa_id FROM tarifa ORDER BY RANDOM() LIMIT 6)")
    s.commit(); s.close()
print(f"solicitudes={n_sol} servicios={n_srv} eventos={len(evt_rows)} feedback={len(fb_rows)} -> {dbp}")
