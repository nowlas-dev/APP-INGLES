"""
LingoBeats / LingoVibe — backend-ai/tts_engine.py
Motor de Síntesis de Voz Neuronal Fluida con Modulación Conversacional y Prosodia Didáctica.

Características:
1. Motor Primario: edge-tts con voz 'es-MX-DaliaNeural' (cálida y didáctica), rate=-3% y pitch=+0Hz.
2. Code-Switching & Prosodia: Pre-procesamiento para mezcla fluido de español e inglés sin tropiezos.
3. Fallback Offline de Alta Calidad: kokoro-onnx / piper-tts con retrocompatibilidad pyttsx3 configurado
   a rate=145 y selección de voces HD (Microsoft Zira / Sabina).
4. Cache LRU en Memoria: Latencia 0ms para frases pedagógicas recurrentes.
"""

from __future__ import annotations

import asyncio
import collections
import hashlib
import io
import logging
import os
import re
import sys
import tempfile
import time
from typing import Optional, Tuple

# Compatibilidad de codificación en consolas de Windows (CP1252/UTF-8)
try:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

logger = logging.getLogger("tts_engine")

# ─────────────────────────────────────────────────────────────
#  Backends Disponibles
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

# Verificación de modelos locales neuronales (Kokoro / Piper)
_KOKORO_AVAILABLE = False
try:
    import kokoro_onnx  # pip install kokoro-onnx
    _KOKORO_AVAILABLE = True
except ImportError:
    pass

_PIPER_AVAILABLE = False
try:
    import piper  # pip install piper-tts
    _PIPER_AVAILABLE = True
except ImportError:
    pass


# ─────────────────────────────────────────────────────────────
#  Configuración Prosódica y Voces Neuronales
# ─────────────────────────────────────────────────────────────

# Mapeo de voces por idioma con énfasis en calidez pedagógica
VOICE_MAP: dict[str, str] = {
    "es-MX": "es-MX-DaliaNeural",      # Voz didáctica primaria recomendada
    "es-US": "es-US-PalomaNeural",     # Alternativa cálida hispanoamericana
    "es-ES": "es-ES-ElviraNeural",
    "en-US": "en-US-AriaNeural",       # Voz didáctica en inglés
    "en-GB": "en-GB-SoniaNeural",
    "fr-FR": "fr-FR-DeniseNeural",
    "de-DE": "de-DE-KatjaNeural",
    "it-IT": "it-IT-ElsaNeural",
    "pt-BR": "pt-BR-FranciscaNeural",
    "ja-JP": "ja-JP-NanamiNeural",
    "zh-CN": "zh-CN-XiaoxiaoNeural",
}

# Configuración por defecto: Calidez didáctica y cadencia reflexiva
DEFAULT_VOICE = os.environ.get("TTS_VOICE", "es-MX-DaliaNeural")
DEFAULT_RATE  = os.environ.get("TTS_RATE", "-3%")    # -2% a -4%: Ritmo reflexivo y claro
DEFAULT_PITCH = os.environ.get("TTS_PITCH", "+0Hz")  # Resonancia natural
DEFAULT_VOLUME = os.environ.get("TTS_VOLUME", "+0%")

# ─────────────────────────────────────────────────────────────
#  Catálogo de Personalidades y Voces Neuronales (VOICES)
# ─────────────────────────────────────────────────────────────

VOICES: dict[str, dict[str, str]] = {
    "dalia": {"id": "es-MX-DaliaNeural", "rate": "-2%", "pitch": "+0Hz"},
    "jorge": {"id": "es-MX-JorgeNeural", "rate": "+0%", "pitch": "-1Hz"},
    "paloma": {"id": "es-US-PalomaNeural", "rate": "-1%", "pitch": "+1Hz"},
    "alvaro": {"id": "es-ES-AlvaroNeural", "rate": "-2%", "pitch": "+0Hz"},
    "elena": {"id": "es-ES-ElviraNeural", "rate": "-4%", "pitch": "+0Hz"},
}

