# Paso 10 · Modelos M1 y M2 frente a la línea base bayesiana

Datos sintéticos. División temporal: entrenamiento hasta 2026-05-31 (3660 servicios), calibración isotónica en junio (530), validación julio–septiembre (1539). Variables calculadas con as_of = fecha de la solicitud (sin fuga).

## M1 · Probabilidad de entrega a tiempo

| Modelo | AUC (↑) | Brier (↓) |
|---|---|---|
| Línea base bayesiana (motor A) | 0.5966 | 0.1389 |
| CatBoost sin calibrar | 0.5979 | 0.1384 |
| CatBoost + isotónica | 0.6048 | 0.1400 |

### Curva de calibración (validación, deciles de probabilidad predicha)

| Bayes: predicho | Bayes: real | n | CatBoost: predicho | CatBoost: real | n |
|---|---|---|---|---|---|
| 0.752 | 0.747 | 154 | 0.644 | 0.716 | 155 |
| 0.786 | 0.695 | 154 | 0.801 | 0.741 | 228 |
| 0.814 | 0.812 | 154 | 0.838 | 0.855 | 826 |
| 0.830 | 0.864 | 154 | 0.933 | 0.808 | 73 |
| 0.841 | 0.794 | 155 | 0.948 | 0.901 | 243 |
| 0.852 | 0.888 | 152 | 0.987 | 0.929 | 14 |

## M2 · Tiempo de tránsito (horas)

| Modelo | Pinball P50 (↓) | Pinball P90 (↓) | Cobertura real del P90 (ideal 0,90) |
|---|---|---|---|
| Línea base (percentiles ponderados del corredor) | 2.175 | 1.928 | 0.876 |
| LightGBM quantile | 2.131 | 1.878 | 0.878 |

## Variables más influyentes en M1 (|SHAP| medio)

- p_tarde_corredor: 0.1486
- p_tarde_365: 0.0646
- proveedor_id: 0.0577
- p_tarde_90: 0.0558
- n_365: 0.0487
- transito_med_corredor: 0.0462
- exp_corredor: 0.0363
- lluvia: 0.0362

## Decisión

- **M1 NO mejora la línea base bayesiana de forma suficiente: el motor se queda con el bayesiano.** Criterio: Brier al menos 0,002 menor y AUC no peor.
- **M2 NO mejora la línea base de forma suficiente: el motor se queda con los percentiles bayesianos.** Criterio: pinball P50 y P90 al menos 3 % menores.
- Advertencia: la validación usa solo los servicios que la política humana histórica eligió (sesgo de selección); el backtest del paso 11 evalúa con la verdad oculta.
- Los modelos quedan guardados en `engine/modelos/` y registrados en `modelo_version`; el reentrenamiento nocturno solo publicaría una versión nueva si mejora estas métricas.