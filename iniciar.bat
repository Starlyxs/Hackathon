@echo off
setlocal EnableExtensions
title Hojas en papel
cd /d "%~dp0programa"
if errorlevel 1 (
  echo No encuentro la carpeta "programa". Tiene que estar junto a este archivo.
  goto fail
)

echo.
echo  Hojas en papel
echo  ---------------
echo.

set "BOOT="
call :buscar_python

if not defined BOOT (
  echo No encontre Python 3.11, 3.12 ni 3.13. Lo voy a instalar solo para este usuario.
  echo Necesita internet y tarda unos minutos. No hay que hacer nada.
  echo.
  powershell -NoProfile -Command "[Net.ServicePointManager]::SecurityProtocol=[Net.SecurityProtocolType]::Tls12; Invoke-WebRequest -UseBasicParsing -Uri https://www.python.org/ftp/python/3.11.9/python-3.11.9-amd64.exe -OutFile $env:TEMP\python-3.11.9-amd64.exe"
  if errorlevel 1 goto sin_internet
  if not exist "%TEMP%\python-3.11.9-amd64.exe" goto sin_internet
  "%TEMP%\python-3.11.9-amd64.exe" /quiet InstallAllUsers=0 PrependPath=1 Include_launcher=1 Include_test=0
  call :buscar_python
  if not defined BOOT goto sin_python
)

rem Fuera de OneDrive y fuera de AppData (el Python de la Microsoft Store redirige AppData y rompe el entorno).
set "VENV=%USERPROFILE%\.hojas-en-papel\venv"
set "VPY=%VENV%\Scripts\python.exe"

rem Si copiaron la carpeta desde otra computadora o se desinstalo Python, el entorno se rehace solo.
if exist "%VPY%" (
  "%VPY%" -c "import sys" >nul 2>&1
  if errorlevel 1 rmdir /s /q "%VENV%"
)
if not exist "%VPY%" (
  echo Preparando el programa por primera vez...
  %BOOT% -m venv "%VENV%"
  if errorlevel 1 goto fail
)

"%VPY%" preparar.py
if errorlevel 1 goto fail

rem Acceso directo con el logo en el escritorio, solo la primera vez.
powershell -NoProfile -Command "$d=[Environment]::GetFolderPath('Desktop'); $l=Join-Path $d 'Hojas en papel.lnk'; if (-not (Test-Path $l)) { $s=(New-Object -ComObject WScript.Shell).CreateShortcut($l); $s.TargetPath='%~dp0iniciar.bat'; $s.WorkingDirectory='%~dp0'; $s.IconLocation='%~dp0programa\app\static\logo.ico'; $s.Save(); Write-Host 'Puse un acceso directo en el escritorio.' }" 2>nul

"%VPY%" run.py
echo.
echo El programa se detuvo. Para volver a abrirlo, haz doble clic en iniciar.bat.
pause
exit /b 0

:buscar_python
for %%V in (3.11 3.12 3.13) do (
  if not defined BOOT (
    py -%%V -c "import sys" >nul 2>&1
    if not errorlevel 1 set "BOOT=py -%%V"
  )
)
if not defined BOOT (
  python -c "import sys; raise SystemExit(0 if (3,11)<=sys.version_info[:2]<=(3,13) else 1)" >nul 2>&1
  if not errorlevel 1 set "BOOT=python"
)
if not defined BOOT (
  for %%P in ("%LOCALAPPDATA%\Programs\Python\Python311\python.exe" "%LOCALAPPDATA%\Programs\Python\Python312\python.exe" "%LOCALAPPDATA%\Programs\Python\Python313\python.exe") do (
    if not defined BOOT if exist %%P set BOOT=%%P
  )
)
exit /b 0

:sin_internet
echo.
echo No pude descargar Python. Revisa que la computadora tenga internet.
echo Tambien puedes instalarlo a mano desde https://www.python.org/downloads/
echo (version 3.11, 3.12 o 3.13, marcando la casilla "Add python.exe to PATH")
echo y luego volver a abrir este archivo.
goto fail

:sin_python
echo.
echo Python no se termino de instalar. Instalalo a mano desde https://www.python.org/downloads/
echo (version 3.11, 3.12 o 3.13, marcando la casilla "Add python.exe to PATH")
echo y luego vuelve a abrir este archivo.
goto fail

:fail
echo.
echo No se pudo abrir el programa. Lee el mensaje de arriba y la seccion "Si algo falla" del README.
pause
exit /b 1
