@echo off
cd /d "%~dp0"

if exist "docs\dashboard.html" (
  start "" "%~dp0docs\dashboard.html"
) else (
  echo No se encontro docs\dashboard.html
  echo Ejecuta primero run.bat o run_visual.bat
  pause
)
