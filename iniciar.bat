@echo off
setlocal
cd /d "%~dp0"

set "BOOT="
py -3 -c "import sys; raise SystemExit(0 if sys.version_info >= (3, 11) else 1)" >nul 2>&1
if not errorlevel 1 set "BOOT=py -3"
if not defined BOOT (
  python -c "import sys; raise SystemExit(0 if sys.version_info >= (3, 11) else 1)" >nul 2>&1
  if not errorlevel 1 set "BOOT=python"
)
if not defined BOOT (
  echo Necesitas Python 3.11 o mas nuevo.
  echo Descargalo en https://www.python.org/downloads/
  echo En el instalador marca "Add python.exe to PATH".
  pause
  exit /b 1
)

if not exist ".venv\Scripts\python.exe" (
  echo Creando el entorno local...
  %BOOT% -m venv .venv
  if errorlevel 1 goto fail
)

echo Instalando librerias. La primera vez usa internet. Despues ya no hace falta.
".venv\Scripts\python.exe" -m pip install -r requirements.txt
if errorlevel 1 goto fail

echo.
echo Abre http://127.0.0.1:8000
echo Para cerrar el programa, cierra esta ventana o pulsa Ctrl+C.
echo.
start "" cmd /c "timeout /t 3 /nobreak >nul & start http://127.0.0.1:8000"
".venv\Scripts\python.exe" -m uvicorn app.main:app --host 127.0.0.1 --port 8000
echo.
echo El programa se detuvo.
pause
exit /b 0

:fail
echo.
echo No se pudo preparar el programa. Revisa el mensaje de arriba.
pause
exit /b 1
