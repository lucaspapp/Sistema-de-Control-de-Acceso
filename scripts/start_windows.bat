@echo off
setlocal
cd /d "%~dp0.."

set "DETECT_PY=analisis-caras\venv\Scripts\python.exe"
set "SYSTEM_PY=analisis-caras\.venv\Scripts\python.exe"

if not exist "%DETECT_PY%" set "DETECT_PY=.venv-detect\Scripts\python.exe"
if not exist "%SYSTEM_PY%" set "SYSTEM_PY=.venv-system\Scripts\python.exe"

if not exist "%DETECT_PY%" (
  echo No se encontro el entorno de DETECT.
  echo Usa analisis-caras\venv o crea .venv-detect con Python 3.11.
  exit /b 1
)

if not exist "%SYSTEM_PY%" (
  echo No se encontro el entorno de SISTEMA.
  echo Usa analisis-caras\.venv o crea .venv-system con las dependencias de requirements.txt.
  exit /b 1
)

start "DETECT" cmd /k ""%DETECT_PY%" src\access_control\detect.py"
timeout /t 3 /nobreak >nul
start "SISTEMA" cmd /k ""%SYSTEM_PY%" src\access_control\sistema.py"
timeout /t 3 /nobreak >nul
start "DASHBOARD" cmd /k ""%SYSTEM_PY%" src\access_control\dashboard.py"
