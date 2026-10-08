"""
LingoVibe v2 — audio_engine/gemini_client.py
Cliente Gemini API (migrado y refactorizado desde backend_service.py v1).
Actúa como fallback cloud cuando Ollama no está disponible.
"""

from __future__ import annotations

import asyncio
import json
import os
import time
import urllib.error
import urllib.request
from typing import List, Dict, Any, Optional, Tuple

GEMINI_API_KEY   = os.environ.get("GEMINI_API_KEY", "")
GEMINI_MODEL     = os.environ.get("GEMINI_MODEL", "gemini-1.5-flash")
GEMINI_BASE_URL  = "https://generativelanguage.googleapis.com/v1beta/models"


def _get_api_key() -> str:
    key = (
        os.environ.get("GEMINI_API_KEY") or
        os.environ.get("API_KEY") or
        os.environ.get("GOOGLE_API_KEY") or ""
    ).strip()
    return key


# ─────────────────────────────────────────────────────────────
#  Core REST call
# ─────────────────────────────────────────────────────────────

def _sync_call(
    system_instruction: str,
    user_message: str,
    api_key: str,
    audio_b64: Optional[str] = None,
    mime_type: str = "audio/webm",
    max_tokens: int = 400,
    temperature: float = 0.7,
) -> str:
    """Llamada síncrona al endpoint REST de Gemini (ejecutada en thread pool)."""
    parts: List[Dict[str, Any]] = []

    if audio_b64:
        parts.append({"inline_data": {"mime_type": mime_type, "data": audio_b64}})
        parts.append({"text": (
            "Listen carefully to the audio. Reply as LingoVibe tutor and "
            "identify grammar/vocabulary errors following the output format."
        )})
    else:
        parts.append({"text": user_message})

    url = f"{GEMINI_BASE_URL}/{GEMINI_MODEL}:generateContent?key={api_key}"
    payload = json.dumps({
        "system_instruction": {"parts": [{"text": system_instruction}]},
        "contents": [{"role": "user", "parts": parts}],
        "generationConfig": {
            "temperature": temperature,
            "maxOutputTokens": max_tokens,
        },
    }).encode("utf-8")

    req = urllib.request.Request(
        url, data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    try:
        with urllib.request.urlopen(req, timeout=25) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8") if exc.fp else ""
        raise RuntimeError(f"Gemini HTTP {exc.code}: {body}")
    except urllib.error.URLError as exc:
        raise RuntimeError(f"Gemini network error: {exc.reason}")

    candidates = data.get("candidates", [])
    if candidates:
        raw = candidates[0].get("content", {}).get("parts", [{}])[0].get("text", "").strip()
        return raw
    raise RuntimeError("Gemini returned empty candidates (possibly blocked).")


# ─────────────────────────────────────────────────────────────
#  API pública (async)
# ─────────────────────────────────────────────────────────────

async def generate(
    system_prompt: str,
    user_message: str,
    audio_b64: Optional[str] = None,
    mime_type: str = "audio/webm",
    max_tokens: int = 400,
    temperature: float = 0.7,
) -> Tuple[str, float]:
    """
    Genera una respuesta usando Gemini API.

    Returns:
        Tuple[str, float]: (texto_generado, latencia_en_segundos)
    """
    api_key = _get_api_key()
    if not api_key:
        raise ValueError("GEMINI_API_KEY no configurado en .env o variables de entorno.")

    t0 = time.perf_counter()
    text = await asyncio.to_thread(
        _sync_call,
        system_prompt, user_message, api_key,
        audio_b64, mime_type, max_tokens, temperature,
    )
    latency = time.perf_counter() - t0

    print(f"[GEMINI] ✨ Modelo: {GEMINI_MODEL} | "
          f"Chars: {len(text)} | Latencia: {latency*1000:.0f}ms")
    return text, latency


def is_configured() -> bool:
    return bool(_get_api_key())
