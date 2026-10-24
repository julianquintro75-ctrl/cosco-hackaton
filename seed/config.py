"""Mundo sintetico: corredores, vehiculos, proveedores y sus 'historias' (verdad oculta).
CIFRAS ILUSTRATIVAS: calibrar precios con SICE-TAC (Min. Transporte) y distancias con rutas reales."""
from datetime import date

INICIO = date(2025, 11, 1)
FIN_HISTORICO = date(2026, 9, 30)
FIN = date(2026, 10, 15)           # 1-15 oct 2026 = fase de prueba

CORREDORES = [  # id, origen, destino, puerto, km (aprox.), riesgo_vial, peso_demanda, pacifico
    ("C1", "Buenaventura", "Bogota", "Buenaventura", 519, 0.75, 0.22, True),
    ("C2", "Buenaventura", "Cali", "Buenaventura", 165, 0.55, 0.12, True),
    ("C3", "Buenaventura", "Medellin", "Buenaventura", 499, 0.70, 0.08, True),
    ("C4", "Cartagena", "Bogota", "Cartagena", 1050, 0.45, 0.20, False),
    ("C5", "Cartagena", "Medellin", "Cartagena", 640, 0.40, 0.12, False),
    ("C6", "Santa Marta", "Bogota", "Santa Marta", 960, 0.45, 0.08, False),
    ("C7", "Barranquilla", "Medellin", "Barranquilla", 690, 0.40, 0.10, False),
    ("C8", "Cartagena", "Bucaramanga", "Cartagena", 700, 0.45, 0.08, False),
]
VEHICULOS = [  # id, nombre, ton, contenedor, multiplicador de precio
    ("V40", "Tractomula 40'", 32, "40", 1.00),
    ("V20", "Tractomula 20'", 22, "20", 0.75),
    ("VRF", "Reefer 40'", 28, "40", 1.45),
    ("VCB", "Cama baja", 35, "-", 1.60),
    ("VSE", "Camion sencillo", 10, "-", 0.55),
]
PRECIO_KM, PRECIO_FIJO = 5200, 600_000          # COP, base ilustrativa para tractomula 40'
INFLACION_TRIM = 0.012                            # alza de tarifas por trimestre

def s_const(p):
    return lambda d, c: p

def s_andina(d, c):        # excelente hasta julio, se degrada desde el 1 de agosto
    if d < date(2026, 8, 1): return 0.06
    k = min((d - date(2026, 8, 1)).days / 20, 1)
    return 0.06 + k * 0.29

def s_transpacifico(d, c):  # mala al inicio, mejora entre abril y junio
    if d < date(2026, 4, 1): return 0.30
    if d > date(2026, 6, 30): return 0.09
    k = (d - date(2026, 4, 1)).days / 90
    return 0.30 - k * 0.21

def s_caribe(d, c):         # fuerte en el Caribe, debil en el Pacifico
    return 0.30 if c in ("C1", "C2", "C3") else 0.08

def s_altiplano(d, c):      # un paro de dos semanas (evento puntual, no deterioro)
    if date(2026, 3, 10) <= d <= date(2026, 3, 24): return 0.55
    return 0.12

# id, nombre, ciudad, alta, mult_precio, historia, p_incidente, p_cancel, spread(variabilidad), flota, certs, corredores, peso_habito
PROVEEDORES = [
    ("P01", "Andina Cargo", "Bogota", date(2019, 3, 1), 1.02, s_andina, 0.010, 0.02, .28, {"V40": 14, "V20": 8, "VSE": 4}, [], ["C1","C2","C3","C4","C5"], 2.4),
    ("P02", "TransPacifico", "Cali", date(2018, 6, 1), 0.92, s_transpacifico, 0.015, 0.04, .30, {"V40": 12, "V20": 6}, [], ["C1","C2","C3"], 1.4),
    ("P03", "Caribe Express", "Barranquilla", date(2017, 2, 1), 1.00, s_caribe, 0.008, 0.02, .28, {"V40": 16, "V20": 6, "VRF": 3}, ["REEFER"], ["C1","C2","C4","C5","C6","C7","C8"], 1.8),
    ("P04", "Nuevo Rumbo", "Bogota", date(2026, 8, 15), 0.95, s_const(0.07), 0.008, 0.02, .28, {"V40": 6, "V20": 3}, [], ["C1","C4","C7"], 0.6),
    ("P05", "Economica del Sur", "Cali", date(2016, 9, 1), 0.86, s_const(0.26), 0.022, 0.06, .30, {"V40": 18, "V20": 10, "VSE": 6}, [], ["C1","C2","C3","C4","C5","C6","C7","C8"], 1.6),
    ("P06", "Premium Logistics", "Bogota", date(2015, 1, 1), 1.22, s_const(0.04), 0.004, 0.01, .22, {"V40": 10, "V20": 6, "VCB": 3}, ["SOBREDIMENSIONADA"], ["C1","C4","C5","C6","C7","C8"], 1.0),
    ("P07", "Mulas del Valle", "Cali", date(2014, 5, 1), 0.98, s_const(0.14), 0.012, 0.03, .30, {"V40": 30, "V20": 14, "VSE": 8}, [], ["C1","C2","C3","C4","C5","C6","C7","C8"], 3.0),
    ("P08", "FrioCol", "Medellin", date(2018, 11, 1), 1.10, s_const(0.09), 0.006, 0.02, .26, {"VRF": 9, "V40": 4}, ["REEFER"], ["C3","C4","C5","C7","C8"], 1.2),
    ("P09", "Seguridad Total", "Cartagena", date(2016, 4, 1), 1.12, s_const(0.10), 0.003, 0.02, .26, {"V40": 8, "V20": 4}, ["IMO"], ["C1","C4","C5","C6","C7","C8"], 1.1),
    ("P10", "Rapido SAS", "Bogota", date(2019, 8, 1), 1.04, s_const(0.18), 0.015, 0.03, .50, {"V40": 10, "V20": 5}, [], ["C1","C3","C4","C5","C6"], 1.0),
    ("P11", "Veteranos del Camino", "Bucaramanga", date(2012, 1, 1), 1.01, s_const(0.10), 0.009, 0.02, .27, {"V40": 3, "V20": 2, "VSE": 2}, [], ["C4","C5","C6","C8"], 1.0),
    ("P12", "Altiplano Trans", "Tunja", date(2015, 7, 1), 0.97, s_altiplano, 0.011, 0.03, .29, {"V40": 11, "V20": 5, "VCB": 2}, ["SOBREDIMENSIONADA"], ["C1","C4","C5","C6","C8"], 1.3),
]
LLUVIA_MESES = {4, 5, 10, 11}
PESO_LLUVIA = {"P06": 0.4, "P09": 0.6}      # que tanto les afecta la temporada de lluvias en el Pacifico (default 1)
NIVEL_PROB = {"Flexible": 0.30, "Estandar": 0.50, "Urgente": 0.20}
HOLGURA = {"Flexible": 1.20, "Estandar": 1.20, "Urgente": 1.10}   # entrega_planeada = T0 * holgura
VENTANA_FLEX_H = 72
PRIMA_NIVEL = {"Flexible": 0.97, "Estandar": 1.22, "Urgente": 1.60}
MARGEN_BASE = 1.16
