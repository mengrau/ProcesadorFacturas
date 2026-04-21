@echo off
echo ========================================
echo INICIANDO SERVIDOR DE FACTURAS
echo ========================================
echo.

cd /d "%~dp0"
cd ..

echo Directorio actual: %CD%
echo.

echo Verificando Python...
python --version
if errorlevel 1 (
    echo ERROR: Python no encontrado. Verifica que Python este instalado y en el PATH.
    pause
    exit /b 1
)

echo.
echo Iniciando servidor...
echo.
echo El servidor estara disponible en:
echo   http://localhost:5000
echo   http://127.0.0.1:5000
echo.
echo Para FactuVal (cargar facturas):
echo   http://localhost:5000/facturas
echo.
echo Presiona Ctrl+C para detener el servidor
echo.

python Facturas\server.py

pause
