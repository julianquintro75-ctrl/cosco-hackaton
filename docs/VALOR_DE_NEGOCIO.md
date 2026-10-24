# Valor de negocio, escalabilidad y plan de implementación

> Formato breve. Todas las cifras salen de **datos sintéticos** (COSCO no entregó datos): indican la dirección y el orden de magnitud, no un ahorro garantizado. Cada cifra se puede reproducir (ver «Evidencia»).

## 1. Qué problema resuelve y para quién

El equipo de operaciones compara a mano más de diez proveedores por cada solicitud. El resultado depende de quién decide y es difícil de explicar. El sistema entrega, para cada solicitud, un Top-3 con su costo total esperado desglosado (precio, retraso esperado, incidentes, incertidumbre, concentración), los proveedores descartados con motivo y una señal de cuánta atención merece el caso. **La persona sigue decidiendo.**

## 2. Valor para COSCO SHIPPING

| Palanca | Cómo se produce | Evidencia (sintética) |
|---|---|---|
| **Tiempo** | La comparación pasa de minutos a un clic en los casos claros; el sistema responde en ~18 ms por solicitud | Mediana medida sobre 382 solicitudes |
| **Costo** | Elige por costo total esperado, no por precio | Backtest de 1.586 solicitudes: ahorro medio de ≈ $182 mil de costo real esperado por servicio frente a la decisión histórica; arrepentimiento medio $106 mil frente a $288 mil del analista |
| **Consistencia** | Misma solicitud, misma recomendación y mismo desglose; robusta a orden y nombres de proveedores | Banco de comparación: 100 % igual en las pruebas de robustez |
| **Confiabilidad** | Detecta proveedores que se degradan y los saca del Top-3 | Caso Andina: sale del Top-3 en ~12 días; alerta estadística a los 14 |
| **Atención humana bien dirigida** | Revisión solo donde hace falta | ≈ 30 % de las solicitudes piden revisión y ≈ 25 % escalan; el resto se aprueba en un clic |
| **Negociación** | Cuota por proveedor, dependencias (p. ej. un único proveedor IMO) y fichas de fortalezas y riesgos | Tableros de gerencia |

**Lo que no prometemos:** en puntualidad real el motor (79,1 %) no supera al analista (83,7 %); gana en costo. Es una decisión de diseño explícita y ajustable (ver `docs/CASOS_DIFICILES.md`).

## 3. Escalabilidad

- **Cómputo:** ~18 ms por solicitud en un solo proceso; el volumen de operaciones de un país no es un problema.
- **Datos:** la persistencia está detrás de la interfaz `Repositorio`; SQLite hoy, PostgreSQL u otro motor al escribir un adaptador sin tocar motor, API ni interfaz.
- **Despliegue:** API, interfaz y reentrenador son servicios separados en `docker-compose` (el build de la imagen aún no se probó contra un daemon real).
- **Cobertura:** nuevos corredores, proveedores o tipos de vehículo son filas en tablas, no cambios de código. Otro país: nuevos maestros y parámetros.
- **Modelos:** los motores se intercambian por el contrato `MotorDecision`; el reentrenamiento nocturno solo publica un candidato si supera al método estadístico, y queda **pendiente de aprobación humana**.

## 4. Plan de implementación (con datos reales)

| Fase | Duración orientativa | Qué se hace | Criterio de salida |
|---|---|---|---|
| 0 · Datos | 2 semanas | Llenar `docs/referencia/plantilla_datos.xlsx` con tarifas, flota, capacidad e historial y cargarla con `python -m scripts.importar_datos` (valida llaves y rechaza datos rotos). Revisar calidad con el reporte de datos | Base real cargada sin errores críticos |
| 1 · Calibración | 2 semanas | Fijar con operaciones el costo de un retraso por nivel, la tarifa/margen y el umbral de escalamiento; re-correr el backtest con datos reales | Parámetros firmados por operaciones; backtest sobre historia real |
| 2 · Sombra | 4 semanas | El sistema recomienda en paralelo; las personas deciden como siempre. Se mide acuerdo, y quién tenía razón en los desacuerdos | Acuerdo y costo real medidos; casos de desacuerdo revisados |
| 3 · Piloto | 6 semanas | Un puerto o un grupo de corredores; la recomendación se muestra al decidir; las decisiones y sus motivos se guardan | Tiempo de decisión y costo frente a la línea base |
| 4 · Ampliación | continuo | Más corredores, conexión con el sistema de órdenes, reentrenamiento nocturno activo con aprobación, segunda base de datos si se requiere | Adopción y revisión periódica de gerencia |

**Roles:** operaciones (dueño de reglas y parámetros), TI (datos, despliegue, accesos), gerencia (tableros y excepciones).

## 5. Riesgos y mitigación

| Riesgo | Mitigación |
|---|---|
| Los resultados vienen de datos sintéticos y el simulador comparte supuestos con el motor (circularidad) | Fases 0–2: recalibrar y medir en sombra con datos reales antes de usar la recomendación |
| Jev (motor B) y el LLM (motor C) están implementados pero **no medidos** (no hubo claves en las pruebas) | Medir con `bench/comparar.py` cuando haya claves; mientras tanto, el motor A es el único que decide |
| El modelo de ML no supera al método estadístico en una de las dos métricas | Solo se publica si gana en validación móvil y exige aprobación humana |
| Concentración: aceptar siempre el Top-1 puede cargar a un proveedor (en la muestra, 62 % de los Top-1 son de uno) | Actualizar la participación con las decisiones aceptadas o fijar un tope con operaciones |
| Escalamiento alto (~25 %) por la regla de plazo P90 | Ajustar la regla en la fase de calibración (alternativa documentada) |
| Datos incompletos o sucios | Validador de datos y importador que rechaza llaves rotas; el sistema muestra la incertidumbre en lugar de ocultarla |

## 6. Evidencia reproducible

`python scripts/backtest.py` (costo y puntualidad), `python scripts/replay.py` (detección de Andina), `python -m scripts.casos_dificiles` (revisión, escalamiento, concentración), `python bench/comparar.py` (motores y robustez), `pytest` (45 pruebas).
