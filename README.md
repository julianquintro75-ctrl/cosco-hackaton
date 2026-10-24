# Recomendador de proveedores · COSCO SHIPPING (Sabana Hack 2026)
- `db/schema.sql` · esquema SQLite (16 tablas)
- `contratos/contracts.py` · contratos de entrada/salida (pydantic)
- `seed/` · mundo sintético con historias: `python seed/generate.py --sucio`, luego `python seed/check_story.py`
- `PASOS_Y_PROMPTS.md` · guía paso a paso con prompts para Claude Code
- `engine/` · estadísticas bayesianas con decaimiento, motor A (costo total esperado), fichas y modelos M1/M2
- `app/` · API FastAPI (`uvicorn app.api:app`) e interfaz + tableros Streamlit (`streamlit run app/ui.py`)
- `scripts/` · `replay.py` (repetición del tiempo), `backtest.py`, `demo_api.py`, `preparar_demo.sh` / `.ps1`
- `bench/comparar.py` · banco de comparación con Jev y un LLM · `reportes/` · reporte de cada paso
- `docs/guion_demo.md` · guion de la demostración en 6 escenas

Datos **sintéticos**: COSCO no entregó datos.
