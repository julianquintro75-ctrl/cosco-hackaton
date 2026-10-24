# Pasos y prompts para construir el recomendador (20 horas)

Cómo usarlo: pega **un prompt a la vez** en Claude Code, dentro de la carpeta del proyecto. No pases al siguiente hasta cumplir el **«Listo cuando»** del paso. Si un paso falla, pega el error tal cual y pide que lo arregle antes de seguir.

Estado actual: **los pasos 0 a 2 ya están hechos** (esquema, contratos y datos semilla). Empieza en el paso 3.

| Paso | Qué | Horas | Quién lidera |
|---|---|---|---|
| 0–2 | Esquema, contratos, datos semilla | hecho | sistemas |
| 3 | Verificar datos y contar la historia | 0,5 | sistemas |
| 4 | Estadísticas bayesianas con decaimiento | 1,5 | sistemas |
| 5 | Motor de recomendación (filtros + costo esperado) | 2 | sistemas |
| 6 | Pruebas de casos difíciles | 1 | sistemas |
| 7 | API y registro de decisiones | 1,5 | mecatrónica |
| 8 | Interfaz del operador | 3 | mecatrónica |
| 9 | Aprendizaje en vivo (repetición del tiempo) | 1,5 | control + sistemas |
| 10 | Modelos M1 y M2 (CatBoost / LightGBM) | 2,5 | sistemas |
| 11 | Backtest y validación | 1,5 | sistemas + control |
| 12 | Tableros | 2 | mecánica |
| 13 | Banco de comparación: nuestro motor frente a Jev y un LLM | 2 | sistemas |
| 14 | Congelar, guion de demo y video de respaldo | 2 | todos |

Regla de oro: a la hora 8 debe existir una versión de punta a punta, aunque sea fea (pasos 3 a 8 con el motor sin ML). Los modelos de ML (paso 10) mejoran un sistema que ya funciona; no lo reemplazan.

---

## Paso 0 · Preparar el entorno  *(hecho; repetir en cada computador)*

```
Crea un entorno virtual en la carpeta del proyecto, instala requirements.txt y verifica que
python -c "import pandas, numpy, scipy, pydantic, fastapi, streamlit, catboost, lightgbm" funciona.
Si alguna librería falla, dime cuál y propón la alternativa más simple.
```
**Listo cuando:** el comando de verificación no imprime errores.

## Paso 1 · Esquema y contratos  *(hecho)*

Archivos: `db/schema.sql` (16 tablas del diagrama ER) y `contratos/contracts.py` (entradas y salidas: `SolicitudIn`, `RecomendacionOut`, `DecisionIn`, `CierreServicioIn`, y la interfaz `MotorDecision`). Los JSON Schema están en `contratos/json_schema/`.

Regla del equipo: **si cambias un contrato, se avisa a todos**. Interfaz, motor y tableros dependen de él.

## Paso 2 · Datos semilla con historias  *(hecho)*

`python seed/generate.py --sucio` crea `data/cosco.db` (limpia), `data/cosco_sucio.db` (con errores para practicar limpieza) y `data/verdad_oculta.csv` (la probabilidad real de retraso por semana; **el modelo nunca la lee**, solo sirve para evaluar).

Historias incluidas (están en `seed/config.py`):

| Proveedor | Historia | Qué demuestra |
|---|---|---|
| Andina Cargo | Excelente hasta julio; desde el 1 de agosto se degrada (6 % → 35 % de retrasos) | Detección de deterioro |
| TransPacífico | Mala al inicio; mejora de abril a junio | Detección de mejora |
| Caribe Express | Fuerte en el Caribe, débil en el Pacífico | Fortaleza/debilidad por corredor |
| Nuevo Rumbo | Entra en agosto de 2026 con 19 servicios | Proveedor nuevo, sugerencia de prueba |
| Altiplano Trans | Paro de dos semanas en marzo (evento puntual) | No sobrerreaccionar |
| Mulas del Valle | Cuota del 26 % al 36 % | Concentración |
| Premium Logistics | Caro y casi perfecto | Compromiso precio–confiabilidad |
| FríoCol, Seguridad Total | Únicos con certificación reefer / IMO en varios corredores | Filtros duros |
| Rápido SAS | Rápido pero muy variable | P90 frente a P50 |
| Económica del Sur | Barata y mediocre | El «más barato» que sale caro |
| Veteranos del Camino | Flota pequeña | Capacidad limitada |

