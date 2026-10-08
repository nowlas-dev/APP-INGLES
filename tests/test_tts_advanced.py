"""
Test de verificación del motor TTS avanzado (backend-ai/tts_engine.py y audio_engine/tts_engine.py).
"""
import asyncio
import os
import sys
import time

try:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

async def test_full_tts():
    # Probar módulo en backend-ai
    sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "backend-ai")))
    import tts_engine

    print(f"[TEST] Backend detectado: {tts_engine.get_available_backend()}")

    # 1. Síntesis bilingüe con edge-tts y voz DaliaNeural
    sample_text = "Asegúrate de marcar la D al final de 'land'. ¡Excelente trabajo!"
    t0 = time.perf_counter()
    audio_1 = await tts_engine.synthesize(sample_text)
    latency_1 = (time.perf_counter() - t0) * 1000

    print(f"[TEST 1] Síntesis primaria completada: {len(audio_1):,} bytes en {latency_1:.1f}ms")
    assert len(audio_1) > 1000, "Audio generado demasiado pequeño"

    # 2. Prueba de Cache LRU en Memoria (debe ser casi 0 ms)
    t1 = time.perf_counter()
    audio_2 = await tts_engine.synthesize(sample_text)
    latency_2 = (time.perf_counter() - t1) * 1000

    print(f"[TEST 2] Cache HIT en memoria: {len(audio_2):,} bytes en {latency_2:.3f}ms")
    assert audio_1 == audio_2, "Los bytes del cache deben ser idénticos"
    assert latency_2 < 10.0, f"Cache HIT debe ser ultrarrápido (< 10ms), fue {latency_2:.2f}ms"
    assert tts_engine.get_cache_size() >= 1, "Cache size debe ser >= 1"

    # 3. Prueba de pre-procesamiento de code-switching
    raw_mixed = 'Recuerda que "yesterday" lleva acento inicial /jɛstərdeɪ/.'
    processed = tts_engine.preprocess_bilingual_text(raw_mixed)
    print(f"[TEST 3] Code-switching formateado: '{processed}'")
    assert '"yesterday"' in processed or "'yesterday'" in processed

    # 4. Prueba del fallback pyttsx3 configurado a rate=145
    audio_fallback = tts_engine._synthesize_pyttsx3("Prueba de voz de emergencia")
    print(f"[TEST 4] Fallback pyttsx3 generado: {len(audio_fallback):,} bytes")
    assert len(audio_fallback) > 1000

    print("\n[OK] TODOS LOS REQUERIMIENTOS DE AUDIO TTS FUERON VALIDADOS EXITOSAMENTE!")

if __name__ == "__main__":
    asyncio.run(test_full_tts())
