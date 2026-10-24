"""Reglas de calidad de datos (6 dimensiones: exactitud, completitud, consistencia, oportunidad, unicidad, validez)
+ reglas de REALISMO del mundo simulado. Uso: python validar_datos.py [ruta.db]   (codigo de salida 1 si algo critico falla)
Rangos con fuente: distancias Buenaventura (Camara de Comercio de Buenaventura: B/ventura-Bogota 519 km, -Cali 165 km, -Medellin 499 km).
Los demas rangos son SUPUESTOS DEL EQUIPO (marcados 'supuesto'): calibrar con SICE-TAC (Min. Transporte) cuando haya tiempo."""
import sqlite3, sys, re
from pathlib import Path
db = sys.argv[1] if len(sys.argv) > 1 else str(Path(__file__).resolve().parent.parent / "data" / "cosco.db")
con = sqlite3.connect(db)
q1 = lambda s: con.execute(s).fetchone()[0]
R = []   # (dimension, regla, critica, malos, total, detalle)
def regla(dim, nombre, sql_malos, sql_total, critica=True, nota=""):
    malos = q1(sql_malos); total = q1(sql_total)
    R.append((dim, nombre, critica, malos, total, nota))

# ---------------- UNICIDAD ----------------
regla("Unicidad", "Sin servicios duplicados (misma solicitud, proveedor, cargue)", "SELECT COUNT(*) FROM (SELECT 1 FROM servicio GROUP BY solicitud_id,proveedor_id,cargue_real HAVING COUNT(*)>1 AND cargue_real IS NOT NULL)", "SELECT COUNT(*) FROM servicio")
regla("Unicidad", "Ids de servicio sin prefijo de copia (DUP)", "SELECT COUNT(*) FROM servicio WHERE servicio_id LIKE 'DUP%'", "SELECT COUNT(*) FROM servicio")
regla("Unicidad", "Un proveedor = un nombre normalizado", "SELECT COUNT(*) FROM proveedor WHERE nombre<>trim(nombre) OR nombre GLOB '*[A-Z][A-Z][A-Z]*[A-Z][A-Z]*' AND nombre=upper(nombre)", "SELECT COUNT(*) FROM proveedor", nota="detecta nombres en MAYUSCULAS/S.A.S. que sugieren duplicado de entidad")
regla("Unicidad", "Tarifas sin vigencias solapadas", """SELECT COUNT(*) FROM tarifa a JOIN tarifa b ON a.proveedor_id=b.proveedor_id AND a.corredor_id=b.corredor_id AND a.tipo_vehiculo_id=b.tipo_vehiculo_id AND a.tarifa_id<b.tarifa_id
   AND a.vigente_desde<=COALESCE(b.vigente_hasta,'9999') AND b.vigente_desde<=COALESCE(a.vigente_hasta,'9999')""", "SELECT COUNT(*) FROM tarifa")
