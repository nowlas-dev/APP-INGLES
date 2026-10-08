"""
LingoVibe v2 — audio_engine/tts_engine.py
Motor de síntesis de voz (TTS).
Usa edge-tts (Microsoft Edge TTS, gratuito, alta calidad) con fallback a pyttsx3.
"""

from __future__ import annotations

import asyncio
import io
import os
from typing import Optional

# ─────────────────────────────────────────────────────────────
#  Backends disponibles
# ─────────────────────────────────────────────────────────────

try:
    import edge_tts  # pip install edge-tts
    _EDGE_TTS_AVAILABLE = True
except ImportError:
    _EDGE_TTS_AVAILABLE = False

try:
    import pyttsx3  # pip install pyttsx3
    _PYTTSX3_AVAILABLE = True
except ImportError:
    _PYTTSX3_AVAILABLE = False


# ─────────────────────────────────────────────────────────────
#  Configuración de voces (edge-tts)
#  Lista completa: edge-tts --list-voices
# ─────────────────────────────────────────────────────────────

VOICE_MAP: dict[str, str] = {
    "en-US": "en-US-AriaNeural",
    "en-GB": "en-GB-SoniaNeural",
    "es-ES": "es-ES-ElviraNeural",
    "es-MX": "es-MX-DaliaNeural",
    "fr-FR": "fr-FR-DeniseNeural",
    "de-DE": "de-DE-KatjaNeural",
    "it-IT": "it-IT-ElsaNeural",
    "pt-BR": "pt-BR-FranciscaNeural",
    "ja-JP": "ja-JP-NanamiNeural",
    "zh-CN": "zh-CN-XiaoxiaoNeural",
}

DEFAULT_VOICE = os.environ.get("TTS_VOICE", "en-US-AriaNeural")
TTS_RATE      = os.environ.get("TTS_RATE", "+0%")    # e.g. "-10%" para más lento
TTS_VOLUME    = os.environ.get("TTS_VOLUME", "+0%")


# ─────────────────────────────────────────────────────────────
#  API pública
# ─────────────────────────────────────────────────────────────

async def synthesize(
    text: str,
    target_lang: str = "en-US",
    voice: Optional[str] = None,
    rate: Optional[str] = None,
) -> bytes:
    """
    Sintetiza texto a audio MP3 y devuelve los bytes.

    Args:
        text:        Texto a sintetizar.
        target_lang: Código de idioma para seleccionar la voz automáticamente.
        voice:       Nombre exacto de la voz (anula target_lang si se provee).
        rate:        Velocidad de habla, e.g. "-15%" (más lento), "+10%" (más rápido).

    Returns:
        bytes: Audio en formato MP3.

    Raises:
        RuntimeError: Si ningún backend TTS está disponible.
    """
    if _EDGE_TTS_AVAILABLE:
        return await _synthesize_edge(text, target_lang, voice, rate)
    if _PYTTSX3_AVAILABLE:
        return await asyncio.to_thread(_synthesize_pyttsx3, text)
    raise RuntimeError(
        "No hay backend TTS disponible. "
        "Instala: pip install edge-tts  o  pip install pyttsx3"
    )


async def _synthesize_edge(
    text: str,
    target_lang: str,
    voice: Optional[str],
    rate: Optional[str],
) -> bytes:
    """Síntesis con edge-tts → MP3 bytes."""
    selected_voice = voice or VOICE_MAP.get(target_lang, DEFAULT_VOICE)
    selected_rate  = rate or TTS_RATE

    communicate = edge_tts.Communicate(
        text=text,
        voice=selected_voice,
        rate=selected_rate,
        volume=TTS_VOLUME,
    )

    audio_buffer = io.BytesIO()
    async for chunk in communicate.stream():
        if chunk["type"] == "audio":
            audio_buffer.write(chunk["data"])

    audio_bytes = audio_buffer.getvalue()
    print(f"[TTS] 🔊 edge-tts | Voz: {selected_voice} | "
          f"Bytes: {len(audio_bytes):,}")
    return audio_bytes


def _synthesize_pyttsx3(text: str) -> bytes:
    """Fallback pyttsx3 → WAV bytes (menor calidad, sin red)."""
    import tempfile
    engine = pyttsx3.init()
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
        tmp_path = tmp.name
    try:
        engine.save_to_file(text, tmp_path)
        engine.runAndWait()
        with open(tmp_path, "rb") as f:
            audio_bytes = f.read()
    finally:
        os.unlink(tmp_path)

    print(f"[TTS] 🔊 pyttsx3 fallback | Bytes: {len(audio_bytes):,}")
    return audio_bytes


def get_available_backend() -> str:
    if _EDGE_TTS_AVAILABLE:
        return "edge-tts"
    if _PYTTSX3_AVAILABLE:
        return "pyttsx3"
    return "none"