Las decisiones históricas las toma una «política humana» simulada (favorece al barato y al de siempre), así que los datos tienen el sesgo de selección real: esto es intencional, porque el backtest debe enfrentarlo.

Del 1 al 15 de octubre de 2026 las solicitudes quedan marcadas `fase='prueba'`: son los casos de la demostración.

COSCO confirmó que **no entregará datos**: todo es sintético, y se declara así en la presentación.

Más datos y pruebas en vivo:

```
python seed/en_vivo.py --dias 14 --pausa 3                         # agrega un día simulado cada 3 s (fase 'vivo')
python seed/en_vivo.py --dias 10 --evento P03:0.6:2026-10-20       # daña a Caribe Express desde el 20 de oct (60 % tarde)
python seed/generate.py --seed 11 --out ../data2                   # otra base completamente distinta
python seed/validar_datos.py                                       # 35 reglas de calidad; repetir si se cambia el generador
```

---

## Paso 3 · Verificar los datos y contar la historia

```
Ejecuta seed/generate.py --sucio y luego seed/check_story.py. Revisa que:
(1) Andina Cargo baje de ~95 % a ~65 % de entregas a tiempo desde agosto,
(2) TransPacífico mejore de ~65 % a ~95 % entre abril y junio,
(3) Caribe Express tenga ~65 % a tiempo en los corredores C1–C3 y ~90 % en el resto,
(4) Mulas del Valle aumente su cuota mensual.
Luego abre data/cosco_sucio.db y escribe seed/limpiar.py que detecte y corrija: entregas anteriores al cargue,
a_tiempo vacío, servicios duplicados (ids que empiezan por DUP), nombres de proveedor con otro formato y tarifas con
un factor de 1000. Imprime cuántos registros corrigió de cada tipo y guarda cosco_limpio.db.
```
Ejecuta también `python seed/validar_datos.py` sobre ambas bases: la limpia debe dar 0 reglas críticas fallidas y la sucia unas 9.

**Listo cuando:** las 4 verificaciones se cumplen y `limpiar.py` deja `cosco_limpio.db` con los mismos conteos que `cosco.db`.

> Hallazgo ya medido (siete semillas distintas): el deterioro de Andina se detecta entre 20 y 40 días con vida media de 30 días, entre 26 y 56 con 45 días, y entre 36 y 68 con 90 días (con una semilla ni siquiera antes del 15 de oct); sin decaimiento nunca. El PDF propone 90 días: **probablemente conviene entre 30 y 45**, y el paso 11 lo decide con evidencia (también hay que vigilar falsas alarmas como el paro de Altiplano).

## Paso 4 · Estadísticas bayesianas con decaimiento

```
Crea engine/estadisticas.py. Para cada proveedor × corredor × tipo_carga calcula, usando SOLO servicios entregados
con entrega_real <= as_of (nunca el futuro): alfa y beta con prior Beta(17, 3) (85 % de puntualidad con fuerza 20),
cada servicio ponderado por 0.5 ** (edad_en_días / vida_media) con vida_media configurable (por defecto 45),
p_tarde = (tarde_ponderado + beta0) / (n_ponderado + alfa0 + beta0), el ancho del intervalo de confianza del 90 %
(distribución beta de scipy), percentiles 50 y 90 del tiempo de tránsito real en horas, tasa de incidentes
(con prior), n_servicios y el Índice de Dureza (0–10) con los pesos de la sección 6 del PDF.
Si no hay datos en el corredor, usa el promedio del proveedor, y si tampoco, el prior global, y marca el nivel de respaldo usado.
Escribe los resultados en la tabla estadistica_proveedor. Expón la función calcular(as_of) y actualizar_con_servicio(cierre)
para el aprendizaje incremental. Agrega pruebas: un proveedor con 3 de 3 a tiempo NO debe tener p_tarde < 0.10,
y una llamada con as_of anterior a un servicio no debe contarlo.
```
**Listo cuando:** las pruebas pasan y `calcular("2026-09-30")` llena la tabla con Andina bajando de dureza en septiembre.

