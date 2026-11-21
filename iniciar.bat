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
set "LOCALPY=%LOCALAPPDATA%\Programs\Python\Python311\python.exe"
if not defined BOOT if exist "%LOCALPY%" (
  "%LOCALPY%" -c "import sys; raise SystemExit(0 if sys.version_info >= (3, 11) else 1)" >nul 2>&1
  if not errorlevel 1 set "BOOT=%LOCALPY%"
)
if not defined BOOT (
  echo No encontre Python. Lo voy a descargar e instalar solo para este usuario.
  powershell -NoProfile -Command "Invoke-WebRequest -Uri https://www.python.org/ftp/python/3.11.9/python-3.11.9-amd64.exe -OutFile $env:TEMP\python-3.11.9-amd64.exe"
  if errorlevel 1 goto fail
  "%TEMP%\python-3.11.9-amd64.exe" /quiet InstallAllUsers=0 PrependPath=1 Include_launcher=1 Include_test=0
  if exist "%LOCALPY%" set "BOOT=%LOCALPY%"
)

if not exist ".venv\Scripts\python.exe" (
  echo Creando el entorno local...
  if "%BOOT%"=="py -3" (
    py -3 -m venv .venv
  ) else if "%BOOT%"=="python" (
    python -m venv .venv
  ) else (
    "%BOOT%" -m venv .venv
  )
  if errorlevel 1 goto fail
)

echo Instalando librerias. La primera vez usa internet. Despues ya no hace falta.
".venv\Scripts\python.exe" -m pip install -r requirements.txt
if errorlevel 1 goto fail

rem Acceso directo con el logo en el escritorio, solo la primera vez.
powershell -NoProfile -Command "$d=[Environment]::GetFolderPath('Desktop'); $l=Join-Path $d 'Hojas en papel.lnk'; if (-not (Test-Path $l)) { $s=(New-Object -ComObject WScript.Shell).CreateShortcut($l); $s.TargetPath='%~dp0iniciar.bat'; $s.WorkingDirectory='%~dp0'; $s.IconLocation='%~dp0app\static\logo.ico'; $s.Save(); Write-Host 'Puse un acceso directo en el escritorio.' }" 2>nul

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
