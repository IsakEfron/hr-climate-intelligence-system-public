@echo off
REM Script de inicio rápido para Canels - Windows
REM Activa el entorno virtual y ejecuta la aplicación

cls
echo.
echo ============================================================
echo          CANELS - Sistema de Encuestas
echo     Iniciando servidor de desarrollo...
echo ============================================================
echo.

REM Verificar que existe el entorno virtual
if not exist "venv\" (
    echo Error: Entorno virtual no encontrado
    echo.
    echo Ejecuta primero: python setup.py
    echo.
    pause
    exit /b 1
)

REM Verificar que .env existe
if not exist ".env" (
    echo Error: Archivo .env no encontrado
    echo.
    echo Ejecuta primero: python setup.py
    echo.
    pause
    exit /b 1
)

REM Activar entorno virtual
echo Activando entorno virtual...
call venv\Scripts\activate.bat

REM Verificar que la activación fue exitosa
if errorlevel 1 (
    echo Error al activar el entorno virtual
    pause
    exit /b 1
)

echo.
echo Iniciando servidor...
echo.
echo URL Local:     http://localhost:5000
echo Red Local:     http://^<tu-ip^>:5000
echo.
echo Para obtener tu IP: ipconfig
echo Para detener: Presiona Ctrl+C
echo.

python app.py

pause
