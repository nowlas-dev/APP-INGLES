@echo off
title LingoBeats - Detener Servidores
cd /d "%~dp0"

echo ============================================================
echo   Deteniendo servidores de LingoBeats
echo ============================================================

for /f "tokens=5" %%a in ('netstat -aon ^| findstr /r /c:":8000 .*LISTENING"') do (
    echo Cerrando Audio Engine PID %%a
    taskkill /F /PID %%a >nul 2>&1
)

for /f "tokens=5" %%a in ('netstat -aon ^| findstr /r /c:":3000 .*LISTENING"') do (
    echo Cerrando Orquestador PID %%a
    taskkill /F /PID %%a >nul 2>&1
)

echo [OK] Puertos 8000 y 3000 liberados.
