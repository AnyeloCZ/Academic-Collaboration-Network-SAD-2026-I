@echo off
setlocal
cd /d "%~dp0"

set "BUNDLED_PYTHON=C:\Users\santi\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe"

if not exist "%~dp0data\custom_students.csv" (
    echo No encontre data\custom_students.csv
    echo.
    echo Copia data\custom_students_template.csv y renombralo como:
    echo data\custom_students.csv
    echo.
    echo Luego edita ese CSV con tus datos y vuelve a ejecutar este archivo.
    pause
    exit /b 1
)

if exist "%BUNDLED_PYTHON%" (
    "%BUNDLED_PYTHON%" ".\src\run_simulations.py" --students ".\data\custom_students.csv"
) else (
    echo Bundled Python was not found.
    echo Trying system Python instead...
    python ".\src\run_simulations.py" --students ".\data\custom_students.csv"
)

echo.
echo Finished using your custom data. Press any key to close this window.
pause >nul
