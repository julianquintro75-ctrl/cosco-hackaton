"""Verifica que el computador tiene todo lo necesario. Uso: python scripts/verificar_entorno.py"""
import importlib, sys, sqlite3, platform
print(f"Python {sys.version.split()[0]} en {platform.system()} {platform.machine()}")
if sys.version_info < (3, 10): print("!! Se recomienda Python 3.10 o superior")
ok = True
for m in ["numpy", "pandas", "scipy", "pydantic", "fastapi", "uvicorn", "streamlit", "plotly", "catboost", "lightgbm", "sklearn", "shap"]:
    try:
        mod = importlib.import_module(m); print(f"  OK   {m:10s} {getattr(mod, '__version__', '')}")
    except Exception as e:
        ok = False; print(f"  FALTA {m:10s} -> {type(e).__name__}")
print("SQLite", sqlite3.sqlite_version)
print("\nTodo listo." if ok else "\nInstala lo que falta: pip install -r requirements.txt")
sys.exit(0 if ok else 1)
