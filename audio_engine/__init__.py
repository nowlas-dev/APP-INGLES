"""audio_engine/__init__.py — Expone submódulos del motor de audio."""
from audio_engine import whisper_stt, ollama_client, gemini_client, tts_engine

__all__ = ["whisper_stt", "ollama_client", "gemini_client", "tts_engine"]
