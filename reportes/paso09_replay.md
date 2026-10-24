# Paso 9 · Repetición del tiempo (2026-06-01 → 2026-10-15)

Comando: `python scripts/replay.py` (vida media 45 días). Resultado en `data/replay.csv` (una fila por día y proveedor). La verdad oculta solo se usa para evaluar.

```
== Andina Cargo: deterioro real desde 2026-08-01 (verdad oculta) ==
  % Top-3 en Estandar (ventana 7 d): julio 80% -> 15-30 sep 42%
  Cae del Top-3 en Estandar (queda < 50 % para siempre): 2026-09-25  -> retraso de detección 55 días
  Alerta de tendencia (binomial 30 d) desde: 2026-08-15  -> 14 días
  P(tarde) estimada del proveedor supera 15 %: 2026-09-14  -> 44 días
```

## Andina Cargo, una fila por semana

| fecha      |   p_tarde_est |   p_tarde_real |   posicion_media |   pct_top3 |   tendencia |   cuota_30d |
|:-----------|--------------:|---------------:|-----------------:|-----------:|------------:|------------:|
| 2026-06-01 |        0.0811 |       0.06     |            3.167 |     0.6667 |      0      |      0.0923 |
| 2026-06-08 |        0.0834 |       0.06     |            4.667 |     0      |      0      |      0.0868 |
| 2026-06-15 |        0.0813 |       0.06     |            2.917 |     0.75   |      0      |      0.0996 |
| 2026-06-22 |        0.0733 |       0.06     |            3.846 |     0.3077 |      0      |      0.1099 |
| 2026-06-29 |        0.0691 |       0.06     |            3.364 |     0.4545 |      0      |      0.1085 |
| 2026-07-06 |        0.0629 |       0.06     |            1.5   |     1      |      0      |      0.1142 |
| 2026-07-13 |        0.0606 |       0.06     |            2.947 |     0.6316 |      0      |      0.1004 |
| 2026-07-20 |        0.0668 |       0.06     |            3     |     0.6923 |      0      |      0.0874 |
| 2026-07-27 |        0.07   |       0.06     |            2.286 |     0.8571 |      0      |      0.084  |
| 2026-08-03 |        0.075  |       0.1335   |            2.545 |     0.9091 |      0      |      0.0688 |
| 2026-08-10 |        0.0757 |       0.243683 |            3.5   |     0.625  |      0      |      0.0766 |
| 2026-08-17 |        0.1008 |       0.321    |            3.429 |     0.5714 |      0.1079 |      0.0965 |
| 2026-08-24 |        0.1084 |       0.35     |            4.615 |     0.3077 |      0.1197 |      0.0838 |
| 2026-08-31 |        0.1322 |       0.35     |            4.333 |     0.2    |      0.2015 |      0.0895 |
| 2026-09-07 |        0.1404 |       0.35     |            3.6   |     0.6    |      0.2608 |      0.0797 |
| 2026-09-14 |        0.1566 |       0.35     |            4.571 |     0.3571 |      0.2714 |      0.0668 |
| 2026-09-21 |        0.1674 |       0.35     |            3.933 |     0.4    |      0.2783 |      0.0643 |
| 2026-09-28 |        0.151  |       0.381818 |            4.6   |     0.2667 |      0.1722 |      0.064  |
| 2026-10-05 |        0.1626 |       0.38125  |            4.667 |     0.3333 |      0.1409 |      0.0716 |
| 2026-10-12 |        0.1844 |       0.363636 |            5.333 |     0.25   |      0.2133 |      0.0697 |

Lectura: el sistema avisa (alerta de tendencia) unas dos semanas después del inicio del deterioro; el ranking reacciona más lento porque la estimación bayesiana con vida media 45 días amortigua. La vida media y λ se eligen en el paso 11.
