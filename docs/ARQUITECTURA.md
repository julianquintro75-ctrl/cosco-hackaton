# Arquitectura

![Arquitectura](img/arquitectura.png)

## Capas y reglas de dependencia

| Capa | Código | Puede depender de |
|---|---|---|
| 1 Clientes | `app/ui.py`, `app/tableros.py`, `scripts/demo_api.py` | API (meta) |
| 2 API | `app/api.py` | motores, contratos |
| 3 Decisión | `engine/motor_a.py` (+ B y C por implementar) | núcleo, contratos |
| 4 Núcleo | `engine/estadisticas.py`, `fichas.py`, `modelos.py`, `config_motor.json` | datos, contratos |
| 5 Datos | `engine/datos.py`, `db/schema.sql`, SQLite | nada |

Una capa solo conoce a la de abajo. `contratos/` es transversal.

## Estado real

- **La UI no abre la base de datos.** Todo pasa por `app/cliente_api.py`: por HTTP si existe `COSCO_API_URL` (Docker) y en proceso si no. Para armar los tableros descarga una instantánea de tablas (`GET /datos/tablas`) y construye su propio `Base` con `app/contexto.py`. En Docker el servicio `ui` ni siquiera monta el volumen de datos.
- **Un solo módulo ejecuta SQL de la aplicación:** `engine/repo_sqlite.py`, detrás del puerto `engine/repositorio.py`. Lo verifica `tests/test_repositorio.py::test_capas_altas_no_hablan_sql`. (Siguen usando SQLite directamente solo el generador `seed/`, los scripts de evaluación `scripts/backtest.py`, `replay.py`, `bench/` y `en_vivo.py`, que son herramientas sin conexión.)
- Mientras no haya otro backend registrado, el acceso sigue siendo SQLite.

## Cómo extender

| Quiero agregar | Qué hacer |
|---|---|
| Un frontend (React, móvil) | Consumir la API; CORS en `app/api.py`; nuevo servicio en `docker-compose.yml` |
| Otro servicio backend | Nuevo bloque en `services:` (red `cosco`); la API lo llama por HTTP; mensajes como modelos pydantic en `contratos/` |
| Otro motor | Clase que cumpla `MotorDecision`; registrarla en la API; medirla en `bench/` antes de afirmar nada |
| Otra base de datos | 1) clase que cumpla `Repositorio` (`engine/repositorio.py`), 2) `registrar_backend("postgresql", MiRepo)`, 3) `COSCO_REPO=postgresql://…`, 4) agregar su fábrica a `FABRICAS` en `tests/test_repositorio.py`: si pasa, el resto del sistema no cambia |

## Concurrencia con SQLite

Ahora solo la API (y el reentrenador, que escribe el registro de modelos) escriben en el archivo. Basta para una demo; con varios usuarios activar WAL o pasar a PostgreSQL.

## Despliegue

`docker-compose.yml`: `init-datos` (una vez, idempotente) → `api` (8000) → `ui` (8501, sin volumen); perfil opcional `ml` con el `reentrenador` nocturno. Una sola imagen para todos. Para reiniciar los datos: `docker compose down -v`.

## Reentrenamiento nocturno (`scripts/reentrenar.py`)

Ventanas móviles respecto al «hoy» (entrena hasta −60 d, calibra −60…−30 d, valida los últimos 30 d). Publica un candidato **solo** si supera a la estadística bayesiana (M1: Brier −0,002 sin perder AUC; M2: pinball P50 y P90 −3 %) y la validación tiene ≥ 300 servicios. El candidato queda en `engine/modelos/candidato/` y en `modelo_version` como «pendiente de aprobacion»: **el motor A no lo usa todavía**; una persona decide. Cada corrida se registra en `data/reentrenamiento_log.jsonl`. `docker compose --profile ml up -d` lo deja corriendo a las 02:00.
