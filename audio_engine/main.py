"""
LingoBeats / LingoVibe — audio_engine/main.py
FastAPI Motor de Audio e Inteligencia Artificial — Puerto 8000
Lifespan singleton, validación de magic bytes, persistencia de audios, rotación de archivos,
integración de Scorer (WER/Levenshtein), Downloader (yt-dlp), Separator (Demucs) y TutorAgent.
"""

from __future__ import annotations

import os
import sys
import time
import base64
import logging
import traceback
from contextlib import asynccontextmanager
from typing import Optional, Dict, Any

if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
if hasattr(sys.stderr, "reconfigure"):
    try:
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

# Compatibilidad defensiva con PyAV (av >= 14 no soporta metadata_errors)
try:
    import av
    _orig_av_open = av.open
    def _safe_av_open(*args, **kwargs):
        kwargs.pop("metadata_errors", None)
        return _orig_av_open(*args, **kwargs)
    av.open = _safe_av_open
except Exception:
    pass

# Agrega directorio raíz al path para importar db
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))


from fastapi import FastAPI, File, Form, HTTPException, UploadFile, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response, JSONResponse
from pydantic import BaseModel, Field

try:
    from dotenv import load_dotenv
    load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))
except ImportError:
    _env_path = os.path.join(os.path.dirname(__file__), "..", ".env")
    if os.path.exists(_env_path):
        with open(_env_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, v = line.split("=", 1)
                    os.environ.setdefault(k.strip(), v.strip().strip("'\""))

from audio_engine import whisper_stt, ollama_client, gemini_client, tts_engine
from audio_engine.services.tutor_agent import TutorAgent
from audio_engine.services.scorer import PhoneticScorer
from audio_engine.services.downloader import AudioDownloader
from audio_engine.services.audio_separator import StemSeparator
from db import database

# ─────────────────────────────────────────────────────────────
#  Directorios y Rutas
# ─────────────────────────────────────────────────────────────

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
STORAGE_DIR = os.path.join(BASE_DIR, "data", "storage", "turns")
DOWNLOADS_DIR = os.path.join(BASE_DIR, "data", "storage", "downloads")
STEMS_DIR = os.path.join(BASE_DIR, "data", "storage", "stems")
LOGS_DIR = os.path.join(BASE_DIR, "logs")

for d in (STORAGE_DIR, DOWNLOADS_DIR, STEMS_DIR, LOGS_DIR):
    os.makedirs(d, exist_ok=True)

# Logging local aislado para prevenir fuga de stack traces al cliente
logger = logging.getLogger("audio_engine")
logger.setLevel(logging.INFO)
file_handler = logging.FileHandler(os.path.join(LOGS_DIR, "audio_engine.log"), encoding="utf-8")
file_handler.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s"))
logger.addHandler(file_handler)


# ─────────────────────────────────────────────────────────────
#  Lifespan: Inicialización Singleton y Purga Automática
# ─────────────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    print("=" * 60)
    print("  [STARTUP] LingoBeats Audio Engine iniciando...")
    print("=" * 60)

    # 1. Aplicar esquema SQLite
    await database.init_db()

    # 2. Inicializar Singleton de Whisper en memoria (eager loading)
    if whisper_stt.is_available():
        try:
            whisper_stt.get_model()
            print("[AUDIO ENGINE] [OK] Whisper Singleton cargado en memoria.")
        except Exception as exc:
            print(f"[AUDIO ENGINE] [WARN] No se pudo precargar modelo Whisper: {exc}")

    # 3. Purga defensiva de audios temporales con más de 7 días
    purged = database.purge_old_audio_files(STORAGE_DIR, max_age_days=7)
    if purged > 0:
        print(f"[AUDIO ENGINE] [PURGE] Purga automatica: {purged} audios antiguos eliminados.")

    yield
    print("[AUDIO ENGINE] [SHUTDOWN] Apagando Audio Engine.")



# ─────────────────────────────────────────────────────────────
#  App FastAPI
# ─────────────────────────────────────────────────────────────

app = FastAPI(
    title="LingoBeats Audio & AI Engine",
    version="2.1.0",
    description="Motor unificado de STT, LLM adaptativo, TTS y procesamiento musical para LingoBeats",
    lifespan=lifespan,
)

# CORS defensivo: permite orígenes locales autorizados
ALLOWED_ORIGINS = [
    "http://localhost:3000",
    "http://127.0.0.1:3000",
    "http://localhost:5000",
    "http://127.0.0.1:5000",
    "http://localhost:5500",
    "http://127.0.0.1:5500",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
)


# ─────────────────────────────────────────────────────────────
#  Middleware Global de Manejo de Errores y Seguridad (Item 13)
# ─────────────────────────────────────────────────────────────

@app.middleware("http")
async def security_and_error_middleware(request: Request, call_next):
    # Límite global de payload (10 MB)
    content_length = request.headers.get("content-length")
    if content_length and int(content_length) > 10 * 1024 * 1024:
        return JSONResponse(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            content={"success": False, "error": "PAYLOAD_TOO_LARGE", "detail": "El archivo excede el límite máximo de 10 MB."},
        )

    try:
        response = await call_next(request)
        return response
    except HTTPException:
        raise
    except Exception as exc:
        # Registrar stack trace en log local sin exponerlo al cliente
        logger.error(f"Error no controlado en {request.method} {request.url.path}: {exc}\n{traceback.format_exc()}")
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "success": False,
                "error": "INTERNAL_PROCESSING_ERROR",
                "detail": "Ha ocurrido un error interno en el procesamiento de audio o inferencia.",
            },
        )


