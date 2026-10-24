"""Contratos del sistema (entrada/salida del motor y de la API). Fuente unica de verdad.
Todos los motores (A nuestro, B Jev, C LLM) deben respetar estos tipos.
Dinero en COP (entero). Fechas/horas en ISO-8601."""
from __future__ import annotations
from datetime import datetime
from enum import Enum
from typing import Literal, Optional
from pydantic import BaseModel, Field, model_validator


class Nivel(str, Enum):
    FLEXIBLE = "Flexible"
    ESTANDAR = "Estandar"
    URGENTE = "Urgente"


TipoCarga = Literal["general", "refrigerada", "peligrosa", "sobredimensionada"]


# ---------- ENTRADA ----------
class SolicitudIn(BaseModel):
    solicitud_id: str
    cliente_id: str
    corredor_id: str
    tipo_vehiculo_req: str
    tipo_carga: TipoCarga = "general"
    peso_ton: float = Field(gt=0)
    mercancia_peligrosa: bool = False
    fecha_cargue: datetime
    plazo_entrega: datetime
    nivel_servicio: Nivel = Nivel.ESTANDAR
    tarifa_cliente: int = Field(gt=0, description="Lo que COSCO cobra al cliente (para el margen)")
    as_of: Optional[datetime] = Field(None, description="Fecha 'ahora' del sistema; permite reproducir el pasado sin ver el futuro")

    @model_validator(mode="after")
    def _plazo_coherente(self):
        if self.plazo_entrega <= self.fecha_cargue:
            raise ValueError("plazo_entrega debe ser posterior a fecha_cargue")
        return self


# ---------- SALIDA ----------
class DesgloseCosto(BaseModel):
    precio: int
    retraso_esperado: int
    incidente_esperado: int
    incertidumbre: int
    concentracion: int

    @property
    def total(self) -> int:
        return self.precio + self.retraso_esperado + self.incidente_esperado + self.incertidumbre + self.concentracion


class ProveedorEvaluado(BaseModel):
    posicion: int = Field(ge=1)
    proveedor_id: str
    nombre: str
    costo_esperado: int
    desglose: DesgloseCosto
    margen_esperado: int
    p_a_tiempo: float = Field(ge=0, le=1)
    ic90_p_a_tiempo: tuple[float, float]
    transito_p50_h: float
    transito_p90_h: float
    n_servicios_corredor: int
    indice_dureza: Optional[float] = Field(None, ge=0, le=10)
    banda_dureza: Optional[Literal["Diamante", "Zafiro", "Cuarzo", "Yeso"]] = None
    capacidad_unidades: Optional[int] = None
    alertas: list[str] = []
    factores_clave: list[str] = []          # explicacion (SHAP / diferencias de componentes)


class Descartado(BaseModel):
    proveedor_id: str
    motivo: Literal["sin_vehiculo", "sin_capacidad", "sin_cobertura", "sin_certificacion", "inactivo", "fuera_de_plazo"]
    detalle: str = ""


class SugerenciaPrueba(BaseModel):
    proveedor_id: str
    razon: str


class RecomendacionOut(BaseModel):
    recomendacion_id: str
    solicitud_id: str
    modelo_version: str
    motor: Literal["A_propio", "B_jev", "C_llm", "hibrido"] = "A_propio"
    ranking: list[ProveedorEvaluado] = Field(max_length=3)      # Top-3
    descartados: list[Descartado] = []
    requiere_revision: bool
    motivos_revision: list[str] = []                             # p.ej. "empate_tecnico", "urgente", "confianza_baja"
    escalar_gerencia: bool = False
    sugerencia_prueba: Optional[SugerenciaPrueba] = None
    confianza: float = Field(ge=0, le=1)
    explicacion_texto: Optional[str] = None
    latencia_ms: Optional[float] = None
    generado_en: datetime


# ---------- EVENTOS DE LA OPERACION ----------
class DecisionIn(BaseModel):
    recomendacion_id: Optional[str] = None
    solicitud_id: str
    proveedor_elegido: str
    usuario: str
    motivo: Optional[Literal["precio", "relacion", "capacidad", "experiencia_previa", "cliente_pidio", "otro"]] = None

    @property
    def acepto(self) -> bool:  # se calcula contra la recomendacion en el servidor
        return self.motivo is None


class CierreServicioIn(BaseModel):
    """Se envia al cerrar un servicio; dispara la actualizacion bayesiana inmediata."""
    servicio_id: str
    entrega_real: datetime
    a_tiempo: bool
    costo_final: int
    dias_detencion: int = 0
    hubo_incidente: bool = False
    feedback_puntaje: Optional[int] = Field(None, ge=1, le=3)
    feedback_causa: Optional[Literal["proveedor", "cliente", "puerto", "clima", "otro"]] = None


class MotorDecision:
    """Interfaz que cumplen A (propio), B (Jev) y C (LLM). Mismo contrato, medibles con el mismo banco."""
    nombre: str = "base"

    def recomendar(self, solicitud: SolicitudIn) -> RecomendacionOut:  # pragma: no cover
        raise NotImplementedError