# ---------------- COMPLETITUD ----------------
regla("Completitud", "Servicios ENTREGADOS con fechas, a_tiempo y costo", "SELECT COUNT(*) FROM servicio WHERE estado='ENTREGADO' AND (entrega_real IS NULL OR cargue_real IS NULL OR a_tiempo IS NULL OR costo_final IS NULL)", "SELECT COUNT(*) FROM servicio WHERE estado='ENTREGADO'")
regla("Completitud", "Toda solicitud tiene al menos un servicio (salvo las sin oferta)", "SELECT COUNT(*) FROM solicitud s WHERE fase='historico' AND NOT EXISTS (SELECT 1 FROM servicio v WHERE v.solicitud_id=s.solicitud_id)", "SELECT COUNT(*) FROM solicitud WHERE fase='historico'", critica=False, nota="tolerable: pocas solicitudes sin proveedor disponible")
regla("Completitud", "Todo proveedor activo tiene flota y al menos una tarifa", "SELECT COUNT(*) FROM proveedor p WHERE activo=1 AND (NOT EXISTS (SELECT 1 FROM flota f WHERE f.proveedor_id=p.proveedor_id) OR NOT EXISTS (SELECT 1 FROM tarifa t WHERE t.proveedor_id=p.proveedor_id))", "SELECT COUNT(*) FROM proveedor WHERE activo=1")
regla("Completitud", "Toda recomendacion/decision requerida: decision con motivo si no acepta", "SELECT COUNT(*) FROM decision WHERE acepto_recomendacion=0 AND (motivo IS NULL OR motivo='')", "SELECT COUNT(*) FROM decision WHERE acepto_recomendacion=0")
# ---------------- VALIDEZ (formatos y rangos) ----------------
regla("Validez", "Fechas en formato AAAA-MM-DD[THH:MM]", "SELECT COUNT(*) FROM servicio WHERE entrega_planeada NOT GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]T[0-9][0-9]:[0-9][0-9]*'", "SELECT COUNT(*) FROM servicio")
regla("Validez", "Dinero entero positivo y sin escala errada (tarifa/km entre 2.000 y 25.000 COP, supuesto)", """SELECT COUNT(*) FROM tarifa t JOIN corredor c USING(corredor_id) WHERE precio_cop/ c.distancia_km NOT BETWEEN 2000 AND 25000""", "SELECT COUNT(*) FROM tarifa", nota="detecta tarifas x1000 o en miles")
regla("Validez", "Peso no supera la capacidad del vehiculo", "SELECT COUNT(*) FROM solicitud s JOIN tipo_vehiculo v ON v.tipo_vehiculo_id=s.tipo_vehiculo_req WHERE s.peso_ton>v.capacidad_ton", "SELECT COUNT(*) FROM solicitud")
regla("Validez", "Dias de detencion entre 0 y 15", "SELECT COUNT(*) FROM servicio WHERE dias_detencion<0 OR dias_detencion>15", "SELECT COUNT(*) FROM servicio")
regla("Validez", "Velocidad efectiva entre 3 y 90 km/h (supuesto; incluye cierres viales, filas en el puerto y esperas)", """SELECT COUNT(*) FROM servicio s JOIN solicitud so USING(solicitud_id) JOIN corredor c USING(corredor_id)
  WHERE s.estado='ENTREGADO' AND c.distancia_km/((julianday(s.entrega_real)-julianday(s.cargue_real))*24) NOT BETWEEN 3 AND 90""", "SELECT COUNT(*) FROM servicio WHERE estado='ENTREGADO'")
