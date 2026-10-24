# Recomendador de proveedores · COSCO SHIPPING (Sabana Hack 2026)

Sistema de apoyo a la decisión para transporte terrestre en Colombia: para cada solicitud recomienda un **Top-3 de proveedores**, explicado en pesos, y **una persona decide**. Los datos son **sintéticos** (COSCO no los entregó); la verdad oculta del simulador solo se usa para evaluar.

![Pantalla Nueva solicitud con la recomendación](docs/img/ui_recomendacion.png)

## Arranque rápido

**Con Docker (cualquier computador con Docker Desktop o Engine):**
```bash
git clone <url-del-repo> && cd cosco-hackaton
docker compose up --build
```
**Frontend Angular en <http://localhost:4200>** (inicia sesión con el usuario de demostración que muestra la pantalla de acceso: `jurado` / `Cosco-2026!`) · API en <http://localhost:8000/docs> · interfaz Streamlit alterna en <http://localhost:8501>. La primera vez genera los datos sintéticos (~1 min). Puertos configurables copiando `.env.example` a `.env`.

**Sin Docker (Python 3.10+):**
```bash
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\Activate.ps1
make instalar datos test      # o: pip install -r requirements-dev.txt && python scripts/init_datos.py && pytest
make api                      # terminal 1
make ui                       # terminal 2
```
En Windows sin `make`: `scripts\setup.ps1` y luego `uvicorn app.api:app` / `streamlit run app/ui.py`.

## Cómo decide

`filtros duros → estadística bayesiana con decaimiento → costo total esperado → explicación → decide una persona`

- **Filtros duros**: certificación, vehículo, tarifa y capacidad; cada descartado lleva su motivo.
- **Bayes**: Beta(17,3) por proveedor × corredor × tipo de carga, vida media del dato 30 días.
- **Costo esperado** = precio + P(tarde)·costo del retraso (según nivel de servicio) + P(incidente)·costo + λ·ancho del IC90·costo + penalización por concentración. Margen = tarifa al cliente − costo esperado.
- **Determinista**: misma entrada, misma salida (≈11–18 ms).
- **Motores intercambiables** mediante el contrato `MotorDecision`: A (propio, medido), B (Jev) y C (LLM) **no medidos**.

![Replay de Andina Cargo](docs/img/replay_andina.png)

## Arquitectura

![Arquitectura](docs/img/arquitectura.png)

Detalle, decisiones y puntos de extensión en [`docs/ARQUITECTURA.md`](docs/ARQUITECTURA.md). Versión web: [`docs/arquitectura/index.html`](docs/arquitectura/index.html).

## Tableros

| | |
|---|---|
| ![Precios](docs/img/tablero_precios.png) | ![Tránsito](docs/img/tablero_transito.png) |
| ![Capacidad](docs/img/tablero_capacidad.png) | ![Vehículos](docs/img/tablero_vehiculos.png) |
| ![Tendencias](docs/img/tablero_tendencias.png) | ![Ranking](docs/img/tablero_ranking.png) |
| ![Gestión](docs/img/tablero_gestion.png) | ![Banco de comparación](docs/img/bench_comparacion.png) |

## API

| Método y ruta | Uso |
|---|---|
| `GET /salud` | Estado del servicio y de los datos |
| `POST /recomendar` | Solicitud → Top-3, descartados, alertas, explicación |
| `POST /solicitudes` | Crea una solicitud nueva (cliente, corredor, vehículo, peso, plazo); idempotente por `clave_envio` |
| `POST /decision` | Registra qué decidió la persona (y por qué si se aparta) |
| `POST /cierre` | Registra el resultado real del servicio |
| `GET /proveedores/{id}/ficha` | Ficha e Índice de Dureza |

## Frontend Angular, idiomas y acceso

`web/` contiene una interfaz Angular en **español, inglés y chino (简体中文)** con inicio de sesión (JWT, contraseñas con PBKDF2, bloqueo tras 5 intentos fallidos) y los colores de COSCO SHIPPING. Detalle en [`web/README.md`](web/README.md).
Toda la API (salvo `/salud` y `/auth/login`) exige sesión; el usuario semilla es **solo de demostración** (ver `.env.example` para cambiarlo y fijar `COSCO_JWT_SECRET`).
Sin Docker: `make api` y, en otra terminal, `make web-instalar && make web` (Node ≥ 22.12).

## Roles y avisos por Slack

Tres roles, con un usuario de demostración cada uno (misma contraseña del usuario semilla, `Cosco-2026!`):

| Rol | Usuario | Qué puede hacer |
|---|---|---|
| **Solicitante** (comercial) | `comercial` | Pide recomendaciones, las ve y sigue el estado de **sus** solicitudes. No decide. |
| **Operador** (operaciones) | `operador` | Todo lo anterior, más revisar los casos pendientes, decidir y cerrar servicios; ve proveedores, panel y el historial de avisos. |
| **Gerencia** | `jurado` | Todo, además de decidir lo **escalado a gerencia** y activar o desactivar los avisos. |

