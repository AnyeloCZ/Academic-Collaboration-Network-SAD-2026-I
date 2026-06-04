@echo off
setlocal
cd /d "%~dp0"

python src\run_simulations.py --ignore-custom

if exist "docs\dashboard.html" (
  start "" "%~dp0docs\dashboard.html"
) else (
  echo No se encontro docs\dashboard.html
)

pause
