# Paso 9 · Repetición del tiempo (2026-06-01 → 2026-10-15)

Comando: `python scripts/replay.py` (vida media 30 días, λ = 0.5, elegidas en el paso 11). Resultado en `data/replay.csv` (una fila por día y proveedor). La verdad oculta solo se usa para evaluar.

```
== Andina Cargo: deterioro real desde 2026-08-01 (verdad oculta) ==
  % Top-3 en Estandar (ventana 7 d): julio 78% -> 15-30 sep 38%
  Cae del Top-3 en Estandar (queda < 50 % para siempre): 2026-08-13  -> retraso de detección 12 días
  Alerta de tendencia (binomial 30 d) desde: 2026-08-15  -> 14 días
  P(tarde) estimada del proveedor supera 15 %: 2026-08-30  -> 29 días
```

## Andina Cargo, una fila por semana

| fecha      |   p_tarde_est |   p_tarde_real |   posicion_media |   pct_top3 |   tendencia |   cuota_30d |
|:-----------|--------------:|---------------:|-----------------:|-----------:|------------:|------------:|
| 2026-06-01 |        0.0886 |         0.06   |            3.833 |     0.25   |      0      |      0.0937 |
| 2026-06-08 |        0.0915 |         0.06   |            4.667 |     0      |      0      |      0.089  |
| 2026-06-15 |        0.0878 |         0.06   |            3.083 |     0.6667 |      0      |      0.0979 |
| 2026-06-22 |        0.077  |         0.06   |            3.846 |     0.3077 |      0      |      0.1119 |
| 2026-06-29 |        0.0718 |         0.06   |            3.455 |     0.4545 |      0      |      0.1081 |
| 2026-07-06 |        0.0642 |         0.06   |            2.75  |     1      |      0      |      0.1111 |
| 2026-07-13 |        0.0619 |         0.06   |            3.053 |     0.6316 |      0      |      0.0931 |
| 2026-07-20 |        0.0714 |         0.06   |            3.231 |     0.6154 |      0      |      0.0832 |
| 2026-07-27 |        0.0756 |         0.06   |            3.286 |     0.8571 |      0      |      0.0838 |
| 2026-08-03 |        0.0829 |         0.1335 |            2.909 |     0.8182 |      0      |      0.0716 |
| 2026-08-10 |        0.0833 |         0.2437 |            4.25  |     0.125  |      0      |      0.0792 |
| 2026-08-17 |        0.1167 |         0.321  |            3.857 |     0.2857 |      0.1079 |      0.0938 |
| 2026-08-24 |        0.127  |         0.35   |            5.308 |     0.0769 |      0.1197 |      0.0832 |
| 2026-08-31 |        0.1573 |         0.35   |            4.667 |     0.2    |      0.2015 |      0.0857 |
| 2026-09-07 |        0.1656 |         0.35   |            3.867 |     0.5333 |      0.2608 |      0.0754 |
| 2026-09-14 |        0.1849 |         0.35   |            4.857 |     0.2857 |      0.2714 |      0.065  |
| 2026-09-21 |        0.197  |         0.35   |            4.733 |     0.2    |      0.2783 |      0.0671 |
| 2026-09-28 |        0.1691 |         0.3818 |            5.2   |     0.0667 |      0.1722 |      0.0634 |
| 2026-10-05 |        0.182  |         0.3812 |            5.167 |     0.1667 |      0.1409 |      0.0706 |
| 2026-10-12 |        0.2087 |         0.3636 |            5.333 |     0.25   |      0.2133 |      0.0682 |

Lectura: la alerta de tendencia avisa unas dos semanas después del inicio del deterioro; el ranking reacciona más lento porque la estimación bayesiana amortigua (así no sobrerreacciona a eventos puntuales como el paro de Altiplano).
