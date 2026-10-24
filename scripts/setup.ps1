$ErrorActionPreference = "Stop"
Set-Location (Join-Path $PSScriptRoot "..")
python -m venv .venv
& .\.venv\Scripts\python.exe -m pip install -q -U pip
& .\.venv\Scripts\pip.exe install -r requirements.txt
& .\.venv\Scripts\python.exe seed\generate.py --sucio
try { & .\.venv\Scripts\python.exe seed\validar_datos.py } catch { }
& .\.venv\Scripts\python.exe scripts\verificar_entorno.py
Write-Host "Siguiente: .\.venv\Scripts\Activate.ps1 ; claude"
