# Paso 5 · Motor A (sin ML)

Solicitud de la fase de prueba en los tres niveles (`python -m engine.motor_a`). Datos sintéticos; costos de retraso ilustrativos.
```

== Flexible · R005908 C1 V20 · 31.42 ms · revisión=[] · confianza=0.971
  1. Economica del Sur    total   $2.457.162 = precio $2.192.000 + retraso $70.292 + inc $137.300 + incert $57.570 + conc $0 | P(a tiempo) 77% n=194 Cuarzo
  2. Nuevo Rumbo          total   $2.703.670 = precio $2.530.000 + retraso $36.008 + inc $76.195 + incert $61.467 + conc $0 | P(a tiempo) 88% n=7 Zafiro
  3. Andina Cargo         total   $2.750.647 = precio $2.578.000 + retraso $51.532 + inc $66.590 + incert $54.525 + conc $0 | P(a tiempo) 83% n=155 Zafiro
   Se recomienda Economica del Sur con costo esperado $2.457.162 y P(a tiempo) 77% (194 servicios en el corredor). Supera a Nuevo Rumbo por $246.508, sobre todo por precio ($338.000). Nivel Flexible: un retraso cuesta $300.000.

== Estandar · R005908 C1 V20 · 11.62 ms · revisión=['empate_tecnico', 'margen_negativo'] · confianza=0.611
  1. Economica del Sur    total   $3.394.814 = precio $2.192.000 + retraso $585.766 + inc $137.300 + incert $479.748 + conc $0 | P(a tiempo) 77% n=194 Cuarzo
  2. Mulas del Valle      total   $3.415.501 = precio $2.597.000 + retraso $400.884 + inc $59.378 + incert $303.106 + conc $55.133 | P(a tiempo) 84% n=347 Cuarzo
  3. Nuevo Rumbo          total   $3.418.492 = precio $2.530.000 + retraso $300.069 + inc $76.195 + incert $512.228 + conc $0 | P(a tiempo) 88% n=7 Zafiro
   Se recomienda Economica del Sur con costo esperado $3.394.814 y P(a tiempo) 77% (194 servicios en el corredor). Supera a Mulas del Valle por $20.687, sobre todo por precio ($405.000). Nivel Estandar: un retraso cuesta $2.500.000.

== Urgente · R005908 C1 V20 · 11.3 ms · revisión=['urgente', 'margen_negativo'] · confianza=0.817
  1. Mulas del Valle      total   $4.401.087 = precio $2.597.000 + retraso $962.121 + inc $59.378 + incert $727.455 + conc $55.133 | P(a tiempo) 84% n=347 Cuarzo
  2. Nuevo Rumbo          total   $4.555.707 = precio $2.530.000 + retraso $720.165 + inc $76.195 + incert $1.229.347 + conc $0 | P(a tiempo) 88% n=7 Zafiro
  3. Andina Cargo         total   $4.765.722 = precio $2.578.000 + retraso $1.030.638 + inc $66.590 + incert $1.090.494 + conc $0 | P(a tiempo) 83% n=155 Zafiro
   Se recomienda Mulas del Valle con costo esperado $4.401.087 y P(a tiempo) 84% (347 servicios en el corredor). Supera a Nuevo Rumbo por $154.620, sobre todo por incertidumbre (poca evidencia) ($501.892). El más barato (Economica del Sur, $2.192.000) sale más caro en costo esperado por su riesgo de retraso o incertidumbre. Nivel Urgente: un retraso cuesta $6.000.000.
```

Determinismo: la misma solicitud repetida 100 veces produce **1** JSON distinto (se excluye solo `latencia_ms`). Latencia mediana medida ≈ 30 ms por recomendación.
