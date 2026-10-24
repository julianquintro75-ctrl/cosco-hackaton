# Paso 9 · Repetición del tiempo (2026-06-01 → 2026-10-15)

Comando: `python scripts/replay.py` (vida media 30 días, λ = 0.5, elegidas en el paso 11). Resultado en `data/replay.csv` (una fila por día y proveedor). La verdad oculta solo se usa para evaluar.

```
== Andina Cargo: deterioro real desde 2026-08-01 (verdad oculta) ==
  % Top-3 en Estandar (ventana 7 d): julio 78% -> 15-30 sep 39%
  Cae del Top-3 en Estandar (queda < 50 % para siempre): 2026-08-14  -> retraso de detección 13 días
  Alerta de tendencia (binomial 30 d) desde: 2026-08-15  -> 14 días
  P(tarde) estimada del proveedor supera 15 %: 2026-08-30  -> 29 días
```

## Andina Cargo, una fila por semana

| fecha      |   p_tarde_est |   p_tarde_real |   posicion_media |   pct_top3 |   tendencia |   cuota_30d |
|:-----------|--------------:|---------------:|-----------------:|-----------:|------------:|------------:|
| 2026-06-01 |        0.0886 |       0.06     |            3.833 |     0.25   |      0      |      0.0923 |
| 2026-06-08 |        0.0915 |       0.06     |            4.667 |     0      |      0      |      0.0868 |
| 2026-06-15 |        0.0878 |       0.06     |            3.083 |     0.6667 |      0      |      0.0996 |
| 2026-06-22 |        0.077  |       0.06     |            3.846 |     0.3077 |      0      |      0.1099 |
| 2026-06-29 |        0.0718 |       0.06     |            3.455 |     0.4545 |      0      |      0.1085 |
| 2026-07-06 |        0.0642 |       0.06     |            2.75  |     1      |      0      |      0.1142 |
| 2026-07-13 |        0.0619 |       0.06     |            3.158 |     0.6316 |      0      |      0.1004 |
| 2026-07-20 |        0.0714 |       0.06     |            3.231 |     0.6154 |      0      |      0.0874 |
| 2026-07-27 |        0.0756 |       0.06     |            3.286 |     0.8571 |      0      |      0.084  |
| 2026-08-03 |        0.0829 |       0.1335   |            2.818 |     0.9091 |      0      |      0.0688 |
| 2026-08-10 |        0.0833 |       0.243683 |            4.25  |     0.125  |      0      |      0.0766 |
| 2026-08-17 |        0.1167 |       0.321    |            3.857 |     0.2857 |      0.1079 |      0.0965 |
| 2026-08-24 |        0.127  |       0.35     |            5.308 |     0.0769 |      0.1197 |      0.0838 |
| 2026-08-31 |        0.1573 |       0.35     |            4.667 |     0.2    |      0.2015 |      0.0895 |
| 2026-09-07 |        0.1656 |       0.35     |            3.867 |     0.5333 |      0.2608 |      0.0797 |
| 2026-09-14 |        0.1849 |       0.35     |            4.857 |     0.2857 |      0.2714 |      0.0668 |
| 2026-09-21 |        0.197  |       0.35     |            4.733 |     0.2    |      0.2783 |      0.0643 |
| 2026-09-28 |        0.1691 |       0.381818 |            5.2   |     0.0667 |      0.1722 |      0.064  |
| 2026-10-05 |        0.182  |       0.38125  |            5.167 |     0.1667 |      0.1409 |      0.0716 |
| 2026-10-12 |        0.2087 |       0.363636 |            5.333 |     0.25   |      0.2133 |      0.0697 |

Lectura: la alerta de tendencia avisa unas dos semanas después del inicio del deterioro; el ranking reacciona más lento porque la estimación bayesiana amortigua (así no sobrerreacciona a eventos puntuales como el paro de Altiplano).
