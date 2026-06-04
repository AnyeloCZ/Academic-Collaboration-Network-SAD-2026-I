@echo off
setlocal
cd /d "%~dp0"
python src\run_simulations.py --randomize --ignore-custom
pause
