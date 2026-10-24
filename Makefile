.PHONY: web-instalar web web-test web-build reentrenar help instalar datos test api ui demo docker docker-bajar docker-limpiar lint
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
	ruff check .
reentrenar:      ## Reentrena M1/M2 una vez (publica solo si mejora a bayes)
	$(PY) scripts/reentrenar.py
api:             ## API en http://localhost:8000/docs
	uvicorn app.api:app --reload
ui:              ## Interfaz en http://localhost:8501
	streamlit run app/ui.py
demo:            ## Prepara y arranca la demo completa (Linux/Mac)
	bash scripts/preparar_demo.sh
docker:          ## Todo en contenedores: API + UI
	docker compose up --build
docker-bajar:    ## Detiene los contenedores (conserva los datos)
	docker compose down
docker-limpiar:  ## Detiene y borra el volumen de datos
	docker compose down -v
web-instalar:    ## Instala el frontend Angular (Node >= 22.12)
	cd web && npm install --legacy-peer-deps
web:             ## Frontend en http://localhost:4200 (la API debe estar en :8000)
	cd web && npm start
web-test:        ## Pruebas del frontend
	cd web && npm test
web-build:       ## Compila el frontend para producción
	cd web && npm run build
