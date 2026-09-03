@echo off
setlocal
cd /d "%~dp0.."

set "SYSTEM_PY=analisis-caras\.venv\Scripts\python.exe"

if not exist "%SYSTEM_PY%" set "SYSTEM_PY=.venv-system\Scripts\python.exe"

if not exist "%SYSTEM_PY%" (
  echo No se encontro el entorno de SISTEMA.
  echo Usa analisis-caras\.venv o crea .venv-system con las dependencias de requirements.txt.
  exit /b 1
)

start "SISTEMA" cmd /k ""%SYSTEM_PY%" src\access_control\sistema.py"
timeout /t 3 /nobreak >nul
start "GOLDENJACK WEB" cmd /k ""%SYSTEM_PY%" src\access_control\webapp.py"
