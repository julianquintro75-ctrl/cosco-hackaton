# Pasar el proyecto al computador potente

## 1. Copiar
Copia `cosco_proyecto.zip` al otro computador (USB, nube o correo) y descomprímelo. Queda una carpeta `proyecto/`. Ábrela en la terminal (en Windows: PowerShell; en Mac/Linux: Terminal).

## 2. Instalar (una sola vez)
**Requisito:** Python 3.10 o superior. Comprueba con `python --version` (en Mac/Linux a veces es `python3`).

Mac / Linux:
```
bash scripts/setup.sh
```
Windows (PowerShell):
```
powershell -ExecutionPolicy Bypass -File scripts\setup.ps1
```
El script crea el entorno virtual `.venv`, instala las librerías, genera los datos y corre el validador. Al final debe mostrar la verificación del entorno y «0 críticas».

Para activar el entorno cada vez que abras una terminal nueva:
- Mac/Linux: `source .venv/bin/activate`
- Windows: `.venv\Scripts\Activate.ps1`

## 3. Ver los datos y reportes
```
python seed/check_story.py        # historias de los proveedores
python seed/reporte_datos.py      # abre reportes/reporte_datos.html en el navegador
```

## 4. Trabajar con Claude Code en ese computador
1. Instala Claude Code en ese computador e inicia sesión con tu cuenta (instrucciones oficiales: https://docs.claude.com/en/docs/claude-code/overview).
2. En la terminal, dentro de la carpeta `proyecto/`, con el entorno activado, escribe `claude`.
3. Claude lee automáticamente `CLAUDE.md` (contexto del proyecto, reglas y decisiones). Dile primero: «Lee CLAUDE.md y docs/enunciado_reto.txt y resúmeme el proyecto en 5 líneas». Si lo resume bien, sigue.
4. Abre `PASOS_Y_PROMPTS.md` y pega **un prompt a la vez**, empezando por el **paso 3**. No pases al siguiente hasta cumplir el «Listo cuando».
5. Al terminar cada paso pide: «Corre pytest y dime qué pasó». Si algo falla, pega el error tal cual.
6. Cuando el sistema funcione: `uvicorn app.api:app --reload` (API) y `streamlit run app/ui.py` (interfaz); los tableros salen del paso 12.

## 5. Reportes que se generan en el camino
| Paso | Reporte |
|---|---|
| Datos | `reportes/reporte_datos.html` y salida de `check_story.py` |
| 4–5 | Pruebas de estadística y de motor (pytest) |
| 9 | `data/replay.csv`: la caída de Andina Cargo en el tiempo |
| 10–11 | Tabla bayesiano vs. ML y tabla de arrepentimiento por configuración |
| 12 | Tableros en Streamlit |
| 13 | Tabla de comparación con Jev y LLM |

Pídele a Claude, al final de cada paso, que guarde su reporte en la carpeta `reportes/` en markdown o HTML.

## 6. Si algo falla
- «python no se reconoce»: instala Python desde python.org y marca «Add to PATH».
- Falla `catboost` o `lightgbm`: actualiza pip (`python -m pip install -U pip`) y reintenta; si persiste, dile a Claude que use `scikit-learn` en su lugar.
- El reporte HTML carga plotly desde internet: ábrelo con conexión.
- Cualquier otro error: pégalo completo a Claude y pídele que lo arregle antes de seguir.
