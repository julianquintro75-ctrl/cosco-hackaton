# Paso 11 · Backtest y validación

Periodo 2026-07-01 → 2026-09-30: 1586 solicitudes (1512 con al menos un proveedor factible). Datos **sintéticos**. El motor usa as_of = fecha de la solicitud (no ve el futuro). El costo real se calcula con la verdad oculta del simulador; por eso la comparación con el analista no sufre el sesgo de selección de los resultados observados.

Costo real = precio + P(tarde) real × costo de retraso del nivel + P(incidente) real × $8.000.000 (sin penalizaciones de decisión).

## Barrido de configuración (motor A)

| Vida media (d) | λ | Arrepentimiento medio | % óptimo | Puntualidad real | Acuerdo con analista | Andina: días hasta P(tarde)>15 % | Andina: días hasta dejar el Top-1 Estándar | Pico Altiplano (paro) |
|---|---|---|---|---|---|---|---|---|
| 15 | 0 | $109.562 | 59.9 % | 78.5% | 27.7 % | 16.0 | 51 | 21% |
| 15 | 0.5 | $113.398 | 59.5 % | 78.5% | 28.0 % | 16.0 | 51 | 21% |
| 15 | 1 | $113.797 | 59.3 % | 78.7% | 29.5 % | 16.0 | 51 | 21% |
| 15 | 2 | $114.008 | 59.5 % | 79.5% | 31.4 % | 16.0 | 51 | 21% |
| 30 | 0 | $103.955 | 62.6 % | 78.9% | 26.7 % | 30.0 | 52 | 19% |
| 30 | 0.5 | $105.875 **←** | 61.9 % | 79.1% | 28.2 % | 30.0 | 52 | 19% |
| 30 | 1 | $109.199 | 61.2 % | 79.3% | 30.2 % | 30.0 | 52 | 19% |
| 30 | 2 | $114.924 | 58.9 % | 80.4% | 33.3 % | 30.0 | 52 | 19% |
| 45 | 0 | $106.079 | 65.3 % | 79.3% | 26.7 % | 45.0 | 52 | 18% |
| 45 | 0.5 | $112.009 | 63.0 % | 79.2% | 28.9 % | 45.0 | 52 | 18% |
| 45 | 1 | $110.463 | 61.9 % | 79.9% | 31.3 % | 45.0 | 52 | 18% |
| 45 | 2 | $120.860 | 57.7 % | 80.8% | 33.8 % | 45.0 | 52 | 18% |
| 60 | 0 | $116.296 | 64.9 % | 79.2% | 27.1 % | 68.0 | 52 | 17% |
| 60 | 0.5 | $121.432 | 62.3 % | 79.1% | 29.1 % | 68.0 | 52 | 17% |
| 60 | 1 | $120.635 | 61.3 % | 79.9% | 31.5 % | 68.0 | 52 | 17% |
| 60 | 2 | $130.787 | 56.5 % | 81.0% | 33.3 % | 68.0 | 52 | 17% |
| 90 | 0 | $127.309 | 63.9 % | 79.0% | 27.1 % | no | no | 17% |
| 90 | 0.5 | $132.808 | 62.1 % | 79.2% | 28.5 % | no | no | 17% |
| 90 | 1 | $145.291 | 59.5 % | 79.8% | 30.1 % | no | no | 17% |
| 90 | 2 | $146.879 | 56.3 % | 80.8% | 32.2 % | no | no | 17% |

## Configuración elegida: vida media 30 días, λ = 0.5

| Política | Arrepentimiento medio | % elige el óptimo | Puntualidad real esperada |
|---|---|---|---|
| Motor A (nuestro) | $105.875 | 61.9 % | 79.1% |
| Analista (decisión histórica) | $287.695 | 28.1 % | 83.7% |
| Siempre el más barato | $201.263 | 50.8 % | 75.9% |
| Aleatorio | $410.220 | 24.1 % | 84.7% |
| Oráculo (verdad oculta) | $0 | 100.0 % | 84.1% |

### Por nivel de servicio (arrepentimiento medio en COP)

| Nivel | n | Motor A | Analista | Más barato | Aleatorio | Acuerdo motor–analista |
|---|---|---|---|---|---|---|
| Estandar | 771 | $109.238 | $233.544 | $154.883 | $368.770 | 30% |
| Flexible | 461 | $2.935 | $260.574 | $2.835 | $405.632 | 26% |
| Urgente | 280 | $266.100 | $484.538 | $655.668 | $531.911 | 27% |

## Justificación

- Se elige la configuración con **menor arrepentimiento medio**; el desempate es la detección más temprana de Andina.
- Diferencia de arrepentimiento λ=0.5 − λ=0 (vida media 30): $1.920 por servicio, IC 95 % [$-3.108, $6.534]. **No es significativa → se elige λ = 0.5** para conservar la protección frente a proveedores con poca evidencia.
- Frente a la decisión histórica del analista, el motor ahorraría en promedio **$181.819 de costo real esperado por servicio** ($274.910.447 en el trimestre simulado). Cifra sobre datos sintéticos: indica la dirección, no el valor real para COSCO.
- Vidas medias cortas detectan antes a Andina pero se mueven más con eventos puntuales (pico de Altiplano en el paro de marzo); las largas son estables pero tardan semanas en reaccionar. La alerta de tendencia (binomial a 30 días) avisa independientemente de la vida media.
- λ alto protege frente a proveedores con poca evidencia pero sacrifica ahorro cuando la evidencia es suficiente.
- La configuración elegida se copia a `engine/config_motor.json` (vida_media_dias = 30, lambda_incertidumbre = 0.5).
- Limitación: los datos simulados siguen una estructura parecida a la que supone el modelo, así que la ventaja frente a las referencias probablemente está exagerada respecto a datos reales.