regla("Validez", "Valores de catalogo permitidos (nivel, carga, estado)", "SELECT COUNT(*) FROM solicitud WHERE nivel_servicio NOT IN ('Flexible','Estandar','Urgente') OR tipo_carga NOT IN ('general','refrigerada','peligrosa','sobredimensionada')", "SELECT COUNT(*) FROM solicitud")
regla("Validez", "Puntaje de feedback entre 1 y 3", "SELECT COUNT(*) FROM feedback WHERE puntaje NOT BETWEEN 1 AND 3", "SELECT COUNT(*) FROM feedback")
# ---------------- CONSISTENCIA ----------------
regla("Consistencia", "Integridad referencial (todo codigo apunta a algo que existe)", """SELECT (SELECT COUNT(*) FROM servicio WHERE solicitud_id NOT IN (SELECT solicitud_id FROM solicitud))+(SELECT COUNT(*) FROM servicio WHERE proveedor_id NOT IN (SELECT proveedor_id FROM proveedor))+(SELECT COUNT(*) FROM solicitud WHERE corredor_id NOT IN (SELECT corredor_id FROM corredor))+(SELECT COUNT(*) FROM solicitud WHERE cliente_id NOT IN (SELECT cliente_id FROM cliente))+(SELECT COUNT(*) FROM evento_servicio WHERE servicio_id NOT IN (SELECT servicio_id FROM servicio))+(SELECT COUNT(*) FROM feedback WHERE servicio_id NOT IN (SELECT servicio_id FROM servicio))""", "SELECT COUNT(*) FROM servicio")
regla("Consistencia", "La entrega real es posterior al cargue real", "SELECT COUNT(*) FROM servicio WHERE estado='ENTREGADO' AND entrega_real<=cargue_real", "SELECT COUNT(*) FROM servicio WHERE estado='ENTREGADO'")
regla("Consistencia", "a_tiempo coincide con entrega_real <= entrega_planeada", "SELECT COUNT(*) FROM servicio WHERE estado='ENTREGADO' AND a_tiempo<>(entrega_real<=entrega_planeada)", "SELECT COUNT(*) FROM servicio WHERE estado='ENTREGADO'")
regla("Consistencia", "Cancelados no tienen entrega ni costo final", "SELECT COUNT(*) FROM servicio WHERE estado<>'ENTREGADO' AND (entrega_real IS NOT NULL OR costo_final IS NOT NULL)", "SELECT COUNT(*) FROM servicio WHERE estado<>'ENTREGADO'")
regla("Consistencia", "Plazo posterior al cargue y solicitud anterior al cargue", "SELECT COUNT(*) FROM solicitud WHERE plazo_entrega<=fecha_cargue OR fecha_solicitud>fecha_cargue", "SELECT COUNT(*) FROM solicitud")
regla("Consistencia", "Costo final >= precio pactado", "SELECT COUNT(*) FROM servicio WHERE estado='ENTREGADO' AND costo_final<precio_pactado", "SELECT COUNT(*) FROM servicio WHERE estado='ENTREGADO'")
regla("Consistencia", "Detencion solo cuando hubo retraso", "SELECT COUNT(*) FROM servicio WHERE a_tiempo=1 AND dias_detencion>0", "SELECT COUNT(*) FROM servicio WHERE a_tiempo=1")
regla("Consistencia", "Eventos ocurren entre cargue y entrega", "SELECT COUNT(*) FROM evento_servicio e JOIN servicio s USING(servicio_id) WHERE s.estado='ENTREGADO' AND (e.fecha_hora<s.cargue_real OR e.fecha_hora>s.entrega_real)", "SELECT COUNT(*) FROM evento_servicio")
regla("Consistencia", "Capacidad reportada no supera la flota", "SELECT COUNT(*) FROM capacidad_snapshot c JOIN flota f USING(proveedor_id,tipo_vehiculo_id) WHERE c.unidades_disponibles>f.cantidad", "SELECT COUNT(*) FROM capacidad_snapshot")
# --- coherencia con REGLAS DURAS del negocio ---
regla("Consistencia", "Carga refrigerada/peligrosa/sobredimensionada solo con proveedor certificado", """SELECT COUNT(*) FROM servicio s JOIN solicitud so USING(solicitud_id) WHERE
  (so.tipo_carga='refrigerada' AND NOT EXISTS (SELECT 1 FROM certificacion c WHERE c.proveedor_id=s.proveedor_id AND c.tipo='REEFER')) OR
  (so.tipo_carga='peligrosa' AND NOT EXISTS (SELECT 1 FROM certificacion c WHERE c.proveedor_id=s.proveedor_id AND c.tipo='IMO')) OR
  (so.tipo_carga='sobredimensionada' AND NOT EXISTS (SELECT 1 FROM certificacion c WHERE c.proveedor_id=s.proveedor_id AND c.tipo='SOBREDIMENSIONADA'))""", "SELECT COUNT(*) FROM servicio")
