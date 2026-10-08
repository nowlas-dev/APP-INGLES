"""
Test de verificación del selector interactivo de tutores y perfiles prosódicos de voz.
"""
import asyncio
import os
import sys

try:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "backend-ai")))
import tts_engine


async def test_tutor_selector():
    print("[TEST] Verificando catálogo de personalidades TUTOR_PROFILES...")

    expected_tutors = ["dalia", "jorge", "paloma", "alvaro", "elena"]
    for tutor in expected_tutors:
        assert tutor in tts_engine.TUTOR_PROFILES, f"Falta tutor '{tutor}' en TUTOR_PROFILES"
        profile = tts_engine.get_tutor_profile(tutor)
        assert "voice" in profile and "rate" in profile and "pitch" in profile
        print(f"  -> {tutor.upper()}: Voz={profile['voice']} | Rate={profile['rate']} | Pitch={profile['pitch']}")

    # Fallback a dalia ante clave desconocida
    fallback_prof = tts_engine.get_tutor_profile("desconocido_xyz")
    assert fallback_prof["voice"] == "es-MX-DaliaNeural", "Fallback debe ser Dalia"
    print("  -> Fallback validado correctamente hacia Dalia")

    # Síntesis con diferentes personalidades
    preview_text = "¡Hola! Seré tu guía en esta canción."
    
    print("\n[TEST] Probando síntesis neuronal para cada tutor...")
    for tutor in expected_tutors:
        audio = await tts_engine.synthesize(preview_text, voice_id=tutor)
        assert len(audio) > 1000, f"Audio generado para {tutor} es demasiado pequeño"
        print(f"  [OK] Tutor '{tutor}' generó {len(audio):,} bytes")

    print("\n[OK] TODOS LOS PERFILES DE TUTOR FUERON VALIDADOS EXITOSAMENTE!")


if __name__ == "__main__":
    asyncio.run(test_tutor_selector())
