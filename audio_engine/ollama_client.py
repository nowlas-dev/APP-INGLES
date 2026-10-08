"""
LingoVibe v2 — audio_engine/ollama_client.py
Cliente para LLM local via Ollama HTTP API.
Compatible con cualquier modelo disponible en el servidor Ollama local.
"""

from __future__ import annotations

import json
import os
import time
from typing import Optional

import httpx  # pip install httpx

OLLAMA_BASE_URL = os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434")
OLLAMA_MODEL    = os.environ.get("OLLAMA_MODEL", "llama3")
# Timeout estricto de 4.0s para evitar congelamiento de la experiencia de usuario
OLLAMA_TIMEOUT  = float(os.environ.get("OLLAMA_TIMEOUT", "4.0"))

# ─────────────────────────────────────────────────────────────
#  Health check
# ─────────────────────────────────────────────────────────────

async def health_check() -> dict:
    """Verifica que el servidor Ollama esté disponible y lista los modelos."""
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            r = await client.get(f"{OLLAMA_BASE_URL}/api/tags")
            if r.status_code == 200:
                models = [m["name"] for m in r.json().get("models", [])]
                return {"status": "ok", "models": models}
            return {"status": "error", "code": r.status_code}
    except Exception as exc:
        return {"status": "unavailable", "detail": str(exc)}


async def is_model_available(model: str = OLLAMA_MODEL) -> bool:
    info = await health_check()
    return info.get("status") == "ok" and any(
        m.startswith(model) for m in info.get("models", [])
    )


# ─────────────────────────────────────────────────────────────
#  Generación de respuesta
# ─────────────────────────────────────────────────────────────

async def generate(
    system_prompt: str,
    user_message: str,
    model: Optional[str] = None,
    temperature: float = 0.7,
    max_tokens: int = 400,
    response_format: Optional[str] = None,
) -> tuple[str, float]:
    """
    Llama al endpoint /api/chat de Ollama con timeout estricto de 4.0 segundos.

    Returns:
        Tuple[str, float]: (texto_generado, latencia_en_segundos)

    Raises:
        RuntimeError: Si Ollama excede el timeout, no está disponible o falla.
    """
    target_model = model or OLLAMA_MODEL
    t0 = time.perf_counter()

    payload = {
        "model": target_model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user",   "content": user_message},
        ],
        "stream": False,
        "options": {
            "temperature": temperature,
            "num_predict": max_tokens,
        },
    }
    if response_format:
        payload["format"] = response_format

    try:
        async with httpx.AsyncClient(timeout=OLLAMA_TIMEOUT) as client:
            r = await client.post(
                f"{OLLAMA_BASE_URL}/api/chat",
                json=payload,
            )
            r.raise_for_status()
    except (httpx.TimeoutException, TimeoutError):
        raise TimeoutError(f"Ollama timeout ({OLLAMA_TIMEOUT}s excedido en {OLLAMA_BASE_URL})")
    except httpx.ConnectError:
        raise RuntimeError(
            f"No se puede conectar a Ollama en {OLLAMA_BASE_URL}. "
            "Asegúrate de que 'ollama serve' está en ejecución."
        )
    except httpx.HTTPStatusError as exc:
        raise RuntimeError(f"Ollama HTTP {exc.response.status_code}: {exc.response.text}")

    data = r.json()
    text = data.get("message", {}).get("content", "").strip()
    latency = time.perf_counter() - t0

    print(f"[OLLAMA] 🤖 Modelo: {target_model} | "
          f"Tokens: {data.get('eval_count','?')} | "
          f"Latencia: {latency*1000:.0f}ms")

    return text, latency