## Paso 5 · Motor de recomendación (sin ML todavía)

```
Crea engine/motor_a.py con la clase MotorA que cumple MotorDecision de contratos/contracts.py.
recomendar(solicitud) debe: (1) filtrar proveedores factibles (tarifa vigente en el corredor y vehículo, flota,
certificación si la carga es refrigerada, peligrosa o sobredimensionada, activo en la fecha, capacidad del último
snapshot anterior a as_of) y registrar un Descartado con motivo para cada uno que no pase;
(2) calcular el costo esperado = precio + p_tarde × costo_retraso(nivel) + p_incidente × 8.000.000
+ λ × ancho_IC × costo_retraso(nivel) + penalización de concentración (cuota del proveedor en los últimos 30 días
sobre 35 % → 100.000 por cada punto sobre el umbral), con costo_retraso Flexible 300.000, Estándar 2.500.000, Urgente 6.000.000
(todo en un archivo de configuración editable); (3) ordenar de forma DETERMINISTA y devolver Top-3 con desglose,
margen esperado = tarifa_cliente − costo_esperado, alertas (poco historial, tendencia a empeorar, P90 > plazo,
concentración) y factores_clave como diferencias de componentes frente al siguiente; (4) marcar requiere_revision
si es Urgente, si Top-1 y Top-2 difieren menos de 3 %, si la confianza es baja o no hay candidatos que cumplan el plazo,
y escalar_gerencia si el margen es negativo o nadie cumple el plazo con 90 % de confianza; (5) proponer una sugerencia
de prueba (aparte del ranking) solo en servicios Flexible de bajo riesgo para proveedores con pocos servicios.
La salida debe validar contra RecomendacionOut. Mide la latencia con time.perf_counter.
```
**Listo cuando:** la misma solicitud repetida 100 veces da el mismo JSON, y para las 3 variantes de nivel de una solicitud típica los resultados cambian de forma razonable.

## Paso 6 · Pruebas de casos difíciles

```
Escribe tests/test_casos.py con pytest. Casos: carga refrigerada solo ve proveedores con certificación REEFER;
corredor C2 con vehículo VCB devuelve solo Descartados y requiere_revision; plazo imposible activa escalar_gerencia;
Nuevo Rumbo sale con alerta de poco historial y ranking prudente; Andina Cargo con as_of 2026-07-15 es Top-1 frecuente
y con as_of 2026-09-20 NO lo es en Estándar; el ranking no cambia al reordenar la lista de proveedores; dos llamadas
iguales dan el mismo resultado; ningún Top-3 incluye un proveedor descartado. Corre todo y arregla lo que falle en el motor, no en las pruebas.
```
**Listo cuando:** todos los tests pasan. Este archivo se vuelve la lista de casos de la demostración.

## Paso 7 · API y registro de decisiones

```
Crea app/api.py con FastAPI: POST /recomendar (SolicitudIn → RecomendacionOut y guarda en la tabla recomendacion),
POST /decision (DecisionIn; calcula acepto_recomendacion comparando con el Top-1 y guarda en decision),
POST /cierre (CierreServicioIn; guarda el cierre, el feedback si viene y llama a actualizar_con_servicio),
GET /proveedores/{id}/ficha (estadísticas, dureza, fortalezas y debilidades) y GET /salud.
Valida con los contratos y devuelve errores claros. Agrega un script scripts/demo_api.py que haga una solicitud
completa de punta a punta e imprima cada respuesta.
```
**Listo cuando:** `demo_api.py` recorre solicitud → recomendación → decisión → cierre y las tablas quedan pobladas.

