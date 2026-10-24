# Paso 12 · Tableros

`streamlit run app/ui.py` → pestaña **Tableros** (o solo: `streamlit run app/tableros.py`). Datos **sintéticos**. Filtros comunes: corredores, rango de fechas y hasta 3 proveedores resaltados (el resto en gris). Cada título dice la conclusión.

| Pestaña | Pregunta del enunciado | Qué muestra |
|---|---|---|
| Precios | ¿Quién es caro o barato en cada corredor? | Mapa de calor proveedor × corredor del índice de precio (tarifa / mediana del corredor) y dispersión precio vs. puntualidad |
| Tiempos de tránsito | ¿Cuánto tarda y qué tan variable es? | Cajas por proveedor y corredor con P50/P90 frente al plazo típico |
| Capacidad | ¿Quién tiene capacidad esta semana? | Barras de unidades disponibles/ocupadas con % de utilización y matriz por semana |
| Disponibilidad de vehículos | ¿Qué vehículos escasean? | Matriz proveedor × vehículo y alertas de vehículos con un solo proveedor |
| Tendencias | ¿Quién mejora o empeora y desde cuándo? | Puntualidad mensual con banda del 90 %, alerta de deterioro (binomial a 30 días) y P(tarde) estimada vs. real del replay |
| Ranking y fichas | ¿Cómo se comparan y qué riesgos tienen? | Ranking por Índice de Dureza, dureza por corredor, fichas con fortalezas y debilidades |
| Gestión | ¿Estamos concentrados? ¿Se acepta la recomendación? | Cuota por proveedor y HHI, tasa de aceptación, motivos de rechazo y costo esperado vs. real |

Verificado con el simulador de Streamlit (sin excepciones, 11 gráficas) y revisión visual de cada pestaña en navegador.
Hallazgos visibles: Andina Cargo baja de ~95 % a ~67 % de puntualidad desde agosto y aparece «En deterioro»; TransPacífico sube de ~65 % a ~90 %; Economica del Sur es la más barata en todos sus corredores y Premium Logistics la más cara.
