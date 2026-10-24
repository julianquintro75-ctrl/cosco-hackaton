"""Seguimiento de servicios en ruta: un puerto (FuenteUbicacion) y un adaptador simulado.

Hoy no hay GPS: SimuladorUbicacion genera un recorrido creíble a partir del tiempo de tránsito estimado del proveedor
(o de los tiempos reales, si el servicio ya se entregó). Mañana, un adaptador real (telemetría del proveedor, sticker GPS,
eventos 'GPS' de la tabla evento_servicio) implementa el mismo método y nada más cambia: ni la API ni el frontend.
Ver docs/SEGUIMIENTO.md.

Las rutas son trazados APROXIMADOS por ciudades intermedias (no son la vía exacta). Un servicio de rutas
(Google Routes, OSRM) podría reemplazarlas sin tocar el resto.
"""
from __future__ import annotations

import hashlib
import math
import random
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Optional, Protocol

ISO = "%Y-%m-%dT%H:%M"

CIUDADES: dict[str, tuple[float, float]] = {
    "Buenaventura": (3.8801, -77.0312), "Loboguerrero": (3.7600, -76.6800), "Dagua": (3.6560, -76.6890), "Cali": (3.4516, -76.5320),
    "Buga": (3.9009, -76.2978), "Tulua": (4.0847, -76.1954), "La Paila": (4.3100, -75.9700), "Armenia": (4.5339, -75.6811),
    "Calarca": (4.5200, -75.6400), "Cajamarca": (4.4400, -75.4300), "Ibague": (4.4389, -75.2322), "Girardot": (4.3017, -74.8040),
    "Fusagasuga": (4.3370, -74.3640), "Bogota": (4.7110, -74.0721), "Cartago": (4.7464, -75.9117), "Pereira": (4.8133, -75.6961),
    "Chinchina": (4.9830, -75.6030), "La Pintada": (5.7430, -75.6050), "Caldas": (6.0910, -75.6360), "Medellin": (6.2442, -75.5812),
    "Cartagena": (10.3910, -75.4794), "El Carmen de Bolivar": (9.7170, -75.1210), "Plato": (9.7900, -74.7820), "Bosconia": (9.9760, -73.8890),
    "Aguachica": (8.3090, -73.6160), "San Alberto": (7.7610, -73.3920), "Puerto Araujo": (6.5300, -74.1000), "Puerto Boyaca": (5.9760, -74.5880),
    "Villeta": (5.0120, -74.4730), "Sincelejo": (9.3047, -75.3978), "Planeta Rica": (8.4110, -75.5850), "Caucasia": (7.9860, -75.1930),
    "Yarumal": (6.9630, -75.4170), "Santa Marta": (11.2408, -74.1990), "Cienaga": (11.0070, -74.2470), "Fundacion": (10.5210, -74.1860),
    "Barranquilla": (10.9685, -74.7813), "Sabanalarga": (10.6310, -74.9220), "Bucaramanga": (7.1193, -73.1227),
}

_CARIBE_ANDES = ["Bosconia", "Aguachica", "San Alberto", "Puerto Araujo", "Puerto Boyaca", "Villeta", "Bogota"]
RUTAS: dict[str, list[str]] = {
    "C1": ["Buenaventura", "Loboguerrero", "Buga", "Tulua", "La Paila", "Armenia", "Calarca", "Cajamarca", "Ibague", "Girardot", "Fusagasuga", "Bogota"],
    "C2": ["Buenaventura", "Loboguerrero", "Dagua", "Cali"],
    "C3": ["Buenaventura", "Loboguerrero", "Buga", "Tulua", "Cartago", "Pereira", "Chinchina", "La Pintada", "Caldas", "Medellin"],
    "C4": ["Cartagena", "El Carmen de Bolivar", "Plato"] + _CARIBE_ANDES,
    "C5": ["Cartagena", "El Carmen de Bolivar", "Sincelejo", "Planeta Rica", "Caucasia", "Yarumal", "Medellin"],
    "C6": ["Santa Marta", "Cienaga", "Fundacion"] + _CARIBE_ANDES,
    "C7": ["Barranquilla", "Sabanalarga", "El Carmen de Bolivar", "Sincelejo", "Planeta Rica", "Caucasia", "Yarumal", "Medellin"],
    "C8": ["Cartagena", "El Carmen de Bolivar", "Plato", "Bosconia", "Aguachica", "San Alberto", "Bucaramanga"],
}


@dataclass
class Punto:
    t: str          # fecha y hora (ISO, minutos)
    lat: float
    lon: float
    evento: Optional[str] = None   # 'salida' | 'parada' | 'reanuda' | 'llegada'


@dataclass
class Traza:
    servicio_id: str
    simulado: bool
    ruta: list[tuple[float, float]]
    puntos: list[Punto] = field(default_factory=list)
    fuente: str = "simulador"


