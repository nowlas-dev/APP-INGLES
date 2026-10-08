@echo off
title LingoBeats Launcher
cd /d "%~dp0"

echo ============================================================
echo   Iniciando LingoBeats / LingoVibe (Modo Local Completo)
echo ============================================================

echo [1/3] Iniciando Motor de Audio e IA (Python FastAPI en puerto 8000)...
start "LingoBeats - Audio Engine (:8000)" cmd /k "cd /d "%~dp0" && call start_audio_engine.bat"

echo [2/3] Iniciando Orquestador y Frontend (Node.js Express en puerto 3000)...
start "LingoBeats - Orquestador (:3000)" cmd /k "cd /d "%~dp0" && call start_orchestrator.bat"

echo [3/3] Esperando inicializacion de servicios (5 segundos)...
timeout /t 5 /nobreak >nul

echo Abriendo navegador en http://127.0.0.1:3000 ...
start http://127.0.0.1:3000

echo.
echo ============================================================
echo   TODO LISTO:
echo   - Frontend:      http://127.0.0.1:3000
echo   - Audio Engine:  http://127.0.0.1:8000
echo ============================================================
echo Puedes minimizar esta ventana. Para apagar los servidores, cierra
echo las ventanas de consola de Audio Engine y Orquestador.
echo.
pause
