@echo off
setlocal

echo =====================================================
echo INICIANDO SERVIDOR DE FACTURAS (ARQUITECTURA MODULAR)
echo =====================================================
echo.

cd /d "%~dp0"

echo Directorio actual: %CD%
echo.

set "PYTHON_CMD=python"
if exist ".venv\Scripts\python.exe" (
    set "PYTHON_CMD=.venv\Scripts\python.exe"
)

echo Verificando Python...
%PYTHON_CMD% --version
if errorlevel 1 (
    echo ERROR: Python no encontrado. Verifica la instalacion o la .venv.
    pause
    exit /b 1
)

echo.
echo Ejecutando diagnostico rapido...
%PYTHON_CMD% verificar_servidor.py
if errorlevel 1 (
    echo.
    echo ERROR: El diagnostico reporto fallos.
    pause
    exit /b 1
)

echo.
echo Iniciando servidor...
echo.
echo Disponible en:
echo   http://localhost:5000
echo   http://127.0.0.1:5000
echo.
echo Presiona Ctrl+C para detener el servidor.
echo.

%PYTHON_CMD% server.py

pause
endlocal