# ─────────────────────────────────────────────────────────────
#  Utilidades de Validación de Magic Bytes (Item 11)
# ─────────────────────────────────────────────────────────────

def validate_audio_magic_bytes(data: bytes) -> bool:
    """Verifica firmas binarias de archivos de audio reales (WebM, WAV, MP3, OGG)."""
    if len(data) < 4:
        return False
    # WebM / MKV (EBML)
    if data[:4] == b"\x1a\x45\xdf\xa3":
        return True
    # WAV (RIFF)
    if data[:4] == b"RIFF":
        return True
    # MP3 ID3 header
    if data[:3] == b"ID3":
        return True
    # MP3 frame sync (11 bits en 1)
    if data[0] == 0xFF and (data[1] & 0xE0) == 0xE0:
        return True
    # OGG container
    if data[:4] == b"OggS":
        return True
    return False


async def build_system_prompt(user_key: str = "usr_001", cefr_level: Optional[str] = None) -> str:
    """Construye el prompt de sistema inyectando memoria relacional activa desde SQLite."""
    system_md_path = os.path.join(BASE_DIR, "system_prompt.md")
    base = ""
    if os.path.exists(system_md_path):
        with open(system_md_path, "r", encoding="utf-8") as f:
            base = f.read().strip()

    user = await database.get_user(user_key)
    level = cefr_level or (user["cefr_level"] if user else "B2")
    weaknesses: list[str] = []
    if user:
        weaknesses = await database.get_weaknesses(user["id"])

    injection = f"""
# CURRENT ACTIVE USER STATE (INJECTED MEMORY - DO NOT REPEAT TO USER)
- Target Level: {level}
- Active Weaknesses to Watch & Correct:
{"  - " + chr(10).join(f"- {w}" for w in weaknesses) if weaknesses else "  None specified"}

# OUTPUT FORMAT (MANDATORY JSON ONLY)
You MUST reply with a raw JSON object matching:
{{
  "conversation": "Your warm conversational reply (1-2 sentences).",
  "feedback": "1-2 concise bullet points if mistakes were made, or null.",
  "target_corrections": ["word_or_rule1"],
  "comprehension_question": "Follow-up question."
}}
"""
    return f"{base}\n{injection}".strip()


def _generate_local_tutor_fallback(user_message: str) -> str:
    """Generador pedagógico heurístico local a prueba de caídas (Schema JSON estricto)."""
    import json
    msg = (user_message or "").strip()
    msg_lower = msg.lower()

    if any(w in msg_lower for w in ["hola", "buenas", "que tal", "cómo vamos", "como vamos", "aprender"]):
        return json.dumps({
            "conversation": "Hello! Welcome to LingoBeats! In English, you can say: 'Hello, how is it going?' What would you like to practice today?",
            "feedback": "Great start! When greeting someone in English, you can say 'Hello' or 'Hi', followed by 'How are you?' or 'How is it going?'.",
            "target_corrections": ["Hello, how is it going?"],
            "comprehension_question": "Can you try repeating: 'I want to practice English'?"
        }, ensure_ascii=False)

    if any(w in msg_lower for w in ["yes", "si", "sí", "yeah", "ok", "sure", "fine", "good"]):
        return json.dumps({
            "conversation": "Awesome! Let's build your vocabulary. What music or hobbies do you enjoy the most?",
            "feedback": "Good response! You can answer with a complete sentence like: 'I enjoy listening to rock music!'.",
            "target_corrections": [],
            "comprehension_question": "What is your favorite English song?"
        }, ensure_ascii=False)

    if "inaudible" in msg_lower or "silencio" in msg_lower or not msg_lower:
        return json.dumps({
            "conversation": "I couldn't quite hear that clearly. Could you please try speaking a bit closer to your microphone?",
            "feedback": "Make sure your microphone is connected and speak clearly at a normal volume.",
            "target_corrections": [],
            "comprehension_question": "Could you try saying 'Hello tutor, can you hear me'?"
        }, ensure_ascii=False)

    return json.dumps({
        "conversation": f"I understand! You said: '{msg}'. That is a good attempt, let's keep practicing in English!",
        "feedback": "Good effort! Remember to pay attention to clear pronunciation and complete sentences.",
        "target_corrections": [],
        "comprehension_question": "Can you tell me more about that in one full English sentence?"
    }, ensure_ascii=False)


