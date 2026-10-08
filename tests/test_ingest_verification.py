"""
Test de verificación del pipeline de ingesta de audio con el archivo real grabado.
"""
import asyncio
import os
import sys
import httpx

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from audio_engine.main import app

async def run():
    webm_path = os.path.join(os.path.dirname(__file__), "..", "data", "storage", "turns", "1", "turn_2_1791419446.webm")
    if not os.path.exists(webm_path):
        print("Webm not found, searching...")
        import glob
        files = glob.glob(os.path.join(os.path.dirname(__file__), "..", "data", "storage", "turns", "*", "*.webm"))
        if not files:
            print("No audio files found")
            return
        webm_path = files[0]
    
    with open(webm_path, "rb") as f:
        audio_bytes = f.read()

    print(f"Testing audio of size {len(audio_bytes)} bytes...")
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        files = {"audio": ("audio.webm", audio_bytes, "audio/webm")}
        data = {
            "session_id": "1",
            "turn_seq": "3",
            "user_key": "usr_001",
            "cefr_level": "B2",
            "synthesize_audio": "true",
        }
        r = await client.post("/ingest", files=files, data=data)
        print("STATUS CODE:", r.status_code)
        resp = r.json()
        print("TRANSCRIPT:", resp.get("transcript"))
        print("CONVERSATION:", resp.get("conversation"))
        print("FEEDBACK:", resp.get("feedback"))
        print("LLM PROVIDER:", resp.get("llm_provider"))
        print("AUDIO B64 LENGTH:", len(resp.get("audio_b64") or ""))
        assert r.status_code == 200, f"Expected 200, got {r.status_code}"
        assert resp.get("transcript") != "", "Transcript empty"
        print("VERIFICATION SUCCESSFUL: 100% OPERATIONAL!")

if __name__ == "__main__":
    asyncio.run(run())
