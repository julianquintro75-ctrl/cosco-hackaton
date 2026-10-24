export interface Desglose { precio: number; retraso_esperado: number; incidente_esperado: number; incertidumbre: number; concentracion: number }
export interface Evaluado {
  posicion: number; proveedor_id: string; nombre: string; costo_esperado: number; desglose: Desglose; margen_esperado: number;
  p_a_tiempo: number; ic90_p_a_tiempo: [number, number]; transito_p50_h: number; transito_p90_h: number; n_servicios_corredor: number;
  indice_dureza: number | null; banda_dureza: 'Diamante' | 'Zafiro' | 'Cuarzo' | 'Yeso' | null; capacidad_unidades: number | null;
  alertas: string[]; factores_clave: string[];
}
export interface Descartado { proveedor_id: string; motivo: string; detalle: string }
export interface Recomendacion {
  recomendacion_id: string; solicitud_id: string; modelo_version: string; ranking: Evaluado[]; descartados: Descartado[];
  requiere_revision: boolean; motivos_revision: string[]; escalar_gerencia: boolean; sugerencia_prueba: { proveedor_id: string; razon: string } | null;
  confianza: number; explicacion_texto: string | null; latencia_ms: number | null; generado_en: string;
}
export type Nivel = 'Flexible' | 'Estandar' | 'Urgente';
export interface Solicitud {
  solicitud_id: string; cliente_id: string; corredor_id: string; tipo_vehiculo_req: string; tipo_carga: string; peso_ton: number;
  mercancia_peligrosa: number; fecha_solicitud: string; fecha_cargue: string; plazo_entrega: string; nivel_servicio: Nivel; tarifa_cliente: number;
}
export interface Pendiente { recomendacion: Recomendacion; solicitud: Solicitud }
export interface Ficha {
  proveedor_id: string; nombre: string; ciudad_base: string; fecha_alta: string; as_of: string; servicios_entregados: number;
  puntualidad_general: number; dureza_media: number | null; cuota_30d: number; certificaciones: string[];
  capacidad: { vehiculo: string; flota: number; disponibles: number; reporte: string }[];
  fortalezas: string[]; debilidades: string[]; riesgos: string[];
  estadisticas: { corredor_id: string; tipo_carga: string; p_tarde: number; n_servicios: number; indice_dureza: number | null; banda_dureza: string | null; transito_p50_h: number; transito_p90_h: number }[];
}
export interface Tablas {
  proveedor: { proveedor_id: string; nombre: string; ciudad_base: string; activo: number }[];
  corredor: { corredor_id: string; origen: string; destino: string; puerto: string; distancia_km: number }[];
  tipo_vehiculo: { tipo_vehiculo_id: string; nombre: string; capacidad_ton: number }[];
  cliente: { cliente_id: string; nombre: string; segmento: string; prioridad: number }[];
  flota: { proveedor_id: string; tipo_vehiculo_id: string; cantidad: number }[];
  tarifa: { proveedor_id: string; corredor_id: string; tipo_vehiculo_id: string; precio_cop: number; vigente_desde: string; vigente_hasta: string | null }[];
  capacidad_snapshot: { proveedor_id: string; tipo_vehiculo_id: string; fecha_hora: string; unidades_disponibles: number }[];
  servicios: { proveedor_id: string; entrega_real: string | null; a_tiempo: number | null; estado: string; corredor_id: string }[];
}
export interface NuevaSolicitud {
  cliente_id: string; corredor_id: string; tipo_vehiculo_req: string; tipo_carga: 'general' | 'refrigerada' | 'peligrosa' | 'sobredimensionada';
  peso_ton: number; fecha_cargue: string; plazo_entrega: string; nivel_servicio: Nivel; tarifa_cliente: number; clave_envio: string;
}
export type MotivoDevolucion = 'datos_incompletos' | 'sin_viabilidad_comercial' | 'cliente_cancelo' | 'precio_fuera_de_rango' | 'otro';
export interface Devolucion { solicitud_id: string; usuario: string; motivo: MotivoDevolucion; nota: string | null; fecha: string }
export type Rol = 'solicitante' | 'operador' | 'gerencia';
export interface MiSolicitud {
  solicitud_id: string; solicitante: string; fecha: string; estado: 'lista' | 'en_revision' | 'escalada' | 'decidida' | 'devuelta';
  proveedor_sugerido: string | null; proveedor_elegido: string | null; decidida_por: string | null; motivos: string[];
  devuelta_por: string | null; motivo_devolucion: string | null; nota_devolucion: string | null;
}
export interface AjustesAvisos { slack_activo: boolean; avisar_revision: boolean; avisar_escalamiento: boolean }
export interface EstadoAvisos { ajustes: AjustesAvisos; webhooks: { operaciones: boolean; gerencia: boolean } }
export interface Aviso { id: number; fecha: string; evento: string; solicitud_id: string | null; destino: string; estado: string; detalle: string }
export interface Sesion { access_token: string; expira_en: number; usuario: { usuario: string; nombre: string; rol: Rol } }
