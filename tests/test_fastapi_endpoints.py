import asyncio
import sys
import os
import base64

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from fastapi.testclient import TestClient
from audio_engine.main import app

def main():
    client = TestClient(app)
    
    print("\n=== TEST 1: GET /api/ai/tts/preview con diferentes voces ===")
    for voice in ["dalia", "jorge", "paloma", "alvaro", "elena"]:
        res = client.get(f"/api/ai/tts/preview?voice={voice}")
        assert res.status_code == 200, f"Error {res.status_code} en preview {voice}"
        assert res.headers["content-type"] == "audio/mpeg"
        assert len(res.content) > 1000
        print(f"  [PASS] Preview '{voice}': {len(res.content)} bytes MP3")

    print("\n=== TEST 2: GET /api/tts/preview alias ===")
    res_alias = client.get("/api/tts/preview?voice=paloma&text=Prueba de sonido")
    assert res_alias.status_code == 200
    assert len(res_alias.content) > 1000
    print(f"  [PASS] Preview alias: {len(res_alias.content)} bytes MP3")

    print("\n=== TEST 3: POST /generate con síntesis neuronal ===")
    res_gen = client.post("/generate", json={
        "user_message": "Hello tutor",
        "voice": "jorge",
        "synthesize_audio": True
    })
    assert res_gen.status_code == 200, f"Error {res_gen.status_code}: {res_gen.text}"
    data = res_gen.json()
    assert "conversation" in data
    assert data.get("audio_b64") is not None
    assert data.get("audio_mime") == "audio/mpeg"
    decoded_audio = base64.b64decode(data["audio_b64"])
    print(f"  [PASS] /generate: respuesta='{data['conversation'][:40]}...' | audio={len(decoded_audio)} bytes MP3")

    print("\n=== TEST 4: POST /ingest (texto directo) ===")
    res_ingest = client.post("/ingest", data={
        "text": "I want to improve my accent",
        "voice": "dalia",
        "synthesize_audio": "true"
    })
    assert res_ingest.status_code == 200, f"Error {res_ingest.status_code}: {res_ingest.text}"
    data_ingest = res_ingest.json()
    assert data_ingest.get("audio_b64") is not None
    print(f"  [PASS] /ingest: audio={len(base64.b64decode(data_ingest['audio_b64']))} bytes MP3")

    print("\nTODOS LOS TESTS DE ENDPOINTS PASARON EXITOSAMENTE.")

if __name__ == "__main__":
    main()