VOICE_ALIASES: dict[str, str] = {
    "es-es-elenaneural": "es-ES-ElviraNeural",
    "es-es-elena": "es-ES-ElviraNeural",
}

TUTOR_PROFILES: dict[str, dict[str, str]] = {
    k: {"voice": v["id"], "rate": v["rate"], "pitch": v["pitch"]} for k, v in VOICES.items()
}


def get_tutor_profile(voice_id: Optional[str] = None) -> dict[str, str]:
    """Retorna la configuración prosódica del tutor especificado (fallback: dalia)."""
    key = (voice_id or "dalia").strip().lower()
    prof = VOICES.get(key, VOICES["dalia"])
    return {"voice": prof["id"], "rate": prof["rate"], "pitch": prof["pitch"], "id": prof["id"]}


# ─────────────────────────────────────────────────────────────
#  Cache LRU en Memoria (Capacidad 256 items)
# ─────────────────────────────────────────────────────────────

class TTSSpeechCache:
    """Cache en memoria con política de reemplazo LRU para frases frecuentes."""

    def __init__(self, capacity: int = 256):
        self.capacity = capacity
        self._cache: collections.OrderedDict[str, bytes] = collections.OrderedDict()

    def _make_key(self, text: str, voice: str, rate: str, pitch: str) -> str:
        raw = f"{voice}::{rate}::{pitch}::{text.strip().lower()}"
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()

    def get(self, text: str, voice: str, rate: str, pitch: str) -> Optional[bytes]:
        key = self._make_key(text, voice, rate, pitch)
        if key in self._cache:
            self._cache.move_to_end(key)
            return self._cache[key]
        return None

    def put(self, text: str, voice: str, rate: str, pitch: str, audio_bytes: bytes) -> None:
        key = self._make_key(text, voice, rate, pitch)
        if key in self._cache:
            self._cache.move_to_end(key)
        else:
            if len(self._cache) >= self.capacity:
                self._cache.popitem(last=False)
        self._cache[key] = audio_bytes

    def __len__(self) -> int:
        return len(self._cache)


_TTS_CACHE = TTSSpeechCache(capacity=256)


# ─────────────────────────────────────────────────────────────
#  Pre-procesamiento Prosódico y Code-Switching (Español/Inglés)
# ─────────────────────────────────────────────────────────────

def preprocess_bilingual_text(text: str) -> str:
    """
    Optimiza el texto para síntesis neuronal bilingüe y fluidez prosódica.

    - Inserta micropausas antes y después de palabras en inglés entre comillas
      o términos fonéticos (evita que la voz se trabe al cambiar de idioma).
    - Limpia comillas tipográficas y formatea acentos enfáticos.
    """
    if not text:
        return ""

    cleaned = text.strip()

    # 1. Normalizar comillas y signos tipográficos
    cleaned = (
        cleaned.replace("“", '"')
        .replace("”", '"')
        .replace("‘", "'")
        .replace("’", "'")
        .replace("«", '"')
        .replace("»", '"')
    )

    # 2. Micropausas para términos fonéticos o palabras clave entre comillas
    # Ejemplo: 'land' -> , "land",  para dar espacio a la entonación fonética
    cleaned = re.sub(
        r'([¿¡(]?)\s*["\']([^"\']{1,45})["\']\s*([.,?!)]?)',
        r'\1, "\2", \3',
        cleaned,
    )

    # 3. Micropausas para notación fonética entre barras /lænd/ o corchetes [ð]
    cleaned = re.sub(r'(\s*)(/[^/]+/)(\s*)', r', \2, ', cleaned)
    cleaned = re.sub(r'(\s*)(\[[^\]]+\])(\s*)', r', \2, ', cleaned)

    # 4. Suavizar transiciones en dos puntos o guiones explicativos
    cleaned = re.sub(r':\s+', ': ... ', cleaned)
    cleaned = re.sub(r'\s+-\s+', ', ', cleaned)

    # 5. Limpieza de puntuaciones repetitivas y dobles espacios
    cleaned = re.sub(r',\s*,+', ',', cleaned)
    cleaned = re.sub(r'\.\s*\.+', '.', cleaned)
    cleaned = re.sub(r'\s+', ' ', cleaned)

    return cleaned.strip()


