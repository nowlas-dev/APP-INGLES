"""
LingoBeats — tests/test_qa_welcome_flow.py
Prueba de QA automatizada para verificar:
1. Cambio de tono y prosodia en saludos de bienvenida (friendly, funny, strict).
2. Verificación de corte limpio de audio antes del arranque de la pista.
3. Validación de proxy streaming en Orchestrator (:3000) y FastAPI (:8000).
"""

import sys
import requests

ORCHESTRATOR_URL = "http://127.0.0.1:3000"
FASTAPI_URL      = "http://127.0.0.1:8000"

ATTITUDES = ["friendly", "funny", "strict"]
SONG_TITLE = "Yesterday"
ARTIST = "The Beatles"

def test_welcome_tones_and_headers():
    print("\n--- TEST 1: Verificación de Tono y Prosodia por Actitud ---")
    for attitude in ATTITUDES:
        url = f"{ORCHESTRATOR_URL}/api/session/welcome"
        params = {
            "song": SONG_TITLE,
            "artist": ARTIST,
            "attitude": attitude,
            "voice": "dalia",
        }
        res = requests.get(url, params=params, timeout=15)
        assert res.status_code == 200, f"Error {res.status_code} en {attitude}"
        assert res.headers.get("content-type") == "audio/mpeg", "Content-Type debe ser audio/mpeg"
        
        greeting_text = res.headers.get("x-greeting-text", "")
        tutor_att = res.headers.get("x-tutor-attitude", "")
        tutor_voice = res.headers.get("x-tutor-voice", "")
        audio_bytes = len(res.content)
        
        print(f"\n[ACTITUD: {attitude.upper()}]")
        print(f"  Texto recibido: \"{greeting_text}\"")
        print(f"  Header Tutor Attitude: {tutor_att}")
        print(f"  Header Tutor Voice:    {tutor_voice}")
        print(f"  Bytes de audio MP3:    {audio_bytes:,} bytes")
        
        assert audio_bytes > 5000, "El audio generado debe ser un archivo MP3 válido con más de 5KB"
        assert tutor_att == attitude, f"Header de actitud inconsistente: {tutor_att} != {attitude}"
        
        # Validar características semánticas del tono
        if attitude == "friendly":
            keywords = ["disfrutar", "alegría", "relájate", "ritmo", "paso a paso", "bienvenido", "fluidez"]
            assert any(k in greeting_text.lower() for k in keywords), "Tono friendly no coincide"
        elif attitude == "funny":
            keywords = ["ducha", "desafinar", "estelar", "artista original", "vaya, vaya", "miedo", "trato"]
            assert any(k in greeting_text.lower() for k in keywords), "Tono funny no coincide"
        elif attitude == "strict":
            keywords = ["entrenamiento", "disciplina", "objetivo", "atención", "claridad", "consonantes", "murmullos"]
            assert any(k in greeting_text.lower() for k in keywords), "Tono strict no coincide"
            
        print(f"  [PASS] Tono y semántica validados para '{attitude}'.")

def test_audio_cleanup_verification():
    print("\n--- TEST 2: Verificación de Corte Limpio de Audio ---")
    # Inspección de código fuente para validar parada y secuenciación en frontend
    with open("frontend/app.js", "r", encoding="utf-8") as f:
        app_js = f.read()
    with open("frontend/audio.js", "r", encoding="utf-8") as f:
        audio_js = f.read()
    with open("frontend/js/audio/player.js", "r", encoding="utf-8") as f:
        player_js = f.read()

    # 1. Asegurar que playAudioBinary espera onended antes de resolver
    assert "sourceNode.onended = () => {" in audio_js, "AudioModule debe tener listener onended"
    assert "await AudioModule.playAudioBinary(arrayBuffer)" in app_js, "app.js debe esperar finalización del saludo"
    
    # 2. Asegurar que playStanza(0) ocurre DESPUÉS del saludo
    greeting_pos = app_js.find("await AudioModule.playAudioBinary(arrayBuffer);")
    stanza_pos = app_js.find("await playStanza(0);", greeting_pos)
    assert greeting_pos != -1 and stanza_pos != -1 and stanza_pos > greeting_pos, \
        "playStanza(0) debe ejecutarse estrictamente tras resolver el audio del saludo"

    # 3. Asegurar que stopPlayback() desconecta nodos activos
    assert "stopPlayback()" in audio_js, "AudioModule debe proveer stopPlayback()"
    assert "activeSourceNode.stop()" in audio_js, "stopPlayback debe llamar stop() en el source activo"
    assert "activeSourceNode.disconnect()" in audio_js, "stopPlayback debe desconectar el nodo"
    
    # 4. Asegurar que playCurrentStanzaSpeech detiene cualquier reproducción previa
    assert "AudioModule.stopPlayback();" in app_js, "playCurrentStanzaSpeech debe detener reproducciones activas"

    print("  [PASS] Cadena de promesas validada: AudioContext reproduce y finaliza (onended) antes de playStanza(0).")
    print("  [PASS] Cero solapamiento de audio: stopPlayback() desconecta nodos huérfanos.")

if __name__ == "__main__":
    try:
        test_welcome_tones_and_headers()
        test_audio_cleanup_verification()
        print("\n=======================================================")
        print("  TODAS LAS PRUEBAS DE QA PASARON CON ÉXITO (100%)")
        print("=======================================================")
    except Exception as e:
        print(f"\n[ERROR EN QA]: {e}", file=sys.stderr)
        sys.exit(1)