## Paso 8 · Interfaz del operador

```
Crea app/ui.py con Streamlit. Pantalla 1 «Nueva solicitud»: formulario con los campos de SolicitudIn y botón Recomendar.
Pantalla de resultado como la sección 5.10 del PDF: tabla del Top-3 con precio, tránsito P50/P90, vehículo, capacidad,
P(a tiempo) con número de servicios, banda de dureza (💎🔷🔹⚪), costo esperado y margen, alertas en colores, lista de
descartados con motivo, desglose del costo en barras apiladas, y botones «Aprobar #1» y «Elegir otro» (con motivo obligatorio
en lista desplegable). Pantalla «Revisión» para casos que requieren revisión y pantalla «Gerencia» para escalamientos.
Hazla clara y sin adornos: letra legible para proyectar.
```
**Listo cuando:** un compañero que no conoce el proyecto logra aprobar una recomendación sin ayuda.

## Paso 9 · Aprendizaje en vivo (repetición del tiempo)

```
Crea scripts/replay.py: toma los servicios históricos en orden cronológico desde una fecha (por defecto 2026-06-01),
simula el paso del tiempo con un parámetro de velocidad, y para cada día: genera recomendaciones para las solicitudes del día
con MotorA, aplica cierre de los servicios que terminan ese día (actualizando las estadísticas) y guarda por día el
P(tarde) estimado de cada proveedor, su posición media en el ranking y su cuota. Al final imprime el día en que Andina Cargo
cae del Top-3 en Estándar y compáralo con el 2026-08-01 real (verdad_oculta.csv). Exporta los resultados a data/replay.csv
para que el tablero lo muestre en vivo.
```
**Listo cuando:** se ve la caída de Andina Cargo en el tiempo y el retraso de detección queda medido en días.

## Paso 10 · Modelos M1 y M2

```
Crea engine/modelos.py. Variables solo con información previa a la solicitud (sin fuga): corredor, distancia, tipo de carga,
vehículo, nivel, holgura del plazo, día de la semana, mes, temporada de lluvias, proveedor y sus estadísticas móviles
(30/90/365 días), experiencia en el corredor, utilización de capacidad. M1: CatBoostClassifier con variables categóricas y
calibración isotónica para la probabilidad de entrega a tiempo. M2: LightGBM con objetivo quantile (alpha 0.5 y 0.9) para el
tránsito. Entrena con servicios hasta 2026-06-30 y valida en julio–septiembre (división TEMPORAL). Reporta AUC, Brier, curva de calibración
y pinball loss, y compáralos con la línea base bayesiana pura. Si M1 no mejora la línea base, dímelo claramente y deja el
motor con el bayesiano. Guarda los modelos y registra su versión en modelo_version. Agrega SHAP para los factores clave.
```
**Listo cuando:** tienes una tabla «bayesiano vs ML» con métricas y una decisión escrita de cuál usar.

## Paso 11 · Backtest y validación

```
Crea scripts/backtest.py: para cada solicitud del periodo julio–septiembre, usa MotorA con as_of igual a la fecha de la solicitud
y compara contra: lo que eligió el analista, siempre el más barato, aleatorio y el oráculo (usando verdad_oculta.csv para el
costo esperado REAL). Reporta arrepentimiento medio en pesos, % de veces que elige el óptimo, tasa de acuerdo con el analista,
puntualidad esperada real, y el resultado por nivel de servicio. Barre la vida media (15, 30, 45, 60, 90) y λ (0, 0.5, 1, 2) y
muestra qué configuración da menor arrepentimiento y mejor detección de Andina. Recuerda el sesgo de selección: la comparación
con el analista usa la verdad oculta, no los resultados observados.
```
**Listo cuando:** hay una tabla de arrepentimiento por configuración y una configuración elegida con su justificación.

## Paso 12 · Tableros

