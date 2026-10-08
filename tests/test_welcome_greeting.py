import asyncio
import sys
import os

# Asegura imports desde raíz y backend-ai
ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
BACKEND_AI_DIR = os.path.join(ROOT_DIR, "backend-ai")

for p in (ROOT_DIR, BACKEND_AI_DIR):
    if p not in sys.path:
        sys.path.insert(0, p)

from fastapi.testclient import TestClient

def test_welcome_agent():
    print("\n=== TEST 1: Verificación de WELCOME_TEMPLATES y get_welcome_greeting ===")
    from app.services.tutor_agent import WELCOME_TEMPLATES, get_welcome_greeting
    
    # 1. Verificar catálogo
    assert "friendly" in WELCOME_TEMPLATES, "Falta estilo friendly"
    assert "funny" in WELCOME_TEMPLATES, "Falta estilo funny"
    assert "strict" in WELCOME_TEMPLATES, "Falta estilo strict"
    assert len(WELCOME_TEMPLATES["friendly"]) == 3, "friendly debe tener 3 opciones"
    assert len(WELCOME_TEMPLATES["funny"]) == 3, "funny debe tener 3 opciones"
    assert len(WELCOME_TEMPLATES["strict"]) == 3, "strict debe tener 3 opciones"
    print("  [PASS] WELCOME_TEMPLATES contiene los 3 estilos con 3 opciones cada uno.")

    # 2. Probar generación de texto
    for att in ["friendly", "funny", "strict"]:
        greeting = get_welcome_greeting(song_title="Bohemian Rhapsody", artist="Queen", attitude=att)
        assert "Bohemian Rhapsody" in greeting, f"La canción debe estar en el saludo: {greeting}"
        assert "Queen" in greeting, f"El artista debe estar en el saludo: {greeting}"
        print(f"  [PASS] Estilo '{att}': \"{greeting}\"")

def test_tts_attitude_modulation():
    print("\n=== TEST 2: Modulación prosódica en synthesize_speech según actitud ===")
    from audio_engine import tts_engine

    async def _run():
        attitudes = ["friendly", "funny", "strict"]
        text = "Welcome to LingoBeats! Let's practice English together."
        for att in attitudes:
            audio_bytes = await tts_engine.synthesize_speech(
                text=text,
                voice_key="dalia",
                attitude=att,
            )
            assert len(audio_bytes) > 2000, f"Audio demasiado corto para {att}"
            is_mp3 = audio_bytes[:3] == b"ID3" or (audio_bytes[0] == 0xFF and (audio_bytes[1] & 0xE0) == 0xE0)
            assert is_mp3, f"El audio no es MP3 válido para {att}"
            print(f"  [PASS] Síntesis con actitud '{att}': {len(audio_bytes)} bytes MP3")

    asyncio.run(_run())

def test_fastapi_welcome_endpoint():
    print("\n=== TEST 3: Endpoint GET /api/ai/session/welcome ===")
    # Probar endpoint tanto en backend-ai.main como en audio_engine.main
    from audio_engine.main import app
    client = TestClient(app)

    test_cases = [
        {"song": "Yesterday", "artist": "The Beatles", "attitude": "friendly", "voice": "dalia"},
        {"song": "Shape of You", "artist": "Ed Sheeran", "attitude": "funny", "voice": "jorge"},
        {"song": "Believer", "artist": "Imagine Dragons", "attitude": "strict", "voice": "paloma"},
        {"song": "Hotel California", "artist": "Eagles", "attitude": "funny", "voice": "alvaro"},
        {"song": "Rolling in the Deep", "artist": "Adele", "attitude": "friendly", "voice": "elena"},
    ]

    for tc in test_cases:
        url = f"/api/ai/session/welcome?song={tc['song']}&artist={tc['artist']}&attitude={tc['attitude']}&voice={tc['voice']}"
        res = client.get(url)
        assert res.status_code == 200, f"Error {res.status_code}: {res.text}"
        assert res.headers["content-type"] == "audio/mpeg"
        assert len(res.content) > 2000
        print(f"  [PASS] Endpoint OK ({tc['attitude']} | {tc['voice']}): {len(res.content)} bytes MP3")

    print("\n=== TEST 4: Importación y ejecución directa de backend-ai/main.py ===")
    import importlib.util
    spec = importlib.util.spec_from_file_location("backend_ai_main", os.path.join(BACKEND_AI_DIR, "main.py"))
    backend_ai_mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(backend_ai_mod)
    client_backend_ai = TestClient(backend_ai_mod.app)
    res_b = client_backend_ai.get("/api/ai/session/welcome?song=Thriller&artist=Michael+Jackson&attitude=funny&voice=dalia")
    assert res_b.status_code == 200
    assert res_b.headers["content-type"] == "audio/mpeg"
    assert len(res_b.content) > 2000
    print(f"  [PASS] backend-ai/main.py app directo: {len(res_b.content)} bytes MP3")

    print("\nTODOS LOS TESTS DE SALUDO CONTEXTUAL PASARON EXITOSAMENTE.")

if __name__ == "__main__":
    test_welcome_agent()
    test_tts_attitude_modulation()
    test_fastapi_welcome_endpoint()
