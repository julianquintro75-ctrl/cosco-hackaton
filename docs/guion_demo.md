# Guion de la demostración (≈ 14 minutos, 9 escenas más la 3b)

Datos **sintéticos** (COSCO no entregó datos): las distancias de Buenaventura son reales; precios y desempeño son supuestos del equipo. Las escenas 4 a 9 usan **casos reales de la fase de prueba (1–15 oct 2026)** de `data/cosco.db` con semilla 7; las cifras son las que se ven con esa base. Las escenas 1 a 3 crean solicitudes nuevas (ids `W…`).

**Idea que se repite:** el sistema recomienda y explica; **la persona decide**. Tres personas, tres permisos.

## Antes de empezar

```
docker compose up -d --build         # API :8000 + web :4200
```

(o `bash scripts/preparar_demo.sh` para la versión Streamlit, http://localhost:8501). Abre la web en **http://localhost:4200**. Usuarios de demostración, clave `Cosco-2026!`:

| Usuario | Rol | Qué puede hacer |
|---|---|---|
| `comercial` | solicitante | crear solicitudes y ver las suyas |
| `operador` | operador | revisar pendientes, decidir o devolver |
| `jurado` | gerencia | todo lo anterior + casos escalados por margen negativo, avisos y usuarios |

Para ver Slack: poner en `.env` `COSCO_SLACK_WEBHOOK_OPERACIONES` y `_GERENCIA` (webhooks de Slack, nunca en el repositorio). Sin webhook, los avisos igual quedan en la pantalla **Avisos**.

Usa dos ventanas (una normal y una de incógnito) para ver a dos personas a la vez.

---

## Escena 1 · El solicitante crea una solicitud (2 min)

**Clic:** entra como `comercial` → **Nueva solicitud** → **Llenar con un ejemplo** (o elige cliente, corredor, vehículo, peso y plazo) → **Enviar**.

**Qué se ve:** el botón queda deshabilitado si falta un dato; si el peso supera la capacidad del vehículo avisa en rojo; si el plazo es anterior al cargue, también. Al enviar, la solicitud recibe un id `W…` y aparece en **Mis solicitudes** como «Pendiente».

**Qué decir:** «El comercial no elige proveedor ni ve costos internos: solo describe el envío. Un doble clic o dos pestañas con el mismo envío crean **una sola** solicitud.»

## Escena 2 · El operador recibe el aviso, decide o devuelve (3 min)

**Clic:** en Slack llega «Nueva solicitud … revisar» (o en **Avisos**). Entra como `operador` → **Pendientes** → abre la solicitud nueva → ve el ranking explicado.
- Camino A: **Aprobar #1** → la solicitud pasa a «Decidida» y el solicitante la ve así.
- Camino B: **Devolver al solicitante** → motivo (por ejemplo «datos incompletos») + nota → sale de la cola; el solicitante la ve «Devuelta» con el motivo y el botón **Crear una nueva con estos datos** (el formulario queda prellenado).

**Qué decir:** «Rechazar no es borrar: queda registrado quién devolvió, por qué y cuándo. El solicitante corrige y reenvía en un clic.»

## Escena 3 · Gerencia y el caso escalado (2 min)

**Clic:** con `operador`, abre `R005907` (margen esperado negativo): los botones de decidir están bloqueados con «solo gerencia». Entra como `jurado` → **Gerencia** → decide o devuelve.

**Qué decir:** «Cuando la tarifa no cubre el costo esperado, la decisión sube. El operador no puede saltarse esa regla, y llega un aviso al canal de gerencia.»

## Escena 3b · Qué pasa si llegan dos solicitudes (o dos decisiones) a la vez (2 min)

**Clic:** en la terminal, `python scripts/demo_concurrencia.py` (usa la base de demostración; crea solicitudes nuevas).

**Qué se ve:**
1. Ocho solicitudes simultáneas → ocho ids distintos, ninguna pisa a otra.
2. El mismo envío dos veces a la vez → una sola solicitud (y un solo aviso a Slack).
3. Dos personas deciden la misma solicitud → una queda, la otra recibe «ya fue decidida por …».
4. Una decide y otra devuelve a la vez → solo una de las dos queda.
Además, si dos solicitudes compiten por la **última unidad** de un proveedor, la segunda ya no lo ve disponible (la capacidad comprometida en servicios en curso se descuenta) y, si alguien intenta decidir con una unidad ya tomada, recibe un error claro.

**Qué decir:** «Esto no es de palabra: lo garantiza la base de datos (un índice único y transacciones inmediatas) y lo prueban `tests/test_concurrencia.py` (20 pruebas) y el recorrido de navegador `web/e2e/flujo_nueva.cjs`. Detalle en `docs/CASOS_BORDE.md`.»

---

## Escena 4 · Envío típico Estándar: aprobación en un clic (1,5 min)

**Clic** (web: **Pendientes** → buscar el id; Streamlit: menú «Cargar un caso»): caso `R005909 · C1 V20 general Estandar` → **Recomendar** → **Aprobar #1**.

**Qué se ve:**
- Banda verde «✓ Confianza alta: se puede aprobar en un clic» (confianza 0,95).
- Top-3: **1. TransPacífico $2.929.477** · 2. Economica del Sur $3.122.910 · 3. Altiplano Trans $3.232.660 (costo esperado).
- Barras apiladas del desglose: Economica del Sur es la más barata en precio ($2.192.000 frente a $2.363.000) pero su retraso esperado es mucho mayor (77 % a tiempo frente a 89 %).
- Descartados con motivo: Nuevo Rumbo y Seguridad Total (sin capacidad), FrioCol y Veteranos (no cubren el corredor).
- Tras aprobar: «Decisión registrada … aceptó la recomendación».

**Qué decir:** «La persona sigue decidiendo, pero en los casos claros le toma un clic. El sistema no elige al más barato: elige el menor costo total esperado en pesos, y lo muestra desglosado. TransPacífico era malo a comienzos de año y mejoró entre abril y junio; el sistema ya lo sabe porque los datos recientes pesan más.»

## Escena 5 · La misma solicitud en Flexible y en Urgente: cambia el ganador (1,5 min)

**Clic:** mismo caso `R005909` → cambiar **Nivel de servicio** a `Flexible` → **Recomendar**; luego a `Urgente` → **Recomendar**.

**Qué se ve:**
| Nivel | Costo de un retraso | Ganador | Por qué |
|---|---|---|---|
| Flexible | $300.000 | **Economica del Sur** ($2.370.553) | un retraso casi no cuesta: gana el precio |
| Estándar | $2.500.000 | **TransPacífico** ($2.929.477) | la puntualidad ya vale más que el sobreprecio |
| Urgente | $6.000.000 | **TransPacífico** ($3.624.486), Mulas del Valle sube a #2 | aviso amarillo de revisión detallada (Urgente): la tarifa al cliente ($3.662.000) cubre el costo esperado |

**Qué decir:** «No hay una única respuesta correcta: depende de cuánto cuesta llegar tarde. Por eso el cliente elige el nivel y el sistema lo traduce a pesos. En Urgente, además, siempre pide revisión humana.»

## Escena 6 · El mejor proveedor no tiene capacidad (1,5 min)

**Clic:** caso `R005923 · C4 VCB sobredimensionada Estandar` → **Recomendar**. Luego caso `R005907 · C2 V20 Estandar` → **Recomendar** → barra lateral → **Gerencia**.

**Qué se ve:**
- Descartados: **Altiplano Trans (sin capacidad: 0 unidades VCB en el reporte del 2026-09-26)** y nueve más sin cama baja o sin cobertura.
- Único factible: **Premium Logistics, $12.977.694**. Con capacidad, Altiplano habría costado $10.169.248.
- Margen esperado positivo (tarifa al cliente $15.318.000), sin escalamiento: la excepción es solo que el mejor no estaba disponible.
- Para la pantalla **Gerencia**, `R005907`: Top-1 Mulas del Valle $1.647.003 frente a una tarifa de $1.524.000 → banda roja «⛔ Escalar a gerencia: margen esperado negativo». El caso aparece en la pantalla **Gerencia**.

**Qué decir:** «La capacidad es una regla dura: no se compensa con un buen puntaje. El sistema dice qué se pierde ($2,8 M más) y, cuando la tarifa no cubre el costo esperado (R005907), quién debe decidir y quién debe decidir la excepción: gerencia aprueba, renegocia la tarifa o mueve la fecha.»

## Escena 7 · Proveedor nuevo y sugerencia de prueba (1,5 min)

**Clic:** caso `R005913 · C1 V40 general Flexible` → **Recomendar**.

**Qué se ve:**
- Top-3: Economica del Sur · TransPacífico · **Nuevo Rumbo** (#3) con la alerta «Poco historial: 7 servicios en el corredor» y una penalización visible de incertidumbre.
- Cuadro azul aparte: «🧪 Sugerencia de prueba (aparte del ranking): Nuevo Rumbo tiene solo 7 servicios en este corredor; asignarle este servicio Flexible de bajo riesgo cuesta $241.136 más en costo esperado y ayudaría a evaluarlo. Decide la persona.»

**Qué decir:** «Si un proveedor nuevo nunca recibe carga, nunca sabremos si es bueno. Pero el ranking no usa azar: es determinista. La exploración va aparte, solo en Flexible, nunca con clientes clave, con su costo dicho en pesos, y la persona decide.»

## Escena 8 · Carga peligrosa: filtro duro (1 min)

**Clic:** caso `R005949 · C1 V40 peligrosa Estandar` → **Recomendar**.

**Qué se ve:**
- Único proveedor en el Top: **Seguridad Total** (certificación IMO).
- Nueve descartados con «sin certificación: le falta IMO» (incluidos los más baratos) y dos sin cobertura.
- Tarifa al cliente $4.730.000 frente a un costo esperado de $4.533.515: sin escalamiento, margen ajustado.

**Qué decir:** «Las reglas de seguridad nunca se aprenden ni se relajan: un proveedor sin certificación IMO no entra aunque sea el más barato. Y queda a la vista un riesgo de concentración: en este corredor hay un solo proveedor certificado, así que conviene negociar o certificar a otro.»

## Escena 9 · Andina Cargo se degrada y el sistema lo detecta; comparación con Jev (2,5 min)

**Clic:** **Tableros → Tendencias** (proveedores resaltados: Andina Cargo, TransPacífico, Caribe Express). Bajar a «Repetición del tiempo» y elegir **Andina Cargo**. Luego **Tableros → Ranking y fichas**.

**Qué se ve:**
- Título del gráfico: «⚠ En deterioro: Andina Cargo»; la línea azul cae de ~95 % a ~67 % de entregas a tiempo después de la línea punteada del 1 de agosto. Aviso rojo de la prueba binomial a 30 días.
- Repetición del tiempo: la P(tarde) estimada sigue a la real (verdad oculta, solo para evaluar) con unas semanas de amortiguación.
- Ranking por Índice de Dureza: Andina Cargo baja al puesto 9 de 12.
- En la terminal (opcional, en vivo): `python scripts/replay.py` imprime «Cae del Top-3 en Estandar … retraso de detección 12 días».

**Qué decir (detección):** «Andina era de los mejores hasta julio. Desde el 1 de agosto empieza a fallar. Con decaimiento temporal de 30 días, el sistema la saca del Top-3 en Estándar en unas dos semanas; sin decaimiento nunca lo habría hecho. La vida media y λ no son a ojo: las elegimos con un backtest de 1.586 solicitudes contra la verdad del simulador (`reportes/paso11_backtest.md`).»

**Qué mostrar (comparación):** abrir `reportes/paso13_banco.md` (o `bench/comparacion.png`).
- Motor A: arrepentimiento medio ≈ $96 mil por servicio, elige el óptimo en 66 % de 500 solicitudes; «siempre el más barato» ≈ $205 mil; aleatorio ≈ $386 mil. Robustez: 100 % igual al cambiar orden o nombres, al añadir proveedores irrelevantes y en 20 repeticiones.
- Jev: medido con la misma batería (ver `reportes/paso13_banco.md`); el LLM (Anthropic) se descartó y no se afirma nada sobre él.

**Qué decir (comparación):** «Nuestra arquitectura no depende de un solo modelo: Jev se conecta con el mismo contrato y se midió con la misma batería; mostramos sus números tal cual, sin favorecer a nadie. Lo que sí podemos decir es que nuestro motor es determinista, explicable al peso y cuesta casi cero por decisión.»

---

## Si algo falla en vivo

- La web no abre: `docker compose up -d --build` y revisar http://localhost:4200. La API: http://localhost:8000/docs. Versión Streamlit: `streamlit run app/ui.py`.
- Slack no recibe: revisar los webhooks en `.env`; el aviso siempre queda en la pantalla **Avisos**.
- Un caso no aparece en el menú: la base no es la de semilla 7 → correr de nuevo `preparar_demo`.
- Sin internet: los tableros funcionan (Plotly va dentro de Streamlit); solo `reportes/reporte_datos.html` carga Plotly desde internet.
- Respaldo: video de 5 minutos con estas escenas (grabarlo con la base de semilla 7 después de correr `preparar_demo`).