async def select_llm(
    system_prompt: str,
    user_message: str,
    audio_b64: Optional[str] = None,
    mime_type: str = "audio/webm",
) -> tuple[str, str, float]:
    """
    Inferencia de LLM con timeout estricto de 4.0s en Ollama local y fallback automático a Gemini / Motor Local.
    Garantiza 0% fallos y 100% disponibilidad.
    """
    if not audio_b64:
        try:
            if await ollama_client.is_model_available():
                text, latency = await ollama_client.generate(
                    system_prompt, user_message, response_format="json"
                )
                return text, "ollama", latency
        except Exception as exc:
            logger.warning(f"[LLM] Ollama no disponible ({exc}), evaluando fallback...")

    # Fallback a Gemini Cloud si está configurado
    if gemini_client.is_configured():
        provider = "whisper+gemini" if audio_b64 else "gemini"
        try:
            text, latency = await gemini_client.generate(
                system_prompt, user_message, audio_b64, mime_type
            )
            return text, provider, latency
        except Exception as exc:
            logger.warning(f"[LLM] Gemini Cloud no disponible o clave no válida ({exc}), activando tutor local.")

    # Fallback pedagógico local (cero fallos de pipeline)
    logger.info("[LLM] Despachando respuesta a través del motor tutor de respaldo local.")
    fallback_text = _generate_local_tutor_fallback(user_message)
    return fallback_text, "local_tutor_engine", 0.02


# ─────────────────────────────────────────────────────────────
#  Endpoints de Diagnóstico y Perfil
# ─────────────────────────────────────────────────────────────

@app.get("/health")
async def health():
    ollama_status = await ollama_client.health_check()
    return {
        "status": "ok",
        "service": "LingoBeats Audio Engine",
        "whisper": {
            "available": whisper_stt.is_available(),
            "model": os.environ.get("WHISPER_MODEL", "base"),
            "device": os.environ.get("WHISPER_DEVICE", "cpu"),
        },
        "ollama": ollama_status,
        "gemini": {"configured": gemini_client.is_configured()},
        "tts": {"backend": tts_engine.get_available_backend()},
    }


@app.get("/api/profile")
async def get_profile(user_key: str = "usr_001"):
    profile = await database.get_full_profile(user_key)
    if not profile:
        raise HTTPException(404, f"Usuario '{user_key}' no encontrado.")
    return profile


class LevelUpdate(BaseModel):
    level: str
    user_key: str = "usr_001"


@app.post("/api/profile/level")
async def update_level(req: LevelUpdate):
    valid_levels = {"A1", "A2", "B1", "B2", "C1", "C2"}
    level = req.level.upper()
    if level not in valid_levels:
        raise HTTPException(400, f"Nivel inválido. Use: {', '.join(sorted(valid_levels))}")
    updated = await database.update_user_level(req.user_key, level)
    if not updated:
        raise HTTPException(404, f"Usuario '{req.user_key}' no encontrado.")
    return {"status": "ok", "current_level": level}


# ─────────────────────────────────────────────────────────────
#  Endpoints de STT, TTS y Pipeline Integral
# ─────────────────────────────────────────────────────────────

@app.post("/transcribe")
async def transcribe(
    audio: UploadFile = File(...),
    language: str = Form(default="en"),
):
    if not whisper_stt.is_available():
        raise HTTPException(503, "Whisper STT no disponible. pip install faster-whisper")

    audio_bytes = await audio.read()
    if not validate_audio_magic_bytes(audio_bytes):
        raise HTTPException(400, "Firma de audio inválida. Se requiere WebM, WAV, MP3 u OGG.")

    transcript, latency = await whisper_stt.transcribe(audio_bytes, language)
    return {
        "transcript": transcript,
        "language": language,
        "latency_ms": int(latency * 1000),
    }


