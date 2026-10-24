import sqlite3, html, json
from pathlib import Path
con = sqlite3.connect("../data/cosco.db"); con.row_factory = sqlite3.Row
q = lambda s, *a: [dict(r) for r in con.execute(s, a)]
E = html.escape

# (tabla, titulo, que_es, quien_llena, prioridad, [(col, significado)])
T = [
("cliente","Clientes","La lista de empresas que le piden transporte a COSCO.","COSCO (su base de clientes)","Deseable",
 [("cliente_id","Código único del cliente (K001, K002…)"),("nombre","Nombre de la empresa"),("segmento","importador, exportador o mixto"),("prioridad","1 = cliente clave, 3 = normal")]),
("corredor","Corredores","Cada ruta entre un puerto y una ciudad. Es el «tramo» sobre el que se compara a los proveedores.","COSCO + mapa de rutas","Indispensable",
 [("corredor_id","Código de la ruta (C1, C2…)"),("origen / destino","Ciudades de salida y llegada"),("puerto","Puerto donde empieza la ruta"),("distancia_km","Kilómetros por carretera"),("riesgo_vial","0 a 1; qué tan difícil es la vía (derrumbes, orden público)")]),
("tipo_vehiculo","Tipos de vehículo","El catálogo de camiones que existen: tractomula 40', 20', reefer, cama baja…","COSCO","Indispensable",
 [("tipo_vehiculo_id","Código (V40, V20, VRF…)"),("nombre","Nombre normal del vehículo"),("capacidad_ton","Toneladas que carga"),("contenedor","Tamaño del contenedor que lleva (20, 40 o –)")]),
("proveedor","Proveedores","Las empresas transportadoras entre las que hay que elegir.","COSCO","Indispensable",
 [("proveedor_id","Código único (P01…)"),("nombre","Nombre comercial"),("nit","Identificación tributaria"),("ciudad_base","Dónde opera principalmente"),("fecha_alta","Desde cuándo trabaja con COSCO"),("activo","1 si se puede usar hoy, 0 si no")]),
("certificacion","Certificaciones","Permisos especiales de cada proveedor: mercancía peligrosa (IMO), refrigerada (REEFER) o sobredimensionada. Sin el permiso NO puede hacer ese servicio.","Proveedores / COSCO","Indispensable",
 [("proveedor_id","A qué proveedor pertenece"),("tipo","IMO, REEFER o SOBREDIMENSIONADA"),("vigente_hasta","Fecha en que vence")]),
("flota","Flota","Cuántos vehículos de cada tipo tiene cada proveedor.","Proveedores","Indispensable",
 [("proveedor_id","Proveedor"),("tipo_vehiculo_id","Tipo de vehículo"),("cantidad","Cuántos tiene")]),
("tarifa","Tarifas","El precio que cobra cada proveedor por cada ruta y tipo de vehículo, y desde cuándo vale. Si no hay tarifa, ese proveedor no cubre esa ruta.","COSCO (cotizaciones)","Indispensable",
 [("proveedor_id","Proveedor"),("corredor_id","Ruta"),("tipo_vehiculo_id","Vehículo"),("precio_cop","Precio en pesos colombianos"),("vigente_desde / hasta","Periodo en que ese precio es válido")]),
("capacidad_snapshot","Capacidad en el tiempo","Una «foto» de cuántos vehículos libres tenía cada proveedor en una fecha. Se guardan muchas fotos para saber qué se sabía en cada momento.","Proveedores (reporte semanal o diario)","Deseable",
 [("proveedor_id","Proveedor"),("tipo_vehiculo_id","Vehículo"),("fecha_hora","Cuándo se tomó la foto"),("unidades_disponibles","Cuántos vehículos libres había")]),
("solicitud","Solicitudes","Cada pedido de transporte de un cliente: qué, de dónde a dónde, para cuándo y con qué nivel de urgencia.","Operaciones de COSCO","Indispensable",
 [("solicitud_id","Código del pedido"),("cliente_id / corredor_id","Quién lo pide y en qué ruta"),("tipo_vehiculo_req","Vehículo que necesita"),("tipo_carga","general, refrigerada, peligrosa o sobredimensionada"),("peso_ton","Peso en toneladas"),("fecha_cargue","Cuándo hay que recoger la carga"),("plazo_entrega","Fecha límite de entrega"),("nivel_servicio","Flexible, Estandar o Urgente"),("tarifa_cliente","Lo que COSCO le cobra al cliente (sirve para calcular el margen)"),("fase","historico (para aprender) o prueba (para la demostración)")]),
("servicio","Servicios ejecutados","Lo que realmente pasó: a qué proveedor se le asignó el pedido y si cumplió. Esta es la tabla MÁS importante: de aquí aprende el sistema.","Operaciones de COSCO","Indispensable",
 [("servicio_id","Código del servicio"),("solicitud_id / proveedor_id","Qué pedido y quién lo hizo"),("precio_pactado","Precio acordado con el proveedor"),("cargue_real","Cuándo cargó de verdad"),("entrega_planeada / entrega_real","Cuándo debía y cuándo entregó"),("a_tiempo","1 si llegó a tiempo, 0 si se retrasó"),("costo_final","Costo real: precio + detención + incidentes"),("dias_detencion","Días extra de contenedor retenido"),("estado","ENTREGADO, CANCELADO o RECHAZADO")]),
("evento_servicio","Eventos en ruta","Lo que ocurre durante el viaje: puntos del GPS, novedades, incidentes, daños.","GPS / proveedores / operaciones","Deseable",
 [("servicio_id","A qué servicio pertenece"),("tipo","GPS, NOVEDAD, INCIDENTE o DANO"),("fecha_hora","Cuándo ocurrió"),("detalle","Texto corto")]),
("feedback","Opinión del cliente","Calificación de 1 clic (😊😐😞) y su causa. Es opcional: no todos los servicios la tienen.","Cliente por WhatsApp / operador","Deseable",
 [("servicio_id","Servicio calificado"),("canal","WhatsApp u operador"),("puntaje","1 = malo, 2 = regular, 3 = bueno"),("causa","proveedor, cliente, puerto o clima (si fue negativo)")]),
("recomendacion","Recomendaciones","Lo que el sistema sugirió para cada pedido (Top-3 y su explicación). Se guarda para poder auditar.","El sistema","Sistema",
 [("recomendacion_id","Código"),("solicitud_id","Pedido"),("modelo_version","Versión del modelo que lo calculó"),("top3_y_desglose","Los tres proveedores y el detalle de costos"),("confianza","0 a 1"),("requiere_revision","1 si una persona debe mirarlo con detalle")]),
("decision","Decisiones","Lo que la persona decidió finalmente, si aceptó la recomendación y por qué no.","Operador en la interfaz","Sistema",
 [("proveedor_elegido","Quién fue elegido"),("usuario","Quién decidió"),("acepto_recomendacion","1 si siguió la sugerencia"),("motivo","Si no la siguió: precio, relación, capacidad, etc.")]),
("estadistica_proveedor","Estadísticas del proveedor","La «hoja de vida» calculada de cada proveedor en cada ruta: puntualidad, tiempos, índice de dureza. Se recalcula con cada servicio.","El sistema","Sistema",
 [("alfa / beta","Números internos del cálculo bayesiano"),("p_tarde","Probabilidad estimada de que se retrase"),("transito_p50_h / p90_h","Horas típicas y pesimistas de viaje"),("n_servicios","Cuántos servicios respaldan estos números"),("indice_dureza","Nota de 0 a 10 de resistencia del proveedor")]),
("modelo_version","Versiones del modelo","El registro de cada modelo o juego de pesos que ha usado el sistema y quién lo aprobó.","El sistema / gerencia","Sistema",
 [("modelo_version","Nombre de la versión"),("metricas_validacion","Qué tan bien funcionó al probarlo"),("aprobado_por","Quién lo autorizó")]),
]
SAMPLE = {
 "cliente":"SELECT * FROM cliente WHERE cliente_id IN ('K003','K007')",
 "corredor":"SELECT * FROM corredor LIMIT 3","tipo_vehiculo":"SELECT * FROM tipo_vehiculo LIMIT 3",
 "proveedor":"SELECT proveedor_id,nombre,ciudad_base,fecha_alta,activo FROM proveedor LIMIT 3",
 "certificacion":"SELECT * FROM certificacion LIMIT 3","flota":"SELECT * FROM flota WHERE proveedor_id='P05'",
 "tarifa":"SELECT proveedor_id,corredor_id,tipo_vehiculo_id,precio_cop,vigente_desde,vigente_hasta FROM tarifa WHERE proveedor_id='P05' AND corredor_id='C1' AND tipo_vehiculo_id='V40'",
 "capacidad_snapshot":"SELECT * FROM capacidad_snapshot WHERE proveedor_id='P05' AND tipo_vehiculo_id='V40' LIMIT 3",
 "solicitud":"SELECT solicitud_id,cliente_id,corredor_id,tipo_vehiculo_req,tipo_carga,peso_ton,fecha_cargue,plazo_entrega,nivel_servicio,tarifa_cliente,fase FROM solicitud WHERE solicitud_id='R000077'",
 "servicio":"SELECT servicio_id,solicitud_id,proveedor_id,precio_pactado,cargue_real,entrega_planeada,entrega_real,a_tiempo,costo_final,dias_detencion,estado FROM servicio WHERE servicio_id='S000079'",
 "evento_servicio":"SELECT servicio_id,tipo,fecha_hora,detalle FROM evento_servicio WHERE servicio_id='S000079'",
 "feedback":"SELECT * FROM feedback WHERE servicio_id='S000079'",
}
def table(rows):
    if not rows: return "<p class='small'>La llena el sistema; empieza vacía.</p>"
    h = "".join(f"<th>{E(k)}</th>" for k in rows[0])
    b = "".join("<tr>" + "".join(f"<td>{E('' if v is None else str(v))}</td>" for v in r.values()) + "</tr>" for r in rows)
    return f"<table class='ex'><thead><tr>{h}</tr></thead><tbody>{b}</tbody></table>"