@dataclass
class ServicioEnRuta:
    """Lo mínimo que una fuente de ubicación necesita saber de un servicio."""
    servicio_id: str
    corredor_id: str
    salida: datetime               # cargue real o planeado
    llegada: Optional[datetime]    # entrega real (si ya se entregó)
    transito_p50_h: float
    transito_p90_h: float
    p_tarde: float
    entrega_planeada: datetime


class FuenteUbicacion(Protocol):
    """Puerto. Un adaptador real (GPS, telemetría del proveedor) implementa este método con la misma firma."""
    nombre: str

    def traza(self, s: ServicioEnRuta) -> Traza: ...


def _haversine_km(a: tuple[float, float], b: tuple[float, float]) -> float:
    la1, lo1, la2, lo2 = map(math.radians, (*a, *b))
    h = math.sin((la2 - la1) / 2) ** 2 + math.cos(la1) * math.cos(la2) * math.sin((lo2 - lo1) / 2) ** 2
    return 2 * 6371 * math.asin(math.sqrt(h))


def ruta_de(corredor_id: str) -> list[tuple[float, float]]:
    return [CIUDADES[c] for c in RUTAS[corredor_id]]


def _en_ruta(ruta: list[tuple[float, float]], f: float) -> tuple[float, float]:
    """Punto a la fracción f (0..1) de la longitud de la ruta."""
    tramos = [_haversine_km(a, b) for a, b in zip(ruta, ruta[1:])]
    objetivo, acum = max(0.0, min(1.0, f)) * sum(tramos), 0.0
    for (a, b), d in zip(zip(ruta, ruta[1:]), tramos):
        if acum + d >= objetivo:
            u = (objetivo - acum) / d if d else 0
            return (a[0] + (b[0] - a[0]) * u, a[1] + (b[1] - a[1]) * u)
        acum += d
    return ruta[-1]


class SimuladorUbicacion:
    """Adaptador simulado y determinista (misma entrada → mismo recorrido).

    - Servicio entregado: el recorrido dura lo que duró en la realidad (cargue_real → entrega_real).
    - Servicio en curso: dura el tránsito típico del proveedor (p50); con probabilidad p_tarde hay una parada
      larga que lo lleva hacia el pesimista (p90) o más allá, como pasaría con un retraso real.
    """
    nombre = "simulador"

    def __init__(self, n_puntos: int = 60):
        self.n = n_puntos

    def traza(self, s: ServicioEnRuta) -> Traza:
        ruta = ruta_de(s.corredor_id)
        rnd = random.Random(int(hashlib.sha256(s.servicio_id.encode()).hexdigest()[:12], 16))
        if s.llegada is not None:
            total_h = max(1.0, (s.llegada - s.salida).total_seconds() / 3600)
            tarde = s.llegada > s.entrega_planeada
        else:
            tarde = rnd.random() < s.p_tarde
            total_h = s.transito_p50_h * rnd.uniform(0.92, 1.08)
            if tarde:
                total_h = max(total_h, s.transito_p90_h * rnd.uniform(1.0, 1.25))
        parada_h = 0.0
        if tarde:
            parada_h = min(total_h * 0.45, max(1.0, total_h - s.transito_p50_h))
        parada_en = rnd.uniform(0.35, 0.7)                     # en qué parte del recorrido se detiene
        mov_h = total_h - parada_h
        # avance no uniforme: más lento en montaña (ruido suave), siempre creciente
        pesos = [rnd.uniform(0.75, 1.25) for _ in range(self.n)]
        acum = [0.0]
        for w in pesos:
            acum.append(acum[-1] + w)
        avance = [a / acum[-1] for a in acum]
        puntos: list[Punto] = []
        t = s.salida
        dt = timedelta(hours=mov_h / self.n)
        parado = False
        for i, f in enumerate(avance):
            lat, lon = _en_ruta(ruta, f)
            ev = "salida" if i == 0 else "llegada" if i == len(avance) - 1 else None
            if parada_h and not parado and f >= parada_en:
                puntos.append(Punto(t.strftime(ISO), round(lat, 5), round(lon, 5), "parada"))
                t += timedelta(hours=parada_h)
                parado = True
                ev = "reanuda"
            puntos.append(Punto(t.strftime(ISO), round(lat, 5), round(lon, 5), ev))
            t += dt
        if s.llegada is not None:                               # que la llegada coincida al minuto con la real
            puntos[-1].t = s.llegada.strftime(ISO)
        return Traza(s.servicio_id, True, ruta, puntos, self.nombre)


def crear_fuente(nombre: str = "simulador") -> FuenteUbicacion:
    """Punto único para cambiar de fuente (variable COSCO_UBICACION). Hoy solo existe el simulador."""
    if nombre == "simulador":
        return SimuladorUbicacion()
    raise ValueError(f"fuente de ubicación desconocida: {nombre} (disponible: simulador; ver docs/SEGUIMIENTO.md)")
