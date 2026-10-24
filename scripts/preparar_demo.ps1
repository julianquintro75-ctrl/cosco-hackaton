# Paso 14 · Prepara la demostracion en Windows (PowerShell). Igual que preparar_demo.sh.
# Uso: powershell -ExecutionPolicy Bypass -File scripts\preparar_demo.ps1 [-SinReplay]
param([switch]$SinReplay)
$ErrorActionPreference = "Stop"
Set-Location (Join-Path $PSScriptRoot "..")
$PY = if (Test-Path .\.venv\Scripts\python.exe) { ".\.venv\Scripts\python.exe" } else { "python" }

Write-Host "== 1/5 Datos sinteticos (semilla 7)"
& $PY seed\generate.py --sucio
Write-Host "== 2/5 Validador de calidad (debe decir 0 criticas)"
& $PY seed\validar_datos.py | Select-Object -Last 1
Write-Host "== 3/5 Estadisticas bayesianas a la fecha de la demo"
& $PY -m engine.estadisticas --as-of 2026-09-30 | Out-String | ForEach-Object { ($_ -split "`n")[0] }
if (-not $SinReplay) {
  Write-Host "== 4/5 Repeticion del tiempo (data/replay.csv)"
  & $PY scripts\replay.py | Select-Object -Last 5
} else { Write-Host "== 4/5 Repeticion del tiempo omitida" }
Write-Host "== 5/5 Arrancando API y UI"
$api = Start-Process -FilePath $PY -ArgumentList "-m","uvicorn","app.api:app","--port","8000" -PassThru -WindowStyle Hidden
Start-Sleep -Seconds 2
Write-Host "   API:      http://127.0.0.1:8000/docs"
Write-Host "   Interfaz: http://localhost:8501   (guion: docs\guion_demo.md)"
try { & $PY -m streamlit run app\ui.py --server.port 8501 } finally { Stop-Process -Id $api.Id -ErrorAction SilentlyContinue }