sol = q(SAMPLE["solicitud"])[0]; srv = q(SAMPLE["servicio"])[0]
prov = q("SELECT nombre FROM proveedor WHERE proveedor_id=?", srv["proveedor_id"])[0]["nombre"]
cor = q("SELECT origen,destino FROM corredor WHERE corredor_id=?", sol["corredor_id"])[0]
fb = q(SAMPLE["feedback"])[0]
PRI = {"Indispensable":"p-r","Deseable":"p-y","Sistema":"p-g"}
parts = []
for t, titulo, que, quien, pri, cols in T:
    rows = q(SAMPLE[t]) if t in SAMPLE else []
    parts.append(f"""<div class='tab'><h3>{E(titulo)} <span class='pill {PRI[pri]}'>{pri}</span></h3>
<p>{E(que)}</p><p class='small'><b>Quién la llena:</b> {E(quien)} · <b>Nombre técnico:</b> <code>{t}</code></p>
<table class='cols'><tbody>{''.join(f"<tr><td class='c'>{E(c)}</td><td>{E(m)}</td></tr>" for c,m in cols)}</tbody></table>
<p class='small' style='margin-top:2mm'><b>Ejemplo real de nuestros datos:</b></p>{table(rows)}</div>""")
doc = f"""<!doctype html><html lang='es'><head><meta charset='utf-8'><title>Guía de datos</title><style>
@page{{size:A4;margin:16mm 15mm}}
:root{{--navy:#0f1729;--line:#d9dde4;--soft:#f5f6f8;--blue:#2f6fed}}
html{{font-family:Inter,'DejaVu Sans',sans-serif;font-size:10pt;line-height:1.5;color:#141a26}}
h1{{font-size:20pt;color:var(--navy);margin:0 0 3mm;line-height:1.2}} h2{{font-size:13.5pt;color:var(--navy);margin:7mm 0 2mm;break-after:avoid}} h3{{font-size:11pt;color:var(--navy);margin:0 0 1mm}}
p{{margin:0 0 2.2mm}} .small{{font-size:8.4pt;color:#5b6472}} .kicker{{font-size:8.5pt;font-weight:700;letter-spacing:.08em;text-transform:uppercase;color:var(--blue)}}
.box{{border:1px solid var(--line);border-left:4px solid var(--blue);background:var(--soft);padding:3mm 4mm;margin:3mm 0;break-inside:avoid}}
.tab{{border-top:1px solid var(--line);padding:3mm 0;break-inside:avoid}}
table{{width:100%;border-collapse:collapse;font-size:8.6pt;margin:1.5mm 0}} th{{background:var(--navy);color:#fff;text-align:left;padding:1.4mm 2mm;font-weight:600}}
td{{padding:1.3mm 2mm;border-bottom:1px solid var(--line);vertical-align:top}} .cols td.c{{width:26%;font-weight:600;white-space:nowrap}}
table.ex td{{font-size:7pt;font-family:'DejaVu Sans Mono',monospace;overflow-wrap:anywhere}} table.ex th{{font-size:7.4pt}}
.pill{{font-size:7.4pt;font-weight:700;padding:.4mm 2mm;border-radius:8px;vertical-align:middle}} .p-r{{background:#fde7e7;color:#9b1c1c}} .p-y{{background:#fdf0dc;color:#8a5000}} .p-g{{background:#e2f4ea;color:#1e6e4a}}
code{{font-family:'DejaVu Sans Mono',monospace;font-size:8pt}}
.flow{{display:grid;grid-template-columns:1fr auto 1fr auto 1fr;gap:2mm;align-items:center;margin:3mm 0}} .flow .n{{border:1px solid var(--line);padding:2mm 3mm;border-radius:3px;font-size:8.8pt;background:#fff}} .flow .ar{{color:var(--blue);font-weight:700}}
.g3{{display:grid;grid-template-columns:1fr 1fr 1fr;gap:3mm}} .card{{border:1px solid var(--line);padding:3mm;border-radius:3px;font-size:8.8pt;break-inside:avoid}} .card h4{{margin:0 0 1mm;font-size:9.6pt}}
.pb{{break-before:page}}
</style></head><body>
<div class='kicker'>Guía para todo el equipo</div>
<h1>Los datos del proyecto, explicados sin tecnicismos</h1>
<p>Esta guía explica qué información necesita el sistema, cómo está organizada y cómo se ve en la práctica. No hace falta saber de bases de datos.</p>

<h2>1. La idea en un minuto</h2>
<div class='box'><p><b>Piensen en un libro de Excel con 16 hojas.</b> Cada hoja guarda un tipo de información (clientes, proveedores, tarifas, servicios…). Cada fila es «una cosa» (un cliente, un servicio). Para que las hojas se conecten, cada fila tiene un <b>código único</b> (por ejemplo, el proveedor P05) y las demás hojas lo usan para señalarlo en vez de repetir su nombre.</p>
<p>A eso se le llama «modelo entidad-relación»: <b>entidad</b> = una hoja, <b>relación</b> = el código que la conecta con otra. Eso es todo. El diagrama del PDF es solo el mapa de qué hoja se conecta con cuál.</p></div>

<h2>2. Un viaje real, de principio a fin</h2>
<p>Así se reparten los datos de <b>un solo pedido</b> tomado de nuestros datos de ejemplo. Las flechas indican «mira el código en la otra hoja».</p>
<div class='flow'>
<div class='n'><b>Solicitud {sol['solicitud_id']}</b><br>Cliente {sol['cliente_id']} pide llevar carga {E(sol['tipo_carga'])} de {E(cor['origen'])} a {E(cor['destino'])}, nivel {sol['nivel_servicio']}. Cobra {int(sol['tarifa_cliente']):,} COP.</div><div class='ar'>→</div>
<div class='n'><b>Servicio {srv['servicio_id']}</b><br>Se asignó al proveedor {srv['proveedor_id']} ({E(prov)}) por {int(srv['precio_pactado']):,} COP.</div><div class='ar'>→</div>
<div class='n'><b>Resultado</b><br>{'Llegó tarde' if srv['a_tiempo']==0 else 'Llegó a tiempo'}; costo final {int(srv['costo_final']):,} COP. El cliente calificó {fb['puntaje']} de 3, causa: {E(str(fb['causa']))}.</div></div>
<p class='small'>Del servicio se desprenden además los <b>eventos</b> del viaje (GPS y novedades) y, al cerrar, el sistema <b>actualiza la hoja de vida</b> del proveedor P05. Por eso el servicio es la hoja más importante: cada fila le enseña algo al sistema.</p>
{table(q(SAMPLE['solicitud']))}{table(q(SAMPLE['servicio']))}{table(q(SAMPLE['evento_servicio']))}{table(q(SAMPLE['feedback']))}

<h2>3. Las 16 hojas en tres grupos</h2>
<div class='g3'>
<div class='card'><h4>Catálogos (8)</h4><p>Lo que cambia poco y es la base: clientes, corredores, tipos de vehículo, proveedores, certificaciones, flota, tarifas y capacidad.</p></div>
<div class='card'><h4>Operación (4)</h4><p>Lo que pasa cada día: solicitudes, servicios, eventos en ruta y opinión del cliente. <b>De aquí aprende el sistema.</b></p></div>
<div class='card'><h4>Inteligencia (4)</h4><p>Lo que genera el sistema: recomendaciones, decisiones, estadísticas por proveedor y versiones de modelo. <b>Nadie la llena a mano.</b></p></div></div>
<p style='margin-top:3mm'><span class='pill p-r'>Indispensable</span> sin esto no se puede hacer una recomendación. <span class='pill p-y'>Deseable</span> mejora la calidad pero hay sustitutos. <span class='pill p-g'>Sistema</span> lo calcula el sistema.</p>

<h2 class='pb'>4. Hoja por hoja</h2>
{''.join(parts)}

<h2 class='pb'>5. De dónde salen los datos: los inventamos</h2>
<div class='box'><p>COSCO confirmó que <b>no entregará datos</b>. Por eso todo es sintético, y eso no es un defecto si se hace con método: lo importante es que los datos sean <b>creíbles</b>, que <b>cuenten historias</b> que el sistema pueda descubrir y que <b>se declare con honestidad</b> qué es real y qué es inventado.</p></div>
<h3>Tres capas de datos</h3>
<div class='g3'>
<div class='card'><h4>1 · Semilla (historia)</h4><p>Un año de operación: ~6.100 servicios, 12 proveedores, 8 rutas. Cada proveedor tiene una «historia» (uno se degrada en agosto, otro mejora en junio, uno es nuevo…). Se genera una vez con <code>generate.py</code>.</p></div>
<div class='card'><h4>2 · En vivo</h4><p>Durante la demo se agregan días nuevos con <code>en_vivo.py</code>: llegan pedidos, se asignan y se cierran con resultados. Así el público ve cómo reacciona el sistema.</p></div>
<div class='card'><h4>3 · Eventos inyectados</h4><p>Con una orden se «daña» a un proveedor desde una fecha (por ejemplo, Caribe Express llega tarde 60 % de las veces). Sirve para probar que el sistema se da cuenta y cuánto tarda.</p></div></div>
<h3>Comandos</h3>
<table class='cols'><tbody>
<tr><td class='c'>Crear la historia</td><td><code>python seed/generate.py --sucio</code> (genera la base limpia, una base con errores para practicar limpieza y un archivo de «verdad oculta» solo para evaluar).</td></tr>
<tr><td class='c'>Agregar días en vivo</td><td><code>python seed/en_vivo.py --dias 14 --pausa 3</code></td></tr>
<tr><td class='c'>Dañar un proveedor</td><td><code>python seed/en_vivo.py --dias 10 --evento P03:0.6:2026-10-20</code> (P03 llega tarde el 60 % desde el 20 de octubre)</td></tr>
<tr><td class='c'>Revisar calidad</td><td><code>python seed/validar_datos.py</code></td></tr>
<tr><td class='c'>Ver las historias</td><td><code>python seed/check_story.py</code></td></tr>
</tbody></table>
<h3>Qué es real y qué es inventado</h3>
<table class='cols'><tbody>
<tr><td class='c'>Con fuente</td><td>Distancias Buenaventura–Bogotá (519 km), –Cali (165 km) y –Medellín (499 km), de una presentación de la Cámara de Comercio de Buenaventura. La existencia de cierres viales y filas de camiones en el corredor del puerto, que explican los retrasos largos. El SICE-TAC (Ministerio de Transporte) como referencia oficial de costos eficientes de transporte de carga.</td></tr>
<tr><td class='c'>Aproximado</td><td>Distancias de las demás rutas (Cartagena, Santa Marta, Barranquilla): valores razonables, por confirmar con un mapa antes de la presentación.</td></tr>
<tr><td class='c'>Inventado</td><td>Los proveedores y sus nombres, las tarifas (fórmula de pesos por kilómetro más un fijo, ilustrativa), la puntualidad de cada uno, los clientes, las calificaciones, los incidentes y los costos de retraso.</td></tr>
</tbody></table>
<p class='small'>Frase para la presentación: «Los datos son sintéticos. Las distancias de Buenaventura son reales; los precios y el desempeño de los proveedores se simularon con supuestos explícitos que COSCO puede reemplazar con sus datos reales sin cambiar el sistema.»</p>

<h2 class='pb'>6. Reglas de calidad de los datos</h2>
<p>Los datos inventados también deben cumplir reglas de calidad; si no, el sistema aprendería de basura. Usamos las <b>seis dimensiones clásicas de calidad de datos</b> (exactitud, completitud, consistencia, oportunidad, unicidad y validez, según IBM, Dagster y otras guías) y las aplicamos a nuestro caso con <b>35 reglas automáticas</b> en <code>seed/validar_datos.py</code>.</p>
<table class='cols'><tbody>
<tr><td class='c'>Unicidad</td><td><b>Cada cosa aparece una sola vez.</b> Sin servicios repetidos, sin el mismo proveedor escrito de dos formas, sin precios que se solapen para la misma ruta y fecha.</td></tr>
<tr><td class='c'>Completitud</td><td><b>No falta lo esencial.</b> Todo servicio entregado trae fechas, si llegó a tiempo y su costo; todo proveedor activo tiene flota y tarifas; toda decisión que rechaza la recomendación trae motivo.</td></tr>
<tr><td class='c'>Validez</td><td><b>Los valores tienen forma y rango razonables.</b> Fechas bien escritas, pesos que caben en el vehículo, precio por kilómetro entre 2.000 y 25.000 pesos (detecta tarifas multiplicadas por mil), puntaje de 1 a 3, velocidad promedio entre 3 y 90 km/h, detención de 0 a 15 días.</td></tr>
<tr><td class='c'>Consistencia</td><td><b>Las hojas no se contradicen.</b> Todo código apunta a algo que existe; la entrega es posterior al cargue; «a tiempo» coincide con las fechas; un servicio cancelado no tiene entrega; la detención solo ocurre con retraso; el costo final nunca es menor al precio pactado; los eventos de ruta ocurren dentro del viaje; la capacidad no supera la flota.</td></tr>
<tr><td class='c'>Reglas del negocio</td><td><b>Se respetan las reglas duras.</b> Carga refrigerada, peligrosa o sobredimensionada solo la mueve un proveedor con esa certificación; el proveedor debe tener el vehículo y una tarifa en esa ruta; no puede trabajar antes de su fecha de alta; el precio pactado debe ser una tarifa real de ese proveedor.</td></tr>
<tr><td class='c'>Exactitud / realismo</td><td><b>Se parece al mundo real.</b> Distancias de Buenaventura iguales a las de la fuente; puntualidad global entre 60 % y 92 %; margen al cliente razonable; pocas solicitudes Urgentes (menos del 35 %); menos solicitudes en fines de semana.</td></tr>
<tr><td class='c'>Oportunidad</td><td><b>Nada del futuro.</b> Un dato «histórico» no puede traer entregas posteriores al corte, y la capacidad se guarda con una foto por semana para saber qué se sabía en cada fecha.</td></tr>
</tbody></table>
<h3>Resultado de la revisión</h3>
<table class='cols'><tbody>
<tr><td class='c'>Base limpia</td><td>33 de 35 reglas cumplidas, <b>0 críticas fallidas</b>. Los 2 avisos son esperables: 144 solicitudes (2,5 %) no encontraron proveedor con capacidad o certificación (justo los casos «sin opción ideal» que el sistema debe manejar) y dos combinaciones proveedor–vehículo (proveedores nuevos o pequeños) con pocas fotos de capacidad.</td></tr>
<tr><td class='c'>Base con errores</td><td>Se detectan los errores sembrados: <b>9 reglas críticas fallan</b> (duplicados, entregas anteriores al cargue, valores de «a tiempo» vacíos, nombre de proveedor en otro formato, tarifas multiplicadas por mil y eventos fuera del viaje). Sirve para practicar la limpieza.</td></tr>
</tbody></table>
<div class='box'><p><b>Lo que encontró el validador en nuestro propio generador:</b> al principio, algunas entregas marcadas «a tiempo» estaban un minuto fuera del plazo y los retrasos más largos daban velocidades de 3 a 11 km/h. Lo primero era un error nuestro y se corrigió; lo segundo es realista (cierres viales y filas en el puerto de Buenaventura) y se ajustó la regla. Así se usa el validador: <b>cada vez que cambien el generador, lo ejecutan.</b></p></div>
<h3>Supuestos propios por calibrar</h3>
<p class='small'>Los rangos de precio por kilómetro, velocidad, puntualidad global y margen al cliente son supuestos del equipo, no cifras oficiales. Se pueden refinar con las tarifas del SICE-TAC si el tiempo lo permite; si alguien del jurado pregunta, la respuesta es que son parámetros editables en <code>seed/config.py</code>.</p>
<h3>Fuentes</h3>
<p class='small'>Cámara de Comercio de Buenaventura (presentación en el foro «Movilidad hacia el Pacífico», Universidad Icesi): distancias y cierres viales. Ministerio de Transporte: SICE-TAC. IBM Docs «Data quality dimensions» y Dagster «Data quality checks»: dimensiones de calidad.</p>
<p class='small'>Los ejemplos del documento son datos sintéticos generados para el proyecto. Plantilla en Excel para completar: <b>plantilla_datos.xlsx</b>.</p>
</body></html>"""
Path("guia_datos.html").write_text(doc, encoding="utf8")

