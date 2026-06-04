@echo off
setlocal
cd /d "%~dp0"
if not exist "data\custom_students.csv" (
  echo No encontre data\custom_students.csv
  echo Copia data\custom_students_template.csv y renombralo como data\custom_students.csv
  pause
  exit /b 1
)
python src\run_simulations.py --students data\custom_students.csv
pause