Los permisos los hace cumplir la API (HTTP 403), no solo el menú del frontend.

**Avisos por Slack.** Cuando una recomendación necesita a una persona, se avisa **una sola vez por solicitud**: «revisión necesaria» al canal de operaciones y «escalamiento» al de gerencia, con corredor, motivos, la primera opción del modelo y un enlace al caso. Si Slack falla, la recomendación sigue su curso y el caso queda en «Pendientes»; el fallo se ve en el historial de la pantalla **Avisos**.

1. En Slack crea un *Incoming Webhook* (api.slack.com/messaging/webhooks) para cada canal.
2. Pon las URLs en tu `.env` (no se versiona): `COSCO_SLACK_WEBHOOK` para un solo canal, o `COSCO_SLACK_WEBHOOK_OPERACIONES` y `COSCO_SLACK_WEBHOOK_GERENCIA` para canales separados. Solo se aceptan URLs `https://hooks.slack.com/…`, y la API nunca las devuelve.
3. Reinicia con `docker compose up -d`. En **Avisos** (gerencia) activas o desactivas cada tipo de aviso y envías un mensaje de prueba.

Endpoints nuevos: `GET /mis-solicitudes`, `GET`/`PUT /notificaciones/ajustes`, `GET /notificaciones/historial`, `POST /notificaciones/probar`.

## Solicitudes nuevas, devolución y solicitudes simultáneas

- **Nueva solicitud** (pantalla propia, `POST /solicitudes`): el servidor asigna el id, valida peso contra la capacidad del vehículo y el plazo contra el cargue.
- **Devolver al solicitante** (`POST /rechazo`, operador o gerencia; lo escalado, solo gerencia): motivo obligatorio y nota; el solicitante lo ve como «Devuelta» y puede crear una nueva con los mismos datos. Consulta: `GET /rechazos/{sid}`.
- **Dos a la vez**: una solicitud solo puede decidirse o devolverse una vez, la capacidad comprometida se descuenta y un doble envío crea una sola solicitud. Tabla completa en [`docs/CASOS_BORDE.md`](docs/CASOS_BORDE.md); demo en vivo con `python scripts/demo_concurrencia.py`.
- Guion de la demostración por roles: [`docs/guion_demo.md`](docs/guion_demo.md).

## Estructura

```
app/        API (FastAPI, con autenticación) · interfaz y tableros (Streamlit)
web/        frontend Angular (es · en · zh)
engine/     estadística, fichas, modelos, motor A, configuración
contratos/  contratos pydantic (fuente de verdad, con db/schema.sql)
seed/       generador sintético, 35 reglas de calidad, simulador en vivo
scripts/    replay, backtest, demo, init_datos (Docker)
bench/      banco de comparación de motores
tests/      pytest
docs/       arquitectura, revisión, guion de demo, referencias, imágenes
```

## Extender sin reescribir

- **Los frontends solo hablan con la API** (Angular por HTTP con sesión; Streamlit vía `app/cliente_api.py`); otro frontend puede hacer lo mismo.
- **La base de datos está detrás de un puerto** (`engine/repositorio.py`): para PostgreSQL u otra se escribe una clase, se registra con `registrar_backend` y se apunta `COSCO_REPO`; `tests/test_repositorio.py` define el contrato.
- **Reentrenamiento nocturno** de M1/M2 (`docker compose --profile ml up -d` o `make reentrenar`): publica un candidato solo si supera a la estadística bayesiana y lo deja pendiente de aprobación humana.

## Reglas del proyecto

1. Contratos y esquema son la fuente de verdad.
2. `data/verdad_oculta.csv` nunca entra al motor ni al entrenamiento.
3. Todo cálculo recibe `as_of` y no ve el futuro.
4. Si algo no se midió, se escribe «no medido».

Más contexto: [`CLAUDE.md`](CLAUDE.md), [`PASOS_Y_PROMPTS.md`](PASOS_Y_PROMPTS.md), [`docs/REVISION_PROYECTO.md`](docs/REVISION_PROYECTO.md), [`docs/guion_demo.md`](docs/guion_demo.md), [`docs/VALOR_DE_NEGOCIO.md`](docs/VALOR_DE_NEGOCIO.md), [`docs/CASOS_DIFICILES.md`](docs/CASOS_DIFICILES.md).

**Datos reales:** llena `docs/referencia/plantilla_datos.xlsx` y cárgala con `python -m scripts.importar_datos datos.xlsx --out data/real.db`; luego `COSCO_DB=data/real.db`.

## Pruebas y calidad

`make test` (41 pruebas), `make lint` (ruff), CI en `.github/workflows/ci.yml`.
