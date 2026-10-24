.PHONY: help instalar datos test lint reentrenar api ui demo docker docker-bajar docker-limpiar
PY ?= python
help:            ## Muestra esta ayuda
	@grep -E '^[a-z-]+:.*##' $(MAKEFILE_LIST) | awk -F':.*## ' '{printf "  make %-15s %s\n", $$1, $$2}'
instalar:        ## Instala dependencias (usa un venv)
	$(PY) -m pip install -r requirements-dev.txt
datos:           ## Genera datos sintéticos si faltan
	$(PY) scripts/init_datos.py
test:            ## Corre las pruebas
	$(PY) -m pytest -q
lint:            ## Revisa estilo con ruff
	ruff check app engine scripts tests --select F,E9
reentrenar:      ## Reentrena M1/M2 una vez (publica solo si mejora a bayes)
	$(PY) scripts/reentrenar.py
api:             ## API en http://localhost:8000/docs
	uvicorn app.api:app --reload
ui:              ## Interfaz en http://localhost:8501 (COSCO_API_URL=http://localhost:8000 para usar la API por HTTP)
	streamlit run app/ui.py
demo:            ## Prepara y arranca la demo completa (Linux/Mac)
	bash scripts/preparar_demo.sh
docker:          ## Todo en contenedores: API + UI
	docker compose up --build
docker-bajar:    ## Detiene los contenedores (conserva los datos)
	docker compose down
docker-limpiar:  ## Detiene y borra el volumen de datos
	docker compose down -v
