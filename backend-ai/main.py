"""
LingoBeats — backend-ai/main.py
FastAPI Motor de Audio e Inteligencia Artificial
Endpoint de saludo contextual de bienvenida con personalidad y modulación prosódica.
"""

from __future__ import annotations

import os
import sys
from typing import Optional
from urllib.parse import quote

# Asegurar rutas de importación tanto para backend-ai como para la raíz del proyecto
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
BACKEND_AI_DIR = os.path.abspath(os.path.dirname(__file__))

for p in (BASE_DIR, BACKEND_AI_DIR):
    if p not in sys.path:
        sys.path.insert(0, p)

from fastapi import Response, Query, HTTPException
from audio_engine.main import app

try:
    from app.services.tutor_agent import get_welcome_greeting
except ImportError:
    from audio_engine.services.tutor_agent import get_welcome_greeting

try:
    import tts_engine
except ImportError:
    from audio_engine import tts_engine


@app.get("/api/ai/session/welcome")
async def session_welcome(
    song: str = Query(default="Yesterday", description="Título de la canción"),
    artist: str = Query(default="", description="Nombre del artista"),
    attitude: str = Query(default="funny", description="Estilo/actitud del tutor (friendly, funny, strict)"),
    voice: str = Query(default="dalia", description="Voz del tutor (dalia, jorge, paloma, alvaro, elena)"),
):
    """
    Endpoint de bienvenida contextual:
    1. Genera el texto personalizado con get_welcome_greeting.
    2. Sintetiza a MP3 con synthesize_speech aplicando modulación prosódica según la actitud.
    3. Retorna directamente el audio streaming como audio/mpeg.
    """
    # 1. Generar texto de bienvenida con personalidad
    greeting_text = get_welcome_greeting(song_title=song, artist=artist, attitude=attitude)

    # 2. Sintetizar en memoria a MP3 con modulación prosódica
    try:
        audio_bytes = await tts_engine.synthesize_speech(
            text=greeting_text,
            voice_key=voice,
            attitude=attitude,
        )
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Error en síntesis del saludo de bienvenida: {exc}",
        )

    if not audio_bytes:
        raise HTTPException(
            status_code=500,
            detail="No se recibieron bytes de audio para el saludo de bienvenida.",
        )

    # 3. Retornar audio streaming directamente
    headers = {
        "X-Greeting-Text": quote(greeting_text),
        "X-Tutor-Attitude": attitude,
        "X-Tutor-Voice": voice,
    }

    return Response(
        content=audio_bytes,
        media_type="audio/mpeg",
        headers=headers,
    )


__all__ = ["app", "session_welcome"]
