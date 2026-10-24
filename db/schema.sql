-- Esquema SQLite del recomendador. Fechas en ISO-8601 (texto). Dinero en pesos colombianos (COP, entero).
PRAGMA foreign_keys = ON;

-- ============ MAESTROS ============
CREATE TABLE IF NOT EXISTS cliente (
  cliente_id TEXT PRIMARY KEY, nombre TEXT NOT NULL,
  segmento TEXT NOT NULL CHECK (segmento IN ('importador','exportador','mixto')),
  prioridad INTEGER NOT NULL CHECK (prioridad BETWEEN 1 AND 3)           -- 1 = clave
);
CREATE TABLE IF NOT EXISTS corredor (
  corredor_id TEXT PRIMARY KEY, origen TEXT NOT NULL, destino TEXT NOT NULL, puerto TEXT NOT NULL,
  distancia_km REAL NOT NULL CHECK (distancia_km > 0), riesgo_vial REAL NOT NULL CHECK (riesgo_vial BETWEEN 0 AND 1)
);
CREATE TABLE IF NOT EXISTS tipo_vehiculo (
  tipo_vehiculo_id TEXT PRIMARY KEY, nombre TEXT NOT NULL, capacidad_ton REAL NOT NULL, contenedor TEXT
);
CREATE TABLE IF NOT EXISTS proveedor (
  proveedor_id TEXT PRIMARY KEY, nombre TEXT NOT NULL, nit TEXT, ciudad_base TEXT,
  fecha_alta TEXT NOT NULL, activo INTEGER NOT NULL DEFAULT 1
);
CREATE TABLE IF NOT EXISTS certificacion (
  proveedor_id TEXT NOT NULL REFERENCES proveedor, tipo TEXT NOT NULL CHECK (tipo IN ('IMO','REEFER','SOBREDIMENSIONADA')),
  vigente_hasta TEXT NOT NULL, PRIMARY KEY (proveedor_id, tipo)
);
CREATE TABLE IF NOT EXISTS flota (
  proveedor_id TEXT NOT NULL REFERENCES proveedor, tipo_vehiculo_id TEXT NOT NULL REFERENCES tipo_vehiculo,
  cantidad INTEGER NOT NULL CHECK (cantidad >= 0), PRIMARY KEY (proveedor_id, tipo_vehiculo_id)
);
CREATE TABLE IF NOT EXISTS tarifa (                       -- una tarifa existente tambien implica cobertura del corredor
  tarifa_id INTEGER PRIMARY KEY AUTOINCREMENT,
  proveedor_id TEXT NOT NULL REFERENCES proveedor, corredor_id TEXT NOT NULL REFERENCES corredor,
  tipo_vehiculo_id TEXT NOT NULL REFERENCES tipo_vehiculo, precio_cop INTEGER NOT NULL CHECK (precio_cop > 0),
  vigente_desde TEXT NOT NULL, vigente_hasta TEXT
);
CREATE INDEX IF NOT EXISTS ix_tarifa ON tarifa (corredor_id, tipo_vehiculo_id, vigente_desde);
CREATE TABLE IF NOT EXISTS capacidad_snapshot (           -- historial: permite reconstruir lo que se sabia en cada fecha
  proveedor_id TEXT NOT NULL REFERENCES proveedor, tipo_vehiculo_id TEXT NOT NULL REFERENCES tipo_vehiculo,
  fecha_hora TEXT NOT NULL, unidades_disponibles INTEGER NOT NULL CHECK (unidades_disponibles >= 0),
  PRIMARY KEY (proveedor_id, tipo_vehiculo_id, fecha_hora)
);

