@echo off
setlocal
cd /d "%~dp0"

set "BUNDLED_PYTHON=C:\Users\santi\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe"

if exist "%BUNDLED_PYTHON%" (
    "%BUNDLED_PYTHON%" ".\src\run_simulations.py"
) else (
    echo Bundled Python was not found.
    echo Trying system Python instead...
    python ".\src\run_simulations.py"
)

echo.
echo Finished. Press any key to close this window.
pause >nul
