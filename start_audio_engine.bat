@echo off
cd /d "%~dp0"
set "PYTHONUTF8=1"
set "PYTHONIOENCODING=utf-8"
set "FOR_DISABLE_CONSOLE_CTRL_HANDLER=1"

echo ============================================================
echo   LingoBeats / LingoVibe - Motor de Audio e IA (FastAPI)
echo   Puerto: 8000
echo ============================================================

REM Verificar dependencias criticas
python -c "import fastapi, uvicorn, faster_whisper, aiosqlite, multipart" >nul 2>&1
if %ERRORLEVEL% neq 0 (
    echo Instalando / verificando dependencias requeridas...
    pip install faster-whisper ollama httpx edge-tts aiosqlite fastapi uvicorn python-dotenv python-multipart
)

echo.
echo [INFO] Iniciando Audio Engine en http://127.0.0.1:8000 ...
python -m uvicorn audio_engine.main:app --host 127.0.0.1 --port 8000

if %ERRORLEVEL% neq 0 (
    echo.
    echo [ERROR] El servidor finalizo con error: %ERRORLEVEL%
    pause
)
