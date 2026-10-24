# Revisión del proyecto frente al enunciado

Estado a 2026-10-23. Datos sintéticos; Jev y LLM no medidos.

## Qué está completo
- Filtros duros con motivo de descarte, Top-3 explicado, decisión humana registrada y cierre del servicio.
- Estadística bayesiana con decaimiento (vida media 30 d, λ=0.5, elegidos por backtest), Índice de Dureza, alerta de tendencia, control de concentración, reglas de escalamiento.
- Datos sintéticos con historias y 35 reglas de calidad (33 cumplen, 0 críticas), simulador en vivo, replay y backtest con oráculo.
- Interfaz de 4 pantallas y 7 tableros; 45 pruebas pasan; determinismo verificado.

## Qué falta o es débil
1. **Calibración del negocio**: aplicada; queda el escalamiento (ver sección siguiente).
2. **Puntualidad**: el motor A es más barato pero menos puntual (79,1 %) que el analista simulado (83,7 %) y que el azar (84,7 %). Hay que defender el trade-off costo/puntualidad o subir el costo del retraso.
3. **ML**: con la ventana fija del reto M1/M2 no superaban al bayesiano (AUC ≈ 0,60). Con ventana móvil (corrida del 2026-10-20) **M1 sigue sin mejorar** (Brier 0,1391 vs 0,1356 bayes) y **M2 sí** (pinball P90 1,52 vs 1,70; P50 −3,3 %). Es una sola ventana de 465 servicios: el reentrenador lo publica como candidato pendiente de aprobación, no lo activa, y conviene repetir varias noches antes de adoptarlo. Falta además la actualización mensual de pesos con aprobación (Bradley-Terry).
4. **Jev y LLM**: no medidos (sin claves ni acceso).
5. **Circularidad sintética**: los resultados dependen del generador; no prueban desempeño en el mundo real.
6. **Detección tardía**: Andina cae el 2026-08-01; sale del Top-3 a los 12 días y la alerta binomial llega a los 14.
7. **Docker**: la construcción de la imagen y `docker compose up` no se ejecutaron en el entorno de revisión (solo `docker compose config`, y todo el flujo UI→API→base se probó con uvicorn y Streamlit sin contenedores).
8. **Otros backends de datos**: el puerto existe y está probado con SQLite; no hay una segunda implementación real.

## Calibración aplicada (resultados medidos)
Antes: revisión 46 %, escalamiento 35 %, margen negativo del Top-1 31 % (Estándar 52 %, Urgente 100 % de revisión).
Cambios: prima de tarifa al cliente por nivel en el generador (`PRIMA_NIVEL`: Flexible 0,97, Estándar 1,22, Urgente 1,60) y el empate técnico pasa a **aviso** (no cuenta como revisión). La holgura de plazos no se tocó (cambiarla rompía la historia de Andina y el validador).
Después (~600 solicitudes de jul–sep): **revisión ≈ 30 %, escalamiento ≈ 25 %, margen negativo ≈ 10 %**. Se cumplió la meta de revisión y de margen; **el escalamiento no llegó a ≤ 10 %**: viene sobre todo de la regla `sin_candidato_en_plazo` (ningún proveedor con tránsito P90 dentro del plazo). Alternativa documentada si COSCO lo pide: escalar solo cuando ni el tránsito mediano cabe en el plazo y degradar el resto a revisión. Detalle en `docs/CASOS_DIFICILES.md`.
La calibración cambió el guion de la demo (escenas 2, 3 y 5): ahora R005907 es el caso de gerencia.

## Corregido en esta revisión
- «$» de la explicación se mostraba como fórmula en Streamlit (`_md` en `app/ui.py`).
- La tabla del Top-3 se cortaba a la derecha: ahora es una tabla HTML que se ajusta al ancho.
- La UI ya no lee SQLite: recomendar, decidir, pendientes, tableros y plantillas pasan por la API; SQL aislado en `engine/repo_sqlite.py` tras el puerto `Repositorio`.
- Reentrenamiento nocturno implementado (`scripts/reentrenar.py`, servicio `reentrenador`).
- `COSCO_Solucion_Proyecto.pdf` con vida media 30 d y `COSCO_BPMN_AS-IS_TO-BE.drawio` con la segunda opinión de Jev (paso 5a) y el ciclo nocturno actualizado.

## Siguiente paso
1. Decidir con operaciones si se relaja la regla de plazo P90 (escalamiento ≈ 25 %).
2. Segunda implementación de `Repositorio` (p. ej. PostgreSQL) pasando `tests/test_repositorio.py`.
3. Medir Jev y el LLM cuando haya acceso.
