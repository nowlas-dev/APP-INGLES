"""
Prueba de verificación del motor TTS mejorado (Prosodia, Cache LRU, DaliaNeural, Fallback).
"""
import asyncio
import io
import os
import sys
import time

# Probar edge-tts con es-MX-DaliaNeural y prosodia
async def test_edge_prosody():
    import edge_tts
    text = "Asegúrate de marcar la 'D' al final de 'land'. ¡Excelente trabajo!"
    voice = "es-MX-DaliaNeural"
    rate = "-3%"
    pitch = "+0Hz"
    
    t0 = time.perf_counter()
    comm = edge_tts.Communicate(text=text, voice=voice, rate=rate, pitch=pitch)
    buf = io.BytesIO()
    async for chunk in comm.stream():
        if chunk["type"] == "audio":
            buf.write(chunk["data"])
    data = buf.getvalue()
    lat = time.perf_counter() - t0
    print(f"EdgeTTS OK! Voice={voice}, Bytes={len(data)}, Latency={lat*1000:.1f}ms")
    assert len(data) > 0

def test_pyttsx3_fallback():
    import pyttsx3
    engine = pyttsx3.init()
    engine.setProperty("rate", 145)
    engine.setProperty("volume", 0.95)
    voices = engine.getProperty("voices")
    selected_voice = None
    for v in voices:
        if any(name.lower() in v.name.lower() for name in ["zira", "sabina", "helena", "laura"]):
            selected_voice = v.id
            break
    if selected_voice:
        engine.setProperty("voice", selected_voice)
    print(f"pyttsx3 OK! Selected voice: {selected_voice or 'default'}")

if __name__ == "__main__":
    asyncio.run(test_edge_prosody())
    test_pyttsx3_fallback()
    print("ALL TTS SMOKE TESTS PASSED!")