-- ============ OPERACION ============
CREATE TABLE IF NOT EXISTS solicitud (
  solicitud_id TEXT PRIMARY KEY, cliente_id TEXT NOT NULL REFERENCES cliente, corredor_id TEXT NOT NULL REFERENCES corredor,
  tipo_vehiculo_req TEXT NOT NULL REFERENCES tipo_vehiculo,
  tipo_carga TEXT NOT NULL CHECK (tipo_carga IN ('general','refrigerada','peligrosa','sobredimensionada')),
  peso_ton REAL NOT NULL, mercancia_peligrosa INTEGER NOT NULL DEFAULT 0,
  fecha_solicitud TEXT NOT NULL, fecha_cargue TEXT NOT NULL, plazo_entrega TEXT NOT NULL,
  nivel_servicio TEXT NOT NULL CHECK (nivel_servicio IN ('Flexible','Estandar','Urgente')),
  tarifa_cliente INTEGER NOT NULL,
  fase TEXT NOT NULL DEFAULT 'historico' CHECK (fase IN ('historico','prueba','vivo'))
);
CREATE INDEX IF NOT EXISTS ix_sol_fecha ON solicitud (fecha_cargue);
CREATE TABLE IF NOT EXISTS servicio (
  servicio_id TEXT PRIMARY KEY, solicitud_id TEXT NOT NULL REFERENCES solicitud, proveedor_id TEXT NOT NULL REFERENCES proveedor,
  precio_pactado INTEGER NOT NULL, cargue_real TEXT, entrega_planeada TEXT NOT NULL, entrega_real TEXT,
  a_tiempo INTEGER, costo_final INTEGER, dias_detencion INTEGER DEFAULT 0,
  estado TEXT NOT NULL CHECK (estado IN ('ENTREGADO','CANCELADO','RECHAZADO','EN_CURSO'))   -- EN_CURSO agregado en el paso 7 (asignado, sin cierre)
);
CREATE INDEX IF NOT EXISTS ix_serv_prov ON servicio (proveedor_id, entrega_real);
CREATE TABLE IF NOT EXISTS evento_servicio (
  evento_id INTEGER PRIMARY KEY AUTOINCREMENT, servicio_id TEXT NOT NULL REFERENCES servicio,
  tipo TEXT NOT NULL CHECK (tipo IN ('GPS','NOVEDAD','INCIDENTE','DANO')), fecha_hora TEXT NOT NULL, detalle TEXT
);
CREATE TABLE IF NOT EXISTS feedback (
  servicio_id TEXT NOT NULL REFERENCES servicio, canal TEXT NOT NULL CHECK (canal IN ('WhatsApp','operador')),
  puntaje INTEGER NOT NULL CHECK (puntaje BETWEEN 1 AND 3), causa TEXT
);

-- ============ INTELIGENCIA Y TRAZABILIDAD ============
CREATE TABLE IF NOT EXISTS modelo_version (
  modelo_version TEXT PRIMARY KEY, tipo TEXT NOT NULL, metricas_validacion TEXT, fecha TEXT NOT NULL, aprobado_por TEXT
);
CREATE TABLE IF NOT EXISTS recomendacion (
  recomendacion_id TEXT PRIMARY KEY, solicitud_id TEXT NOT NULL REFERENCES solicitud, modelo_version TEXT REFERENCES modelo_version,
  top3_y_desglose TEXT NOT NULL,            -- JSON: contrato RecomendacionOut
  confianza REAL, requiere_revision INTEGER NOT NULL DEFAULT 0, fecha TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS decision (
  decision_id TEXT PRIMARY KEY, solicitud_id TEXT NOT NULL REFERENCES solicitud,
  recomendacion_id TEXT REFERENCES recomendacion,   -- NULL en decisiones historicas (antes del sistema)
  proveedor_elegido TEXT NOT NULL REFERENCES proveedor, usuario TEXT, acepto_recomendacion INTEGER, motivo TEXT, fecha TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS estadistica_proveedor (
  proveedor_id TEXT NOT NULL REFERENCES proveedor, corredor_id TEXT NOT NULL REFERENCES corredor, tipo_carga TEXT NOT NULL,
  alfa REAL NOT NULL, beta REAL NOT NULL, p_tarde REAL, ic90_ancho REAL, transito_p50_h REAL, transito_p90_h REAL,
  n_servicios REAL NOT NULL, tasa_incidente REAL, indice_dureza REAL, actualizado TEXT NOT NULL,
  nivel_respaldo TEXT,                      -- agregado en el paso 4: corredor | corredor_cualquier_carga | proveedor | global
  PRIMARY KEY (proveedor_id, corredor_id, tipo_carga)
);
