# Tensiones y casos difíciles (medidos)

Generado por `python -m scripts.casos_dificiles` sobre 600 solicitudes al azar de jul–sep 2026 (semilla 7) con el motor A real.
**Los datos son sintéticos**: las cifras muestran cómo se comporta el método, no el valor real para COSCO.

## 1. Costo frente a puntualidad

Elegir el menor **costo total esperado** (precio + retraso esperado en pesos + incidente) abarata, pero no maximiza la puntualidad.
Backtest de 1.586 solicitudes contra la verdad oculta del simulador:

| Política | Arrepentimiento medio | % óptimo | Puntualidad real |
|---|---|---|---|
| Motor A (nuestro) | $105.875 | 61.9 % | 79.1% |
| Analista (decisión histórica) | $287.695 | 28.1 % | 83.7% |
| Siempre el más barato | $201.263 | 50.8 % | 75.9% |
| Aleatorio | $410.220 | 24.1 % | 84.7% |

Lectura honesta: el motor A es el que menos pierde en pesos, pero **no es el más puntual**. Es una elección de diseño: con retraso de
$300 mil (Flexible) la puntualidad no vale lo que cuesta. Si COSCO prefiere puntualidad por encima del costo, se sube el costo del
retraso por nivel en `engine/config_motor.json` y el ranking cambia sin tocar el código (ver la escena 2 del guion de la demo).

## 2. Autonomía frente a revisión humana

Con la tarifa de cliente calibrada, de 600 solicitudes: 570 tuvieron al menos un proveedor factible, **32.1 %** pidieron
revisión, **25.3 %** se escalaron a gerencia y en **11.1 %** el margen esperado del Top-1 fue negativo.
La persona decide siempre; el sistema solo gradúa cuánta atención merece cada caso.

| Nivel | Solicitudes con opción | Piden revisión | Escalan a gerencia |
|---|---|---|---|
| Estandar | 303 | 23.4 % | 23.4 % |
| Flexible | 158 | 1.9 % | 1.9 % |
| Urgente | 109 | 100.0 % | 64.2 % |

| Motivo | Veces | Sobre la muestra | Ejemplo |
|---|---|---|---|
| `empate_tecnico` | 155 | 25.8 % | `R004996` |
| `sin_candidato_en_plazo` | 126 | 21.0 % | `R005109` |
| `urgente` | 109 | 18.2 % | `R005470` |
| `margen_negativo` | 63 | 10.5 % | `R005109` |
| `sin_opcion` | 30 | 5.0 % | `—` |
| `confianza_baja` | 5 | 0.8 % | `R005698` |

Qué queda abierto: la mayor parte del escalamiento viene de `sin_candidato_en_plazo` (ningún proveedor tiene P90 de tránsito dentro del
plazo). Es una regla de diseño prudente, pero con los plazos sintéticos escala más de lo que un equipo real toleraría. Alternativa
documentada: escalar solo cuando ni siquiera el tránsito mediano (P50) cabe en el plazo y degradar el resto a revisión.
Los empates técnicos son solo un aviso: no cuentan como revisión.

## 3. Casos difíciles y cómo responde el sistema

| Caso | Qué hace el sistema | Dónde verlo |
|---|---|---|
| Mejor proveedor sin capacidad | Lo descarta con motivo y dice cuánto cuesta no tenerlo | Guion escena 3 (`R005923`) |
| Tarifa que no cubre el costo | Escala a gerencia con el margen esperado | `R005907` |
| Proveedor nuevo con poco historial | Lo penaliza por incertidumbre y propone una prueba aparte solo en Flexible: 11 sugerencias en la muestra | Escena 4 (`R005913`) |
| Carga peligrosa | Filtro duro IMO que nunca se relaja; el certificado queda solo y la dependencia se ve (en la muestra, 61 solicitudes tuvieron un único candidato) | Escena 5 (`R005949`) |
| Proveedor que se degrada (Andina) | Pierde el Top-3 en unos 12 días; alerta binomial a 14 días | `python scripts/replay.py` |
| Proveedor que mejora (TransPacífico) | El decaimiento temporal de 30 días da más peso a lo reciente | Escena 1 |
| Paro de Altiplano | Pico de retraso visible en el backtest; si la capacidad reportada es 0, la regla dura lo descarta | `reportes/paso11_backtest.md` |
| Plazo imposible | `sin_candidato_en_plazo`: escala a gerencia, decide una persona | tabla de motivos |
| Dos proveedores casi iguales | Aviso de empate técnico, sin bloquear | tabla de motivos |

### Por qué se descartan proveedores (suma de la muestra)

| Motivo | Descartes |
|---|---|
| `sin_cobertura` | 1927 |
| `sin_vehiculo` | 810 |
| `sin_capacidad` | 418 |
| `inactivo` | 321 |
| `sin_certificacion` | 215 |

## 4. Concentración

Cuota de Top-1 por proveedor en la muestra (si uno concentra demasiado, hay riesgo operativo y poder de negociación en su contra):

| Proveedor | Veces Top-1 | Cuota |
|---|---|---|
| Economica del Sur | 355 | 62.3 % |
| Mulas del Valle | 54 | 9.5 % |
| TransPacifico | 34 | 6.0 % |
| Caribe Express | 24 | 4.2 % |
| Altiplano Trans | 24 | 4.2 % |
| FrioCol | 23 | 4.0 % |
| Andina Cargo | 22 | 3.9 % |
| Seguridad Total | 19 | 3.3 % |
| Veteranos del Camino | 7 | 1.2 % |
| Nuevo Rumbo | 4 | 0.7 % |
| Premium Logistics | 3 | 0.5 % |
| Rapido SAS | 1 | 0.2 % |

El proveedor más frecuente es **Economica del Sur** con 62.3 %. El motor ya incluye un componente de concentración (penaliza al proveedor
que supera el umbral de participación de su ventana reciente, y los tableros de gerencia muestran la cuota y el índice Herfindahl). Pero esta
muestra se recomienda solicitud por solicitud, **sin que las recomendaciones anteriores alimenten la participación**: si la persona aceptara
siempre el Top-1, la concentración real sería mayor que la que el penalizador alcanza a ver. Es un riesgo conocido; mitigarlo exige que las
decisiones aceptadas actualicen la participación en tiempo real (el repositorio ya guarda las decisiones) o un tope duro acordado con operaciones.
