import asyncio
import sys
import os

# Agrega directorio raíz al sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from audio_engine import tts_engine

async def main():
    voices = ["dalia", "jorge", "paloma", "alvaro", "elena"]
    text = "Hola, seré tu tutor de inglés en esta canción"
    
    print(f"Probando sintesis para las 5 voces con edge-tts...")
    for v in voices:
        try:
            audio_bytes = await tts_engine.synthesize_speech(text, voice_key=v)
            is_mp3 = audio_bytes[:3] == b"ID3" or (len(audio_bytes) > 2 and audio_bytes[0] == 0xFF and (audio_bytes[1] & 0xE0) == 0xE0)
            print(f"  [OK] Voz '{v}': {len(audio_bytes)} bytes generados | Valido MP3: {is_mp3}")
        except Exception as e:
            print(f"  [FAIL] Voz '{v}': Error -> {e}")

if __name__ == "__main__":
    asyncio.run(main())
