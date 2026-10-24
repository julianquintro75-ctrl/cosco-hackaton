# Guion de la demostración (≈ 10 minutos, 6 escenas)

Datos **sintéticos** (COSCO no entregó datos): las distancias de Buenaventura son reales; precios y desempeño son supuestos del equipo. Todas las solicitudes son **casos reales de la fase de prueba (1–15 oct 2026)** de `data/cosco.db` con semilla 7. Las cifras de abajo son las que se ven en pantalla con esa base; si se regenera con otra semilla, cambian.

## Antes de empezar (5 minutos antes)

```
bash scripts/preparar_demo.sh                                         # Mac/Linux
powershell -ExecutionPolicy Bypass -File scripts\preparar_demo.ps1     # Windows
```

Reinicia la base, valida (debe decir «0 críticas»), recalcula estadísticas y la repetición del tiempo, y abre la API (http://127.0.0.1:8000/docs) y la interfaz (http://localhost:8501). Deja abiertas dos pestañas: **Nueva solicitud** y **Tableros → Tendencias**.

Para cargar un caso: en «Nueva solicitud», menú **«Cargar un caso de la fase de prueba»**, escribe el número (por ejemplo `R005909`) y elígelo. El formulario se llena solo; el «hoy» del sistema (as_of) queda en la víspera del cargue.

---

## Escena 1 · Envío típico Estándar: aprobación en un clic (1,5 min)

**Clic:** caso `R005909 · C1 V20 general Estandar` → **Recomendar** → **Aprobar #1**.

**Qué se ve:**
- Banda verde «✓ Confianza alta: se puede aprobar en un clic» (confianza 0,95).
- Top-3: **1. TransPacífico $2.929.477** · 2. Economica del Sur $3.122.910 · 3. Altiplano Trans $3.232.660 (costo esperado).
- Barras apiladas del desglose: Economica del Sur es la más barata en precio ($2.192.000 frente a $2.363.000) pero su retraso esperado es mucho mayor (77 % a tiempo frente a 89 %).
- Descartados con motivo: Nuevo Rumbo y Seguridad Total (sin capacidad), FrioCol y Veteranos (no cubren el corredor).
- Tras aprobar: «Decisión registrada … aceptó la recomendación».

**Qué decir:** «La persona sigue decidiendo, pero en los casos claros le toma un clic. El sistema no elige al más barato: elige el menor costo total esperado en pesos, y lo muestra desglosado. TransPacífico era malo a comienzos de año y mejoró entre abril y junio; el sistema ya lo sabe porque los datos recientes pesan más.»

## Escena 2 · La misma solicitud en Flexible y en Urgente: cambia el ganador (1,5 min)

**Clic:** mismo caso `R005909` → cambiar **Nivel de servicio** a `Flexible` → **Recomendar**; luego a `Urgente` → **Recomendar**.

**Qué se ve:**
| Nivel | Costo de un retraso | Ganador | Por qué |
|---|---|---|---|
| Flexible | $300.000 | **Economica del Sur** ($2.370.553) | un retraso casi no cuesta: gana el precio |
| Estándar | $2.500.000 | **TransPacífico** ($2.929.477) | la puntualidad ya vale más que el sobreprecio |
| Urgente | $6.000.000 | **TransPacífico** ($3.624.486), Mulas del Valle sube a #2 | aviso amarillo de revisión detallada (Urgente) y rojo de escalamiento: el margen esperado es negativo con la tarifa al cliente |

**Qué decir:** «No hay una única respuesta correcta: depende de cuánto cuesta llegar tarde. Por eso el cliente elige el nivel y el sistema lo traduce a pesos. En Urgente, además, siempre pide revisión humana, y si la tarifa no cubre el riesgo lo escala a gerencia antes de comprometerse.»

## Escena 3 · El mejor proveedor no tiene capacidad (1,5 min)

**Clic:** caso `R005923 · C4 VCB sobredimensionada Estandar` → **Recomendar**. Después, barra lateral → **Gerencia**.

**Qué se ve:**
- Descartados: **Altiplano Trans (sin capacidad: 0 unidades VCB en el reporte del 2026-09-26)** y nueve más sin cama baja o sin cobertura.
- Único factible: **Premium Logistics, $12.977.694**. Con capacidad, Altiplano habría costado $10.169.248.
- Banda roja «⛔ Escalar a gerencia: margen esperado negativo» (tarifa al cliente $12.556.000). El caso aparece en la pantalla **Gerencia**.

**Qué decir:** «La capacidad es una regla dura: no se compensa con un buen puntaje. El sistema dice qué se pierde ($2,8 M más) y quién debe decidir la excepción: gerencia aprueba, renegocia la tarifa o mueve la fecha.»

## Escena 4 · Proveedor nuevo y sugerencia de prueba (1,5 min)

**Clic:** caso `R005913 · C1 V40 general Flexible` → **Recomendar**.

**Qué se ve:**
- Top-3: Economica del Sur · TransPacífico · **Nuevo Rumbo** (#3) con la alerta «Poco historial: 7 servicios en el corredor» y una penalización visible de incertidumbre.
- Cuadro azul aparte: «🧪 Sugerencia de prueba (aparte del ranking): Nuevo Rumbo tiene solo 7 servicios en este corredor; asignarle este servicio Flexible de bajo riesgo cuesta $241.136 más en costo esperado y ayudaría a evaluarlo. Decide la persona.»

**Qué decir:** «Si un proveedor nuevo nunca recibe carga, nunca sabremos si es bueno. Pero el ranking no usa azar: es determinista. La exploración va aparte, solo en Flexible, nunca con clientes clave, con su costo dicho en pesos, y la persona decide.»

## Escena 5 · Carga peligrosa: filtro duro (1 min)

**Clic:** caso `R005949 · C1 V40 peligrosa Estandar` → **Recomendar**.

**Qué se ve:**
- Único proveedor en el Top: **Seguridad Total** (certificación IMO).
- Nueve descartados con «sin certificación: le falta IMO» (incluidos los más baratos) y dos sin cobertura.
- Escalamiento a gerencia porque la tarifa al cliente ($3.877.000) no cubre el costo esperado ($4.533.515).

**Qué decir:** «Las reglas de seguridad nunca se aprenden ni se relajan: un proveedor sin certificación IMO no entra aunque sea el más barato. Y queda a la vista un riesgo de negocio: en este corredor hay un solo proveedor certificado, así que conviene negociar o certificar a otro.»

## Escena 6 · Andina Cargo se degrada y el sistema lo detecta; comparación con Jev (2,5 min)

**Clic:** **Tableros → Tendencias** (proveedores resaltados: Andina Cargo, TransPacífico, Caribe Express). Bajar a «Repetición del tiempo» y elegir **Andina Cargo**. Luego **Tableros → Ranking y fichas**.

**Qué se ve:**
- Título del gráfico: «⚠ En deterioro: Andina Cargo»; la línea azul cae de ~95 % a ~67 % de entregas a tiempo después de la línea punteada del 1 de agosto. Aviso rojo de la prueba binomial a 30 días.
- Repetición del tiempo: la P(tarde) estimada sigue a la real (verdad oculta, solo para evaluar) con unas semanas de amortiguación.
- Ranking por Índice de Dureza: Andina Cargo baja al puesto 9 de 12.
- En la terminal (opcional, en vivo): `python scripts/replay.py` imprime «Cae del Top-3 en Estandar … retraso de detección 12 días».

**Qué decir (detección):** «Andina era de los mejores hasta julio. Desde el 1 de agosto empieza a fallar. Con decaimiento temporal de 30 días, el sistema la saca del Top-3 en Estándar en unas dos semanas; sin decaimiento nunca lo habría hecho. La vida media y λ no son a ojo: las elegimos con un backtest de 1.586 solicitudes contra la verdad del simulador (`reportes/paso11_backtest.md`).»

**Qué mostrar (comparación):** abrir `reportes/paso13_banco.md` (o `bench/comparacion.png`).
- Motor A: arrepentimiento medio ≈ $96 mil por servicio, elige el óptimo en 66 % de 500 solicitudes; «siempre el más barato» ≈ $205 mil; aleatorio ≈ $386 mil. Robustez: 100 % igual al cambiar orden o nombres, al añadir proveedores irrelevantes y en 20 repeticiones.
- Jev y LLM: **«no medido»** (no hubo clave de API en el entorno de pruebas).

**Qué decir (comparación):** «Nuestra arquitectura no depende de un solo modelo: Jev o un LLM se conectan con el mismo contrato y se miden con la misma batería. Todavía no los medimos, así que no afirmamos nada sobre ellos. Lo que sí podemos decir es que nuestro motor es determinista, explicable al peso y cuesta casi cero por decisión.»

---

## Si algo falla en vivo

- La interfaz no abre: `streamlit run app/ui.py` a mano. La API: `uvicorn app.api:app`.
- Un caso no aparece en el menú: la base no es la de semilla 7 → correr de nuevo `preparar_demo`.
- Sin internet: los tableros funcionan (Plotly va dentro de Streamlit); solo `reportes/reporte_datos.html` carga Plotly desde internet.
- Respaldo: video de 5 minutos con estas 6 escenas (grabarlo con la base de semilla 7 después de correr `preparar_demo`).