class GenerateRequest(BaseModel):
    user_message: str
    session_id: Optional[int] = None
    turn_seq: Optional[int] = None
    user_key: str = "usr_001"
    cefr_level: Optional[str] = None
    audio_b64: Optional[str] = None
    mime_type: str = "audio/webm"


@app.post("/generate")
async def generate(req: GenerateRequest):
    system_prompt = await build_system_prompt(req.user_key, req.cefr_level)
    raw, provider, latency = await select_llm(
        system_prompt, req.user_message, req.audio_b64, req.mime_type
    )
    parsed = TutorAgent.parse_response(raw)

    if req.session_id and req.turn_seq is not None:
        await database.save_turn(
            session_id=req.session_id,
            seq=req.turn_seq,
            input_type="audio" if req.audio_b64 else "text",
            user_input_text=req.user_message,
            tutor_conv=parsed["conversation"],
            tutor_feedback=parsed["feedback"],
            llm_provider=provider,
            latency_ms=int(latency * 1000),
        )
        await database.increment_session_turns(req.session_id)

    return {
        "raw": raw,
        "conversation": parsed["conversation"],
        "feedback": parsed["feedback"],
        "target_corrections": parsed.get("target_corrections", []),
        "comprehension_question": parsed.get("comprehension_question"),
        "llm_provider": provider,
        "latency_ms": int(latency * 1000),
    }


class SynthesizeRequest(BaseModel):
    text: str
    target_lang: str = "en-US"
    voice: Optional[str] = None
    rate: Optional[str] = None


@app.post("/synthesize")
async def synthesize(req: SynthesizeRequest):
    audio_bytes = await tts_engine.synthesize(
        req.text, req.target_lang, req.voice, req.rate
    )
    return Response(content=audio_bytes, media_type="audio/mpeg")


@app.post("/ingest")
async def ingest(
    audio: Optional[UploadFile] = File(default=None),
    text: Optional[str] = Form(default=None),
    session_id: Optional[int] = Form(default=None),
    turn_seq: int = Form(default=1),
    user_key: str = Form(default="usr_001"),
    cefr_level: Optional[str] = None,
    target_lang: str = Form(default="en-US"),
    language: Optional[str] = Form(default=None),
    synthesize_audio: bool = Form(default=True),
):
    """
    Pipeline completo de turno conversacional:
    1. STT en memoria con Whisper
    2. Guardado de audio en storage local y persistencia de ruta
    3. Inferencia LLM con blindaje JSON (Ollama -> Gemini -> Tutor Local)
    4. Síntesis TTS y retorno binario base64
    """
    t_start = time.perf_counter()
    transcript = text or ""
    saved_audio_path = None
    stt_latency = 0.0
    provider = "text"

    # 1. Procesamiento y guardado de audio
    if audio and not transcript:
        audio_bytes = await audio.read()
        if not validate_audio_magic_bytes(audio_bytes):
            raise HTTPException(400, "Encabezado de archivo inválido. Se requiere un formato de audio válido.")

        # Persistir archivo de audio en almacenamiento ordenado
        sess_dir = os.path.join(STORAGE_DIR, str(session_id or "general"))
        os.makedirs(sess_dir, exist_ok=True)
        file_name = f"turn_{turn_seq}_{int(time.time())}.webm"
        saved_audio_path = os.path.join(sess_dir, file_name)

        with open(saved_audio_path, "wb") as f:
            f.write(audio_bytes)

        # STT en memoria (BytesIO nativo) con autodetección
        transcript, stt_latency = await whisper_stt.transcribe(audio_bytes, language)
        provider = "whisper+"

    if not transcript:
        transcript = "(audio inaudible o en silencio)"

    # 2. Inferencia LLM
    system_prompt = await build_system_prompt(user_key, cefr_level)
    raw, llm_provider, llm_latency = await select_llm(system_prompt, transcript)
    provider = provider + llm_provider if provider.endswith("+") else llm_provider

    parsed = TutorAgent.parse_response(raw)

    # 3. Persistencia en SQLite
    if session_id is not None:
        await database.save_turn(
            session_id=session_id,
            seq=turn_seq,
            input_type="audio" if audio else "text",
            user_input_text=transcript,
            audio_path=saved_audio_path,
            transcript=transcript,
            tutor_conv=parsed["conversation"],
            tutor_feedback=parsed["feedback"],
            llm_provider=provider,
            latency_ms=int((time.perf_counter() - t_start) * 1000),
        )
        await database.increment_session_turns(session_id)

    # 4. Síntesis de Audio (TTS)
    audio_b64 = None
    if synthesize_audio and parsed["conversation"]:
        try:
            tts_bytes = await tts_engine.synthesize(parsed["conversation"], target_lang)
            audio_b64 = base64.b64encode(tts_bytes).decode("ascii")
        except Exception as exc:
            logger.warning(f"Fallo en síntesis TTS (no crítico): {exc}")

    return {
        "transcript": transcript,
        "raw": raw,
        "conversation": parsed["conversation"],
        "feedback": parsed["feedback"],
        "target_corrections": parsed.get("target_corrections", []),
        "comprehension_question": parsed.get("comprehension_question"),
        "audio_b64": audio_b64,
        "audio_path": saved_audio_path,
        "audio_mime": "audio/mpeg",
        "llm_provider": provider,
        "stt_latency_ms": int(stt_latency * 1000),
        "llm_latency_ms": int(llm_latency * 1000),
        "total_latency_ms": int((time.perf_counter() - t_start) * 1000),
    }


