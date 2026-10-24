# Recomendador de proveedores · COSCO SHIPPING (Sabana Hack 2026)

Sistema de apoyo a la decisión para transporte terrestre en Colombia: para cada solicitud recomienda un **Top-3 de proveedores**, explicado en pesos, y **una persona decide**. Los datos son **sintéticos** (COSCO no los entregó); la verdad oculta del simulador solo se usa para evaluar.

![Pantalla Nueva solicitud con la recomendación](docs/img/ui_recomendacion.png)

## Arranque rápido

**Con Docker (cualquier computador con Docker Desktop o Engine):**
```bash
git clone <url-del-repo> && cd cosco-hackaton
docker compose up --build
```
API en <http://localhost:8000/docs> · Interfaz en <http://localhost:8501>. La primera vez genera los datos sintéticos (~1 min). Puertos configurables copiando `.env.example` a `.env`.

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
| `POST /decision` | Registra qué decidió la persona (y por qué si se aparta) |
| `POST /cierre` | Registra el resultado real del servicio |
| `GET /proveedores/{id}/ficha` | Ficha e Índice de Dureza |

## Estructura

```
app/        API (FastAPI) · interfaz y tableros (Streamlit)
engine/     estadística, fichas, modelos, motor A, configuración
contratos/  contratos pydantic (fuente de verdad, con db/schema.sql)
seed/       generador sintético, 35 reglas de calidad, simulador en vivo
scripts/    replay, backtest, demo, init_datos (Docker)
bench/      banco de comparación de motores
tests/      pytest
docs/       arquitectura, revisión, guion de demo, referencias, imágenes
```

## Extender sin reescribir

- **La UI solo habla con la API** (`app/cliente_api.py`); otro frontend puede hacer lo mismo.
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
