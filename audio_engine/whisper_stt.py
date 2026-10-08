"""
LingoVibe v2 — audio_engine/whisper_stt.py
Transcripción de audio usando faster-whisper (ejecución local, sin API externa).
"""

from __future__ import annotations

import io
import os
import tempfile
import time
from typing import Tuple, Optional

# Compatibilidad defensiva con PyAV (av >= 14 no soporta metadata_errors)
try:
    import av
    _orig_av_open = av.open

    def _safe_av_open(*args, **kwargs):
        kwargs.pop("metadata_errors", None)
        return _orig_av_open(*args, **kwargs)

    av.open = _safe_av_open
except Exception:
    pass

# faster-whisper es la implementación CTranslate2 de Whisper.
# Instalación: pip install faster-whisper
try:
    from faster_whisper import WhisperModel
    _WHISPER_AVAILABLE = True
except ImportError:
    WhisperModel = None  # type: ignore[assignment,misc]
    _WHISPER_AVAILABLE = False

# ─────────────────────────────────────────────────────────────
#  Configuración
# ─────────────────────────────────────────────────────────────

WHISPER_MODEL_SIZE = os.environ.get("WHISPER_MODEL", "base")   # tiny|base|small|medium|large
WHISPER_DEVICE     = os.environ.get("WHISPER_DEVICE", "cpu")   # cpu|cuda
WHISPER_COMPUTE    = "int8" if WHISPER_DEVICE == "cpu" else "float16"

_model: "WhisperModel | None" = None  # Singleton cargado al primer uso


def _get_model() -> "WhisperModel":
    global _model
    if _model is None:
        if not _WHISPER_AVAILABLE:
            raise RuntimeError(
                "faster-whisper no está instalado. "
                "Ejecuta: pip install faster-whisper"
            )
        print(f"[WHISPER] ⏳ Cargando modelo '{WHISPER_MODEL_SIZE}' "
              f"en {WHISPER_DEVICE} ({WHISPER_COMPUTE})…")
        _model = WhisperModel(
            WHISPER_MODEL_SIZE,
            device=WHISPER_DEVICE,
            compute_type=WHISPER_COMPUTE,
        )
        print(f"[WHISPER] ✅ Modelo listo.")
    return _model


def get_model() -> "WhisperModel":
    """Exportación pública de la carga singleton del modelo para lifespan FastAPI."""
    return _get_model()


# ─────────────────────────────────────────────────────────────
#  API pública
# ─────────────────────────────────────────────────────────────

async def transcribe(audio_bytes: bytes, language: Optional[str] = None) -> Tuple[str, float]:
    """
    Transcribe audio crudo (WebM, WAV, MP3…) a texto usando Whisper directamente en memoria.
    Sin I/O en disco ni archivos temporales.

    Args:
        audio_bytes: Bytes del archivo de audio recibido.
        language: Código ISO de idioma ('en', 'es', 'fr'…). Si es None o 'auto', autodetecta.

    Returns:
        Tuple[str, float]: (texto_transcrito, latencia_en_segundos)
    """
    import asyncio

    def _run_sync() -> Tuple[str, float]:
        model = _get_model()
        t0 = time.perf_counter()

        # Buffer en memoria sin persistir en disco
        audio_stream = io.BytesIO(audio_bytes)

        target_lang = None if language in (None, "", "auto", "detect") else language
        transcript = ""
        info = None

        try:
            segments, info = model.transcribe(
                audio_stream,
                language=target_lang,
                beam_size=5,
                vad_filter=True,          # Filtra silencios con VAD
                vad_parameters=dict(min_silence_duration_ms=300),
            )
            transcript = " ".join(seg.text.strip() for seg in segments)
        except Exception as err:
            # Fallback en caso de que el stream necesite reset de puntero o reintento
            audio_stream.seek(0)
            try:
                segments, info = model.transcribe(
                    audio_stream,
                    language=target_lang,
                    beam_size=1,
                    vad_filter=False,
                )
                transcript = " ".join(seg.text.strip() for seg in segments)
            except Exception:
                raise err
        finally:
            audio_stream.close()

        latency = time.perf_counter() - t0
        detected = getattr(info, "language", target_lang or "auto")
        print(f"[WHISPER] 📝 Idioma detectado: {detected} | "
              f"Texto: {transcript[:80]!r} | "
              f"Latencia: {latency*1000:.0f}ms")
        return transcript.strip(), latency

    return await asyncio.to_thread(_run_sync)


def is_available() -> bool:
    return _WHISPER_AVAILABLE