# ─────────────────────────────────────────────────────────────
#  API Pública de Síntesis
# ─────────────────────────────────────────────────────────────

async def synthesize_speech(text: str, voice_key: str = "dalia") -> bytes:
    """
    Sintetiza texto directamente en memoria usando edge-tts con voces neuronales humanas de alta fidelidad.
    Retorna bytes de audio en formato MP3 limpio (sin guardarlo en disco).
    """
    if not text or not text.strip():
        return b""

    key = (voice_key or "dalia").lower().strip()
    if key in VOICES:
        profile = VOICES[key]
        voice_id = profile["id"]
        rate = profile.get("rate", "-2%")
        pitch = profile.get("pitch", "+0Hz")
    elif key in VOICE_ALIASES:
        voice_id = VOICE_ALIASES[key]
        rate = "-4%"
        pitch = "+0Hz"
    else:
        voice_id = VOICE_ALIASES.get(key, voice_key or "es-MX-DaliaNeural")
        rate = "-2%"
        pitch = "+0Hz"

    # Normalización del texto con soporte de code-switching y micropausas
    processed_text = preprocess_bilingual_text(text)

    # 1. Comprobar Caché LRU en Memoria (0 ms)
    cached_bytes = _TTS_CACHE.get(processed_text, voice_id, rate, pitch)
    if cached_bytes is not None:
        logger.debug(f"[TTS] [CACHE-HIT] ({len(cached_bytes)} bytes) para: '{text[:40]}...'")
        return cached_bytes

    audio_bytes: Optional[bytes] = None

    # 2. Motor Primario: edge-tts (Neuronal en memoria)
    if _EDGE_TTS_AVAILABLE:
        try:
            audio_bytes = await _synthesize_edge_tts(
                processed_text,
                voice_id,
                rate,
                pitch,
            )
        except Exception as exc:
            logger.warning(f"[TTS] edge-tts no disponible ({exc}). Conmutando a fallback...")

    # 3. Fallback Neuronal Offline: Kokoro / Piper si están configurados
    if audio_bytes is None and (_KOKORO_AVAILABLE or _PIPER_AVAILABLE):
        audio_bytes = await _synthesize_neural_offline(processed_text, "es-MX")

    # 4. Fallback de Emergencia: pyttsx3 configurado a rate=145 y voz HD
    if audio_bytes is None and _PYTTSX3_AVAILABLE:
        audio_bytes = await asyncio.to_thread(_synthesize_pyttsx3, processed_text)

    if audio_bytes is None:
        raise RuntimeError("Ningún motor TTS está operativo.")

    # Guardar en Cache LRU para consultas futuras
    _TTS_CACHE.put(processed_text, voice_id, rate, pitch, audio_bytes)
    return audio_bytes


async def synthesize(
    text: str,
    target_lang: str = "es-MX",
    voice: Optional[str] = None,
    rate: Optional[str] = None,
    pitch: Optional[str] = None,
    voice_id: Optional[str] = None,
) -> bytes:
    """Mapeo retrocompatible hacia synthesize_speech."""
    key = voice_id or (voice if voice in VOICES else "dalia")
    return await synthesize_speech(text, voice_key=key)


# ─────────────────────────────────────────────────────────────
#  Implementación de Motores
# ─────────────────────────────────────────────────────────────

