# Contexto del proyecto (léelo antes de tocar nada)

Hackathon **Sabana Hack 2026 · reto COSCO SHIPPING**: sistema de apoyo a la decisión que, para cada solicitud de transporte terrestre en Colombia, recomienda un Top-3 de proveedores, explicado, y la persona de operaciones decide. Enunciado completo en `docs/enunciado_reto.txt`. Tenemos **20 horas** en total y el equipo es multidisciplinario (sistemas, control, mecatrónica, mecánica, negocios). Idioma de trabajo y de la interfaz: **español**.

## Decisiones ya tomadas (no cambiarlas sin avisar)
- Arquitectura híbrida: **filtros duros (reglas) → modelos que predicen lo incierto → costo total esperado en pesos → explicación → decide una persona**.
- Costo esperado = precio + P(tarde)×costo_retraso(nivel) + P(incidente)×costo_incidente + λ×ancho_IC90×costo_retraso + penalización de concentración. Margen = tarifa_cliente − costo esperado.
- Niveles de servicio: Flexible / Estandar / Urgente (costos de retraso ilustrativos 300.000 / 2.500.000 / 6.000.000 COP, configurables).
- **El ranking es DETERMINISTA** (misma entrada, misma salida). La exploración de proveedores con pocos datos es una *sugerencia aparte* (solo Flexible), nunca parte del ranking.
- Estadística bayesiana Beta(17,3) por proveedor × corredor × tipo de carga con **decaimiento temporal** (vida media a decidir en el backtest; probablemente entre 30 y 45 días).
- Aprendizaje en tres velocidades: bayesiano instantáneo, reentrenamiento nocturno de modelos (publica solo si mejora), pesos mensuales con aprobación humana.
- Los motores son intercambiables (contrato `MotorDecision` en `contratos/contracts.py`): A propio, B Jev (caja negra rápida, solo segunda opinión), C LLM (solo explica/critica). **No afirmar nada sobre B y C hasta medirlos.**

## Reglas de oro
1. Los **contratos** (`contratos/contracts.py`) y el **esquema** (`db/schema.sql`) son la fuente de verdad. Si hay que cambiarlos, dilo explícitamente y actualiza ambos.
2. **Nunca usar `data/verdad_oculta.csv` en el motor ni en el entrenamiento.** Solo sirve para evaluar (arrepentimiento, detección).
3. Todo cálculo recibe `as_of` y **no puede ver el futuro** (solo servicios con `entrega_real <= as_of`).
4. Los datos son **sintéticos** (COSCO no los entrega). Se declara siempre. Distancias de Buenaventura reales; precios y desempeño son supuestos en `seed/config.py`.
5. Ningún proveedor sin certificación/vehículo/tarifa/capacidad puede aparecer en el Top-3; cada descartado lleva su motivo.
6. Si un modelo de ML no mejora la línea base bayesiana, **dilo claramente** y deja la base.
7. Cada paso termina con pruebas que pasan (`pytest`) y un «Listo cuando» cumplido. No inventes resultados: si algo no se pudo medir, escribe «no medido».

## Estructura
- `db/schema.sql` esquema SQLite · `contratos/` contratos pydantic · `seed/` generador, validador, simulación en vivo
- `engine/` estadísticas y motor · `app/` API (FastAPI) e interfaz (Streamlit) · `scripts/` utilidades · `bench/` banco de comparación
- `docs/referencia/` PDF de la solución, BPMN (.drawio), guía de datos, plantilla Excel · `PASOS_Y_PROMPTS.md` guía de 15 pasos con prompts

## Comandos útiles
```
python scripts/verificar_entorno.py
python seed/generate.py --sucio          # crea data/cosco.db, cosco_sucio.db, verdad_oculta.csv
python seed/validar_datos.py             # 35 reglas de calidad (limpia: 0 críticas)
python seed/check_story.py               # historias de los proveedores y detección
python seed/reporte_datos.py             # reportes/reporte_datos.html
python seed/en_vivo.py --dias 14 --pausa 3 --evento P03:0.6:2026-10-25
```

## Estado
Pasos 0–14 hechos (ver `reportes/` y el historial de git, con mensajes en formato Conventional Commits). Configuración elegida en el backtest: vida media 30 días, λ = 0,5 (`engine/config_motor.json`). M1/M2 no mejoran la línea base bayesiana: el motor usa el bayesiano. Jev y el LLM están implementados en `bench/comparar.py` pero **no medidos** (falta clave de API).
Pendiente humano: grabar el video de respaldo de 5 minutos siguiendo `docs/guion_demo.md`; medir B y C cuando haya `TYPESAFE_API_KEY` / `ANTHROPIC_API_KEY`.

## Demo
```
bash scripts/preparar_demo.sh                                         # Mac/Linux
powershell -ExecutionPolicy Bypass -File scripts\preparar_demo.ps1     # Windows
python -m pytest -q                                                    # 30 pruebas
python bench/comparar.py                                               # banco A vs Jev vs LLM
```
