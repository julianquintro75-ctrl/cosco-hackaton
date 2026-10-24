# Paso 11 · Backtest y validación

Periodo 2026-07-01 → 2026-09-30: 1586 solicitudes (1512 con al menos un proveedor factible). Datos **sintéticos**. El motor usa as_of = fecha de la solicitud (no ve el futuro). El costo real se calcula con la verdad oculta del simulador; por eso la comparación con el analista no sufre el sesgo de selección de los resultados observados.

Costo real = precio + P(tarde) real × costo de retraso del nivel + P(incidente) real × $8.000.000 (sin penalizaciones de decisión).

## Barrido de configuración (motor A)

| Vida media (d) | λ | Arrepentimiento medio | % óptimo | Puntualidad real | Acuerdo con analista | Andina: días hasta P(tarde)>15 % | Andina: días hasta dejar el Top-1 Estándar | Pico Altiplano (paro) |
|---|---|---|---|---|---|---|---|---|
| 15 | 0 | $111.461 | 59.6 % | 78.5% | 27.3 % | 16.0 | 51 | 21% |
| 15 | 0.5 | $112.069 | 59.6 % | 78.6% | 28.1 % | 16.0 | 51 | 21% |
| 15 | 1 | $114.813 | 59.3 % | 78.7% | 29.5 % | 16.0 | 51 | 21% |
| 15 | 2 | $113.558 | 59.5 % | 79.5% | 31.4 % | 16.0 | 51 | 21% |
| 30 | 0 | $104.390 | 62.6 % | 78.9% | 26.6 % | 30.0 | 52 | 19% |
| 30 | 0.5 | $105.983 **←** | 61.8 % | 79.1% | 28.6 % | 30.0 | 52 | 19% |
| 30 | 1 | $109.962 | 61.1 % | 79.3% | 30.5 % | 30.0 | 52 | 19% |
| 30 | 2 | $115.233 | 58.8 % | 80.4% | 33.5 % | 30.0 | 52 | 19% |
| 45 | 0 | $107.222 | 65.4 % | 79.3% | 26.5 % | 45.0 | 52 | 18% |
| 45 | 0.5 | $111.290 | 62.9 % | 79.2% | 28.9 % | 45.0 | 52 | 18% |
| 45 | 1 | $110.823 | 61.8 % | 79.9% | 31.3 % | 45.0 | 52 | 18% |
| 45 | 2 | $120.104 | 57.7 % | 80.9% | 33.8 % | 45.0 | 52 | 18% |
| 60 | 0 | $116.573 | 64.9 % | 79.2% | 26.9 % | 68.0 | 52 | 17% |
| 60 | 0.5 | $122.562 | 62.3 % | 79.1% | 28.9 % | 68.0 | 52 | 17% |
| 60 | 1 | $121.012 | 61.2 % | 79.9% | 31.7 % | 68.0 | 52 | 17% |
| 60 | 2 | $129.870 | 56.4 % | 81.0% | 33.1 % | 68.0 | 52 | 17% |
| 90 | 0 | $127.440 | 63.9 % | 79.0% | 27.0 % | no | no | 17% |
| 90 | 0.5 | $132.561 | 61.8 % | 79.2% | 28.6 % | no | no | 17% |
| 90 | 1 | $145.845 | 59.5 % | 79.7% | 30.0 % | no | no | 17% |
| 90 | 2 | $145.979 | 56.3 % | 80.7% | 31.7 % | no | no | 17% |

## Configuración elegida: vida media 30 días, λ = 0.5

| Política | Arrepentimiento medio | % elige el óptimo | Puntualidad real esperada |
|---|---|---|---|
| Motor A (nuestro) | $105.983 | 61.8 % | 79.1% |
| Analista (decisión histórica) | $287.695 | 28.1 % | 83.7% |
| Siempre el más barato | $201.263 | 50.8 % | 75.9% |
| Aleatorio | $409.000 | 23.9 % | 84.8% |
| Oráculo (verdad oculta) | $0 | 100.0 % | 84.1% |

### Por nivel de servicio (arrepentimiento medio en COP)

| Nivel | n | Motor A | Analista | Más barato | Aleatorio | Acuerdo motor–analista |
|---|---|---|---|---|---|---|
| Estandar | 771 | $109.314 | $233.544 | $154.883 | $367.598 | 30% |
| Flexible | 461 | $2.935 | $260.574 | $2.835 | $404.861 | 26% |
| Urgente | 280 | $266.475 | $484.538 | $655.668 | $529.814 | 29% |

## Justificación

- Se elige la configuración con **menor arrepentimiento medio**; el desempate es la detección más temprana de Andina.
- Diferencia de arrepentimiento λ=0.5 − λ=0 (vida media 30): $1.593 por servicio, IC 95 % [$-3.066, $6.178]. **No es significativa → se elige λ = 0.5** para conservar la protección frente a proveedores con poca evidencia.
- Frente a la decisión histórica del analista, el motor ahorraría en promedio **$181.711 de costo real esperado por servicio** ($274.747.447 en el trimestre simulado). Cifra sobre datos sintéticos: indica la dirección, no el valor real para COSCO.
- Vidas medias cortas detectan antes a Andina pero se mueven más con eventos puntuales (pico de Altiplano en el paro de marzo); las largas son estables pero tardan semanas en reaccionar. La alerta de tendencia (binomial a 30 días) avisa independientemente de la vida media.
- λ alto protege frente a proveedores con poca evidencia pero sacrifica ahorro cuando la evidencia es suficiente.
- La configuración elegida se copia a `engine/config_motor.json` (vida_media_dias = 30, lambda_incertidumbre = 0.5).
- Limitación: los datos simulados siguen una estructura parecida a la que supone el modelo, así que la ventaja frente a las referencias probablemente está exagerada respecto a datos reales.