```
Crea app/tableros.py (pestañas de Streamlit con Plotly): Precios (mapa de calor proveedor × corredor del índice de precio y dispersión
precio vs puntualidad), Tiempos de tránsito (cajas por proveedor y corredor con P50/P90), Capacidad (barras por proveedor y semana),
Disponibilidad de vehículos (matriz proveedor × vehículo y alertas de vehículos con un solo proveedor), Tendencias (puntualidad
semanal con banda de confianza y alerta de deterioro), Ranking y fichas (dureza por corredor y fortalezas/debilidades), Gestión
(cuota por proveedor, HHI, tasa de aceptación, motivos de rechazo, costo esperado frente al real). Usa la paleta única y accesible,
títulos que digan la conclusión y filtros por corredor y fecha.
```
**Listo cuando:** cada uno de los cinco tableros del enunciado responde su pregunta en una mirada.

## Paso 13 · Banco de comparación: nuestro motor, Jev y un LLM

```
Crea bench/comparar.py con una interfaz común: cada motor recibe SolicitudIn y devuelve RecomendacionOut.
Implementa MotorA (nuestro), MotorB_Jev y MotorC_LLM (este último solo redacta la explicación y critica el Top-3 a partir del
desglose; no decide el ranking). Para MotorB_Jev: arma el estado en texto con los proveedores factibles ya resumidos
(precio, P(a tiempo), P90, número de servicios, alertas), define una pregunta de tipo Choice y llama a la API de TypeSafe según
su documentación oficial; deja la clave en una variable de entorno y fija la versión del modelo. Toma 500 solicitudes de la
fase de prueba y del último trimestre, ejecuta los tres motores y mide: arrepentimiento (con verdad_oculta.csv), % de acuerdo
entre motores, % enviado a revisión, latencia (p50 y p95) y costo en tokens. Prueba además robustez: cambiar el orden de los
proveedores y sus nombres, añadir proveedores irrelevantes y repetir la misma solicitud 20 veces para ver si el resultado
cambia. Genera una tabla en markdown y una gráfica. No inventes resultados: si falta la clave de API, ejecuta solo A y deja
los demás en «no medido».
```
**Listo cuando:** la tabla del PDF (sección 13.6) tiene números en las filas de B y C, o dice honestamente «no medido».

## Paso 14 · Congelar, demo y respaldo

```
Congela las funciones. Escribe docs/guion_demo.md con 6 escenas de 1 a 2 minutos, usando solicitudes reales de la fase de
prueba: (1) envío típico Estándar con aprobación en un clic; (2) la misma solicitud en Flexible y en Urgente, mostrando
cómo cambia el ganador; (3) el mejor proveedor sin capacidad; (4) proveedor nuevo con sugerencia de prueba; (5) carga
peligrosa y filtro duro; (6) repetición del tiempo donde Andina Cargo se degrada y el sistema lo detecta, y la comparación con Jev.
Para cada escena indica el comando o clic exacto, qué se debe ver y qué decir. Agrega scripts/preparar_demo.sh que reinicie la
base, cargue los datos y arranque API y UI. Graba un video de 5 minutos de respaldo.
```
**Listo cuando:** alguien distinto al autor ejecuta `preparar_demo.sh` y recorre el guion sin errores.

---

## Cómo se reparte el trabajo

| Perfil | Pasos |
|---|---|
| Sistemas | 3, 4, 5, 6, 10, 11, 13 |
| Control | 9 y 11 (estabilidad, vida media, λ, límites al cambio de pesos), revisar la narrativa del lazo |
| Mecatrónica | 7, 8 |
| Mecánica | 12, y ayudar a limpiar y a probar casos |
| Negocios | Costos de retraso por nivel (con COSCO), guion de demo (14), presentación, valor de negocio |

## Puntos que no se pueden olvidar

1. COSCO no dará datos: todo es sintético. En la presentación se declara qué es real (distancias de Buenaventura) y qué es supuesto (precios, desempeño).
2. Nunca usar `verdad_oculta.csv` en entrenamiento ni en el motor. Solo evalúa.
3. Toda función de estadística o modelo recibe `as_of` y no ve el futuro.
4. Si Jev o el LLM no están medidos, no se afirma nada sobre ellos en la presentación.
