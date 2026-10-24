# Casos borde: solicitudes simultáneas y decisiones cruzadas

Qué pasa cuando varias personas actúan a la vez. Cada fila tiene su prueba en `tests/test_concurrencia.py`; el recorrido de navegador está en `web/e2e/flujo_nueva.cjs`; la demostración en vivo, en `scripts/demo_concurrencia.py`.

| Situación | Qué hace el sistema | Cómo se garantiza |
|---|---|---|
| Llegan 8 solicitudes nuevas a la vez | 8 solicitudes distintas, ninguna se pierde ni se mezcla | el servidor asigna el id (`W<fecha>-<clave>`) y serializa el cálculo con un candado |
| Doble clic / mismo envío desde dos pestañas | **una** solicitud y **un** aviso a Slack | `clave_envio` idempotente; si se reutiliza con datos distintos → 409; el aviso se reclama de forma atómica (`aviso_reclamo`) |
| Dos personas deciden la misma solicitud | gana una (200); la otra recibe 409 «ya fue decidida por …» | `BEGIN IMMEDIATE` + índice único parcial `ux_decision_solicitud` (también protege entre procesos) |
| Una decide y otra devuelve a la vez | queda solo una de las dos acciones | ambas operaciones corren en transacción inmediata y se revisan mutuamente |
| Decidir una solicitud ya devuelta (o devolver una ya decidida) | 409 con el nombre de quien actuó primero | verificación dentro de la misma transacción |
| Dos solicitudes compiten por la última unidad de un proveedor | la primera la toma; la segunda ya no ve ese proveedor (descartado por capacidad comprometida) | `Base.reservadas()` descuenta los servicios en curso decididos después de la foto de capacidad |
| Se intenta decidir con una unidad que ya se tomó | 409 «ya no tiene unidades …» | `_capacidad_vigente` se vuelve a revisar al decidir |
| Un operador intenta decidir o devolver un caso escalado | 403; solo gerencia | `auth.exigir_rol` |
| Base ocupada por otra escritura | espera hasta 30 s en vez de fallar | `sqlite3.connect(timeout=30)` |

## Límites conocidos (dichos con honestidad)

- La reserva de capacidad cuenta solo las decisiones posteriores a la última foto de capacidad; no ordena por fecha de cargue.
- Con SQLite un solo proceso escribe a la vez. Es suficiente para el volumen del reto; para más, se cambia el adaptador (`Repositorio`) a PostgreSQL sin tocar el motor.
- El modo Streamlit en proceso no envía avisos de fondo; la web con la API sí.
- Las pruebas de capacidad simultánea usan hilos sobre una sola API; no sustituyen una prueba de carga.