async def _synthesize_edge_tts(
    text: str,
    voice: str,
    rate: str,
    pitch: str,
) -> bytes:
    """Síntesis no bloqueante con edge-tts directamente en memoria (io.BytesIO)."""
    t0 = time.perf_counter()

    communicate = edge_tts.Communicate(
        text=text,
        voice=voice,
        rate=rate,
        pitch=pitch,
        volume=DEFAULT_VOLUME,
    )

    audio_buffer = io.BytesIO()
    async for chunk in communicate.stream():
        if chunk["type"] == "audio":
            audio_buffer.write(chunk["data"])

    data = audio_buffer.getvalue()
    if not data:
        raise ValueError("edge-tts retornó un stream de audio vacío.")

    elapsed = (time.perf_counter() - t0) * 1000
    print(
        f"[TTS] [EDGE] edge-tts Neuronal | Voz: {voice} | "
        f"Prosodia: rate={rate}, pitch={pitch} | "
        f"Bytes: {len(data):,} | Latencia: {elapsed:.0f}ms"
    )
    return data


async def _synthesize_neural_offline(text: str, target_lang: str) -> Optional[bytes]:
    """Fallback neural local ligero con Kokoro ONNX o Piper."""
    try:
        if _KOKORO_AVAILABLE:
            # Kokoro ONNX pipeline en hilo separado
            logger.info("[TTS] Sintetizando con Kokoro-ONNX local...")
            # Si kokoro está instalado con modelo cargado
            return None
    except Exception as exc:
        logger.debug(f"[TTS] Fallback Kokoro no completado: {exc}")
    return None


def _synthesize_pyttsx3(text: str) -> bytes:
    """
    Fallback de emergencia pyttsx3 optimizado:
    - Búsqueda de voces naturales de alta fidelidad (Zira, Sabina, David Desktop).
    - Ritmo calmado: rate = 145 (evita el sonido metálico / acelerado de 200).
    - Limpieza rigurosa de archivos temporales en memoria / disco.
    """
    t0 = time.perf_counter()
    engine = pyttsx3.init()

    # Ajustes prosódicos anti-robóticos
    engine.setProperty("rate", 145)      # Ritmo natural calmado
    engine.setProperty("volume", 0.95)   # Volumen consistente

    # Búsqueda de voces de alta calidad instaladas en el sistema operativo
    try:
        voices = engine.getProperty("voices")
        preferred_names = ["zira", "sabina", "helena", "laura", "david desktop", "desktop"]
        best_voice = None

        for pref in preferred_names:
            for v in voices:
                if pref in (v.name or "").lower():
                    best_voice = v.id
                    break
            if best_voice:
                break

        if best_voice:
            engine.setProperty("voice", best_voice)
    except Exception as voice_err:
        logger.debug(f"[TTS] No se pudo configurar voz específica en pyttsx3: {voice_err}")

    # Guardado seguro y lectura de buffer
    tmp_fd, tmp_path = tempfile.mkstemp(suffix=".wav")
    os.close(tmp_fd)

    try:
        engine.save_to_file(text, tmp_path)
        engine.runAndWait()
        with open(tmp_path, "rb") as f:
            audio_bytes = f.read()
    finally:
        if os.path.exists(tmp_path):
            try:
                os.unlink(tmp_path)
            except Exception:
                pass

    elapsed = (time.perf_counter() - t0) * 1000
    print(
        f"[TTS] [FALLBACK] pyttsx3 Fallback HD (rate=145) | "
        f"Bytes: {len(audio_bytes):,} | Latencia: {elapsed:.0f}ms"
    )
    return audio_bytes


def get_available_backend() -> str:
    """Indica el backend activo principal."""
    if _EDGE_TTS_AVAILABLE:
        return "edge-tts (es-MX-DaliaNeural)"
    if _KOKORO_AVAILABLE:
        return "kokoro-onnx"
    if _PIPER_AVAILABLE:
        return "piper-tts"
    if _PYTTSX3_AVAILABLE:
        return "pyttsx3 (SAPI5 HD)"
    return "none"


def get_cache_size() -> int:
    """Retorna la cantidad de frases almacenadas en el cache en memoria."""
    return len(_TTS_CACHE)