# ---- plantilla Excel ----
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment
from openpyxl.utils import get_column_letter
wb = Workbook(); ws = wb.active; ws.title = "LEEME"
for i, l in enumerate(["Plantilla de datos · Recomendador de proveedores COSCO",
 "Una hoja por tabla. La fila 1 son los nombres de columna (no cambiarlos). Las filas 2 a 4 son ejemplos reales de nuestros datos sintéticos: borrarlas al pegar los datos reales.",
 "Hojas Indispensable: corredor, tipo_vehiculo, proveedor, certificacion, flota, tarifa, solicitud, servicio.",
 "Hojas Deseable: cliente, capacidad_snapshot, evento_servicio, feedback.",
 "Las hojas recomendacion, decision, estadistica_proveedor y modelo_version las llena el sistema; no se piden.",
 "Fechas: AAAA-MM-DDTHH:MM. Dinero: pesos enteros. Vacío = celda sin nada."], 1):
    ws.cell(i, 1, l); ws.cell(i, 1).font = Font(bold=(i == 1), size=13 if i == 1 else 11)
ws.column_dimensions["A"].width = 130
for t, *_ in T:
    if t in ("recomendacion", "decision", "estadistica_proveedor", "modelo_version"): continue
    sh = wb.create_sheet(t); cols = [r[1] for r in con.execute(f"PRAGMA table_info({t})")]
    sh.append(cols)
    ex = q(f"SELECT * FROM {t} {'WHERE servicio_id=\'S000079\'' if t in ('evento_servicio','feedback') else ''} LIMIT 3")
    for r in ex: sh.append(list(r.values()))
    for j, c in enumerate(cols, 1):
        cell = sh.cell(1, j); cell.font = Font(bold=True, color="FFFFFF"); cell.fill = PatternFill("solid", fgColor="0F1729")
        sh.column_dimensions[get_column_letter(j)].width = max(14, len(c) + 4)
    sh.freeze_panes = "A2"
wb.save("plantilla_datos.xlsx")
print("ok")
