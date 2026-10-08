@echo off
cd /d "%~dp0orchestrator"

echo ============================================================
echo   LingoBeats / LingoVibe - Orquestador Web (Node.js / Express)
echo   Puerto: 3000
echo ============================================================

if not exist "node_modules" (
    echo Instalando dependencias npm...
    call npm install
)

echo.
echo [INFO] Iniciando Orquestador en http://127.0.0.1:3000 ...
node server.js

if %ERRORLEVEL% neq 0 (
    echo.
    echo [ERROR] El orquestador finalizo con error: %ERRORLEVEL%
    pause
)