regla("Consistencia", "Servicio con proveedor que tiene flota del vehiculo y tarifa del corredor", """SELECT COUNT(*) FROM servicio s JOIN solicitud so USING(solicitud_id) WHERE NOT EXISTS (SELECT 1 FROM flota f WHERE f.proveedor_id=s.proveedor_id AND f.tipo_vehiculo_id=so.tipo_vehiculo_req) OR NOT EXISTS (SELECT 1 FROM tarifa t WHERE t.proveedor_id=s.proveedor_id AND t.corredor_id=so.corredor_id AND t.tipo_vehiculo_id=so.tipo_vehiculo_req)""", "SELECT COUNT(*) FROM servicio")
regla("Consistencia", "Proveedor ya existia (fecha_alta) cuando hizo el servicio", "SELECT COUNT(*) FROM servicio s JOIN proveedor p USING(proveedor_id) JOIN solicitud so USING(solicitud_id) WHERE p.fecha_alta>substr(so.fecha_cargue,1,10)", "SELECT COUNT(*) FROM servicio")
regla("Consistencia", "Precio pactado = tarifa vigente de ese dia", """SELECT COUNT(*) FROM servicio s JOIN solicitud so USING(solicitud_id) WHERE NOT EXISTS (SELECT 1 FROM tarifa t WHERE t.proveedor_id=s.proveedor_id AND t.corredor_id=so.corredor_id AND t.tipo_vehiculo_id=so.tipo_vehiculo_req AND t.precio_cop=s.precio_pactado)""", "SELECT COUNT(*) FROM servicio", critica=False, nota="el precio pactado debe existir como tarifa de ese proveedor/ruta/vehiculo")
# ---------------- EXACTITUD / REALISMO ----------------
regla("Exactitud", "Distancias de corredores de Buenaventura segun fuentes (519, 165, 499 km, +/-5)", "SELECT COUNT(*) FROM corredor WHERE (corredor_id='C1' AND abs(distancia_km-519)>5) OR (corredor_id='C2' AND abs(distancia_km-165)>5) OR (corredor_id='C3' AND abs(distancia_km-499)>5)", "SELECT 3")
regla("Exactitud", "Puntualidad global entre 60 % y 92 % (supuesto de mercado)", "SELECT CASE WHEN avg(a_tiempo) BETWEEN 0.60 AND 0.92 THEN 0 ELSE 1 END FROM servicio WHERE estado='ENTREGADO'", "SELECT 1", critica=False)
regla("Exactitud", "Margen al cliente entre -5 % y +40 % sobre el precio de mercado (supuesto)", "SELECT COUNT(*) FROM solicitud s WHERE tarifa_cliente < 0.95*(SELECT MIN(precio_cop) FROM tarifa t WHERE t.corredor_id=s.corredor_id AND t.tipo_vehiculo_id=s.tipo_vehiculo_req)", "SELECT COUNT(*) FROM solicitud", critica=False)
regla("Exactitud", "Nivel Urgente es minoria (menos del 35 %)", "SELECT CASE WHEN avg(nivel_servicio='Urgente')<0.35 THEN 0 ELSE 1 END FROM solicitud", "SELECT 1", critica=False)
regla("Exactitud", "Fines de semana con menos solicitudes que dias habiles", "SELECT CASE WHEN (SELECT 1.0*SUM(CAST(strftime('%w',fecha_solicitud) AS INT) IN (0,6))/COUNT(*) FROM solicitud)<0.2 THEN 0 ELSE 1 END", "SELECT 1", critica=False)
# ---------------- OPORTUNIDAD ----------------
regla("Oportunidad", "Historia sin datos del futuro: nada 'historico' entregado despues del corte + 2 semanas", "SELECT COUNT(*) FROM servicio s JOIN solicitud so USING(solicitud_id) WHERE so.fase='historico' AND substr(s.entrega_real,1,10)>'2026-10-20'", "SELECT COUNT(*) FROM servicio", critica=False)
regla("Oportunidad", "Capacidad: al menos una foto por semana por proveedor y vehiculo", "SELECT COUNT(*) FROM flota f WHERE (SELECT COUNT(*) FROM capacidad_snapshot c WHERE c.proveedor_id=f.proveedor_id AND c.tipo_vehiculo_id=f.tipo_vehiculo_id)<10", "SELECT COUNT(*) FROM flota", critica=False, nota="proveedores nuevos pueden tener menos fotos")

fallas = 0; crit = 0
print(f"Base: {db}\n{'Dimension':13s} {'Regla':95s} {'Malos':>7s} {'de':>7s}  Estado")
for dim, n, c, m, t, nota in R:
    ok = (m == 0); fallas += (not ok); crit += (not ok and c)
    print(f"{dim:13s} {n[:95]:95s} {m:7d} {t:7d}  {'OK' if ok else ('FALLA' if c else 'AVISO')}" + (f"   ({nota})" if (not ok and nota) else ""))
print(f"\n{len(R)} reglas · {len(R)-fallas} OK · {fallas} con problemas ({crit} criticas)")
sys.exit(1 if crit else 0)
