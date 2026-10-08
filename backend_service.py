import os
import sys
import json
import re
import asyncio
import traceback
import urllib.request
import urllib.error
from typing import Optional, Dict, Any, List
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, FileResponse, JSONResponse
from pydantic import BaseModel

# Try loading python-dotenv if installed, or parse local .env file manually
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    # Lightweight fallback .env loader
    env_file_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")
    if os.path.exists(env_file_path):
        with open(env_file_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, v = line.split("=", 1)
                    os.environ.setdefault(k.strip(), v.strip().strip("'\""))

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SYSTEM_PROMPT_PATH = os.path.join(BASE_DIR, "system_prompt.md")
MEMORY_PROFILE_PATH = os.path.join(BASE_DIR, "memory_profile.json")
INDEX_HTML_PATH = os.path.join(BASE_DIR, "index.html")
MANIFEST_PATH = os.path.join(BASE_DIR, "manifest.json")
SERVICE_WORKER_PATH = os.path.join(BASE_DIR, "service-worker.js")

app = FastAPI(title="LingoVibe Real-Time Voice Tutor API", version="3.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.on_event("startup")
async def startup_event():
    print("=" * 60)
    print("  🚀 LingoVibe Real-Time Voice Assistant Starting Up...")
    print("=" * 60)
    key = get_api_key()
    if key and len(key) > 8:
        masked = f"{key[:4]}...{key[-4:]}"
        print(f"[AUTH] ✅ API Key detected: {masked}")
    elif key:
        print("[AUTH] ⚠️ API Key detected (short length)")
    else:
        print("[AUTH] ❌ No API Key found in .env or environment (GEMINI_API_KEY).")
        print("[AUTH] 💡 Please paste your GEMINI_API_KEY into the .env file.")
    print("=" * 60)

def get_api_key() -> Optional[str]:
    """Retrieve and log LLM API key with masked character output."""
    key = (
        os.environ.get("GEMINI_API_KEY") or
        os.environ.get("API_KEY") or
        os.environ.get("GOOGLE_API_KEY")
    )
    if key and len(key.strip()) > 8:
        clean_key = key.strip()
        masked = f"{clean_key[:4]}...{clean_key[-4:]}"
        return clean_key
    elif key:
        return key.strip()
    else:
        return None

def load_memory_profile() -> Dict[str, Any]:
    if not os.path.exists(MEMORY_PROFILE_PATH):
        return {
            "user_id": "usr_001",
            "target_language": "en-US",
            "current_level": "B2",
            "persona": "friendly_peer",
            "stats": {"diagnostic_score": "7/10", "sessions_completed": 1, "total_turns": 4},
            "persistent_weaknesses": [
                "Subject-verb agreement (3rd person singular)",
                "Second conditional (if + past simple vs would)",
                "Preposition collocations (depend on, think about/of)"
            ],
            "vocabulary_bank": [
                {"word": "tone down", "mastery": 0.8},
                {"word": "buffer", "mastery": 0.9}
            ]
        }
    try:
        with open(MEMORY_PROFILE_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        print(f"[MEMORY ERROR]: Could not read memory_profile.json: {e}")
        return {}

def save_memory_profile(profile: Dict[str, Any]) -> None:
    try:
        with open(MEMORY_PROFILE_PATH, "w", encoding="utf-8") as f:
            json.dump(profile, f, indent=2, ensure_ascii=False)
    except Exception as e:
        print(f"[MEMORY ERROR]: Could not save memory_profile.json: {e}")

def build_contextual_prompt(current_level: Optional[str] = None) -> str:
    base_prompt = ""
    if os.path.exists(SYSTEM_PROMPT_PATH):
        with open(SYSTEM_PROMPT_PATH, "r", encoding="utf-8") as f:
            base_prompt = f.read().strip()

    profile = load_memory_profile()
    level = current_level or profile.get("current_level", "B2")
    weaknesses = profile.get("persistent_weaknesses", [])
    weaknesses_text = "\n- ".join(weaknesses) if weaknesses else "None specified"

    memory_injection = f"""
# CURRENT ACTIVE USER STATE (INJECTED MEMORY - DO NOT REPEAT TO USER)
- Target Level: {level}
- Active Weaknesses to Watch & Correct:
- {weaknesses_text}
"""
    return f"{base_prompt}\n{memory_injection}".strip()

def parse_tutor_output(raw_text: str) -> Dict[str, Optional[str]]:
    conv_pattern = r"\[CONVERSATION\]\s*([\s\S]*?)(?=\[FEEDBACK\]|$)"
    feed_pattern = r"\[FEEDBACK\]\s*([\s\S]*)"

    conv_match = re.search(conv_pattern, raw_text, re.IGNORECASE)
    feed_match = re.search(feed_pattern, raw_text, re.IGNORECASE)

    speech_text = conv_match.group(1).strip() if conv_match else raw_text.strip()
    feedback_text = feed_match.group(1).strip() if feed_match else None

    # Clean leftover markdown tags
    speech_text = re.sub(r"^\[CONVERSATION\]", "", speech_text, flags=re.IGNORECASE).strip()
    if feedback_text:
        feedback_text = re.sub(r"^\[FEEDBACK\]", "", feedback_text, flags=re.IGNORECASE).strip()
        if not feedback_text or feedback_text.lower() in ["none", "none.", "n/a", "no mistakes detected."]:
            feedback_text = None

    return {
        "conversation": speech_text,
        "feedback": feedback_text
    }

async def call_gemini_api(system_instruction: str, user_message: str, api_key: str, audio_b64: Optional[str] = None, mime_type: str = "audio/webm") -> str:
    """Performs real call to Google Gemini 1.5/2.5 Flash API with detailed diagnostic logging."""
    parts: List[Dict[str, Any]] = []
    
    if audio_b64:
        parts.append({
            "inline_data": {
                "mime_type": mime_type,
                "data": audio_b64
            }
        })
        parts.append({
            "text": "Listen to the user's spoken audio carefully. Respond conversing naturally as LingoVibe and identify any grammar/vocabulary errors strictly according to the output format."
        })
    else:
        parts.append({"text": user_message})

    # Direct official Google Generative Language REST Endpoint
    model_name = "gemini-1.5-flash"
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent?key={api_key}"
    
    payload = {
        "system_instruction": {
            "parts": [{"text": system_instruction}]
        },
        "contents": [
            {
                "role": "user",
                "parts": parts
            }
        ],
        "generationConfig": {
            "temperature": 0.7,
            "maxOutputTokens": 400
        }
    }

    # Prompt Size Logging
    payload_str = json.dumps(payload)
    prompt_size_chars = len(system_instruction) + (len(user_message) if user_message else 0)
    print(f"[PROMPT SIZE] Estimated Prompt Characters: {prompt_size_chars} chars (~{prompt_size_chars // 4} tokens)")

    req = urllib.request.Request(
        url,
        data=payload_str.encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST"
    )

    def _sync_post():
        try:
            with urllib.request.urlopen(req, timeout=20) as response:
                status_code = response.getcode()
                response_body = response.read().decode("utf-8")
                return status_code, json.loads(response_body)
        except urllib.error.HTTPError as http_err:
            error_body = http_err.read().decode("utf-8") if http_err.fp else ""
            print(f"[LLM ERROR] HTTP {http_err.code} from Google Gemini API:")
            print(error_body)
            raise RuntimeError(f"Google API HTTP {http_err.code}: {error_body}")
        except urllib.error.URLError as url_err:
            print(f"[LLM ERROR] Network Connection Error: {url_err.reason}")
            raise RuntimeError(f"Network error connecting to Gemini API: {url_err.reason}")

    status_code, res_data = await asyncio.to_thread(_sync_post)

    candidates = res_data.get("candidates", [])
    if candidates:
        parts_res = candidates[0].get("content", {}).get("parts", [])
        if parts_res:
            raw_text = parts_res[0].get("text", "").strip()
            print(f"[LLM RAW RESPONSE]:\n{raw_text}\n" + "-"*50)
            return raw_text

    raise RuntimeError("Google Gemini API returned an empty candidate list or blocked content.")

async def generate_tutor_response(user_message: str = "", current_level: str = "B2", audio_b64: Optional[str] = None, mime_type: str = "audio/webm") -> str:
    """Core function that triggers pure LLM generation with zero static/mock fallbacks."""
    api_key = get_api_key()
    
    # Log incoming input
    if audio_b64:
        print(f"[INPUT RECOGIDO] 🎙️ Audio Blob ({mime_type}) received: {len(audio_b64)} base64 chars")
    else:
        print(f"[INPUT RECOGIDO] 💬 Text: \"{user_message}\"")

    if not api_key:
        error_msg = "API Key not configured. Please set GEMINI_API_KEY or API_KEY in your environment or in a .env file."
        print(f"[LLM ERROR] {error_msg}")
        raise ValueError(error_msg)

    system_prompt = build_contextual_prompt(current_level)

    try:
        raw_output = await call_gemini_api(
            system_instruction=system_prompt,
            user_message=user_message,
            api_key=api_key,
            audio_b64=audio_b64,
            mime_type=mime_type
        )
        return raw_output
    except Exception as e:
        print(f"[LLM ERROR] Exception Traceback:")
        traceback.print_exc()
        raise e

def increment_user_turns():
    profile = load_memory_profile()
    stats = profile.get("stats", {})
    stats["total_turns"] = stats.get("total_turns", 0) + 1
    profile["stats"] = stats
    save_memory_profile(profile)
    return stats

# --- PWA & Endpoints ---

@app.get("/", response_class=HTMLResponse)
async def serve_index():
    if os.path.exists(INDEX_HTML_PATH):
        return FileResponse(INDEX_HTML_PATH)
    return HTMLResponse("<h1>LingoVibe</h1><p>index.html not found</p>")

@app.get("/manifest.json")
async def serve_manifest():
    if os.path.exists(MANIFEST_PATH):
        return FileResponse(MANIFEST_PATH, media_type="application/manifest+json")
    raise HTTPException(status_code=404, detail="manifest.json not found")

@app.get("/service-worker.js")
async def serve_service_worker():
    if os.path.exists(SERVICE_WORKER_PATH):
        return FileResponse(SERVICE_WORKER_PATH, media_type="application/javascript")
    raise HTTPException(status_code=404, detail="service-worker.js not found")

@app.get("/api/profile")
async def get_profile():
    return load_memory_profile()

@app.post("/api/profile/level")
async def update_level(data: Dict[str, str]):
    level = data.get("level", "B2")
    profile = load_memory_profile()
    profile["current_level"] = level
    save_memory_profile(profile)
    return {"status": "ok", "current_level": level}

class ChatRequest(BaseModel):
    message: Optional[str] = ""
    level: Optional[str] = "B2"
    audio_b64: Optional[str] = None
    mime_type: Optional[str] = "audio/webm"

@app.post("/api/chat")
async def chat_endpoint(req: ChatRequest):
    try:
        raw_response = await generate_tutor_response(
            user_message=req.message or "",
            current_level=req.level or "B2",
            audio_b64=req.audio_b64,
            mime_type=req.mime_type or "audio/webm"
        )
        parsed = parse_tutor_output(raw_response)
        updated_stats = increment_user_turns()
        return {
            "raw": raw_response,
            "conversation": parsed["conversation"],
            "feedback": parsed["feedback"],
            "stats": updated_stats
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.websocket("/ws/voice-chat")
async def websocket_voice_chat(websocket: WebSocket):
    await websocket.accept()
    profile = load_memory_profile()
    current_level = profile.get("current_level", "B2")
    
    # Check API key on connection and notify
    api_key = get_api_key()
    has_key = api_key is not None

    await websocket.send_json({
        "type": "connected",
        "profile": profile,
        "api_key_configured": has_key,
        "message": "Connected to LingoVibe Real-Time Voice Engine" if has_key else "Connected, but API Key is missing on server."
    })

    try:
        while True:
            data = await websocket.receive_json()
            event_type = data.get("type", "message")

            if event_type == "set_level":
                current_level = data.get("level", "B2")
                profile = load_memory_profile()
                profile["current_level"] = current_level
                save_memory_profile(profile)
                print(f"[PROFILE] Level updated to: {current_level}")
                await websocket.send_json({
                    "type": "level_updated",
                    "current_level": current_level
                })
                continue

            user_text = data.get("text", "").strip()
            audio_b64 = data.get("audio_b64")
            mime_type = data.get("mime_type", "audio/webm")

            if not user_text and not audio_b64:
                continue

            try:
                raw_response = await generate_tutor_response(
                    user_message=user_text,
                    current_level=current_level,
                    audio_b64=audio_b64,
                    mime_type=mime_type
                )
                parsed = parse_tutor_output(raw_response)
                updated_stats = increment_user_turns()

                await websocket.send_json({
                    "type": "tutor_response",
                    "raw": raw_response,
                    "conversation": parsed["conversation"],
                    "feedback": parsed["feedback"],
                    "stats": updated_stats,
                    "current_level": current_level
                })
            except Exception as err:
                print(f"[WS ERROR DISPATCH]: Sending error event to client: {err}")
                await websocket.send_json({
                    "type": "error",
                    "message": f"LLM Generation Error: {str(err)}"
                })

    except WebSocketDisconnect:
        print("[WS] Client disconnected normally.")
    except Exception as e:
        print(f"[WS FATAL ERROR]: {e}")