# ─────────────────────────────────────────────────────────────
#  Nuevos Módulos de LingoBeats: Scoring, Descarga y Stems
# ─────────────────────────────────────────────────────────────

class ScoreRequest(BaseModel):
    target_text: str = Field(..., description="Texto lírico u objetivo esperado")
    transcript: str = Field(..., description="Transcripción producida por el usuario")
    threshold: float = Field(default=70.0, description="Umbral de aprobación (0-100)")


@app.post("/api/score")
async def compute_score(req: ScoreRequest):
    """Evalúa precisión fonológica, WER, distancia Levenshtein y omisiones consonánticas."""
    scorer = PhoneticScorer(passing_threshold=req.threshold)
    result = scorer.score(req.target_text, req.transcript)
    return result


class DownloadRequest(BaseModel):
    url: str = Field(..., description="URL de YouTube o SoundCloud")


@app.post("/api/download")
async def download_track(req: DownloadRequest):
    """Descarga de pista de audio optimizada con yt-dlp."""
    downloader = AudioDownloader(sample_rate=44100, audio_format="mp3")
    try:
        meta = downloader.download_audio(req.url, DOWNLOADS_DIR)
        return {"status": "ok", "metadata": meta}
    except ValueError as ve:
        raise HTTPException(400, str(ve))
    except Exception as exc:
        raise HTTPException(500, f"Error al descargar pista: {exc}")


class SeparateRequest(BaseModel):
    audio_path: str = Field(..., description="Ruta absoluta o relativa del archivo de audio a separar")


@app.post("/api/separate")
async def separate_track(req: SeparateRequest):
    """Separación de pistas en voz e instrumental con Demucs (htdemucs)."""
    separator = StemSeparator()
    try:
        stems = separator.separate_vocals(req.audio_path, STEMS_DIR)
        return {"status": "ok", "stems": stems}
    except FileNotFoundError as fe:
        raise HTTPException(404, str(fe))
    except Exception as exc:
        raise HTTPException(500, f"Error en separación de pistas: {exc}")


# ─────────────────────────────────────────────────────────────
#  Endpoints de Gestión de Sesiones
# ─────────────────────────────────────────────────────────────

class SessionStart(BaseModel):
    user_key: str = "usr_001"
    cefr_level: str = "B2"


@app.post("/session/start")
async def session_start(req: SessionStart):
    user = await database.get_user(req.user_key)
    if not user:
        raise HTTPException(404, f"Usuario '{req.user_key}' no encontrado.")
    level = req.cefr_level.upper()
    session_id = await database.create_session(user["id"], level)
    return {"session_id": session_id, "user_id": req.user_key, "cefr_level": level}


class SessionEnd(BaseModel):
    session_id: int
    score: Optional[float] = None


@app.post("/session/end")
async def session_end(req: SessionEnd):
    await database.close_session(req.session_id, req.score)
    session = await database.get_session(req.session_id)
    return {"status": "closed", "session": session}


@app.get("/session/{session_id}")
async def session_get(session_id: int):
    session = await database.get_session(session_id)
    if not session:
        raise HTTPException(404, f"Sesión {session_id} no encontrada.")
    turns = await database.get_session_turns(session_id)
    return {"session": session, "turns": turns}
