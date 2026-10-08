# LingoVibe v2 — AI Voice Tutor (Arquitectura Multicapa)

LingoVibe es un tutor interactivo de idiomas asistido por IA. La versión 2 refactoriza el monolito original en una arquitectura de tres capas con persistencia relacional, motor de audio local y orquestador de estados.

---

## 🏗️ Arquitectura

```
┌─────────────────────────────────────────────────────────────┐
│  Frontend SPA (Vanilla JS)          http://localhost:3000   │
│  frontend/index.html + app.js + audio.js + ui.js            │
└───────────────────────┬─────────────────────────────────────┘
                        │ WebSocket + REST
┌───────────────────────▼─────────────────────────────────────┐
│  Orquestador (Node.js / Express)    :3000                   │
│  orchestrator/server.js                                     │
│  State Machine: IDLE→LISTENING→PROCESSING→SPEAKING→IDLE     │
└───────────────────────┬─────────────────────────────────────┘
                        │ HTTP REST
┌───────────────────────▼─────────────────────────────────────┐
│  Motor de Audio (Python / FastAPI)  :8000                   │
│  audio_engine/main.py                                       │
│  ├── Whisper STT   (faster-whisper, local)                  │
│  ├── Ollama LLM    (local, primer intento)                  │
│  ├── Gemini API    (cloud, fallback)                        │
│  └── edge-tts      (TTS Microsoft, sin costo)               │
└───────────────────────┬─────────────────────────────────────┘
                        │ aiosqlite (async)
┌───────────────────────▼─────────────────────────────────────┐
│  SQLite Database    db/lingvovibe.db                        │
│  Tablas: users, sessions, turns, weaknesses, vocabulary     │
└─────────────────────────────────────────────────────────────┘
```

---

## 📁 Estructura del Proyecto

```
APP IDIOMAS/
├── .env                        # Variables de entorno (ambos servicios)
├── start_audio_engine.bat      # ▶ Arrancar Motor de Audio (Python :8000)
├── start_orchestrator.bat      # ▶ Arrancar Orquestador (Node :3000)
│
├── db/
│   ├── schema.sql              # DDL SQLite (tablas + triggers + datos iniciales)
│   ├── database.py             # Módulo async (aiosqlite) con todas las queries
│   └── lingvovibe.db           # Base de datos (auto-creada en el primer arranque)
│
├── audio_engine/
│   ├── main.py                 # FastAPI app :8000
│   ├── whisper_stt.py          # STT local con faster-whisper
│   ├── ollama_client.py        # Cliente HTTP para Ollama local
│   ├── gemini_client.py        # Cliente Gemini API (fallback cloud)
│   └── tts_engine.py           # TTS con edge-tts / pyttsx3 fallback
│
├── orchestrator/
│   ├── server.js               # Express + WebSocket hub :3000
│   ├── routes/
│   │   ├── profile.js          # GET|POST /api/profile
│   │   ├── sessions.js         # POST /api/session/start|end
│   │   └── chat.js             # POST /api/turn/text|audio
│   ├── state/
│   │   └── sessionStore.js     # State Machine en memoria (Map por client ID)
│   └── package.json
│
├── frontend/
│   ├── index.html              # SPA dark UI con indicadores de estado
│   ├── app.js                  # Bootstrap, WebSocket, routing de eventos
│   ├── audio.js                # MediaRecorder, AnalyserNode, TTS playback
│   └── ui.js                   # DOM, burbujas, feedback panel, toasts
│
├── system_prompt.md            # Definición del rol del tutor IA
├── legacy/                     # Backup de LingoVibe v1
│   ├── backend_service.py
│   └── index.html
└── README.md
```

---

## ⚙️ Requisitos

| Componente | Versión mínima |
|---|---|
| Python | 3.10+ |
| Node.js | 18+ |
| Navegador | Chrome / Edge / Firefox (soporte WebSocket + MediaRecorder) |

### Dependencias Python
```
fastapi uvicorn python-dotenv aiosqlite httpx
faster-whisper edge-tts
```

### Dependencias Node.js (auto-instaladas por `start_orchestrator.bat`)
```
express ws axios cors multer form-data dotenv
```

---

## 🚀 Cómo ejecutar

### 1. Motor de Audio (Terminal 1)
```powershell
# Desde el directorio raíz: APP IDIOMAS\
.\start_audio_engine.bat
```
Disponible en: http://localhost:8000 | Docs: http://localhost:8000/docs

### 2. Orquestador (Terminal 2)
```powershell
.\start_orchestrator.bat
```
Disponible en: http://localhost:3000

### 3. Abrir la app
Navega a **http://localhost:3000** en tu navegador.

---

## 🔌 API Reference

### Audio Engine (:8000)
| Método | Path | Descripción |
|--------|------|-------------|
| `GET` | `/health` | Estado de Whisper, Ollama, Gemini y TTS |
| `GET` | `/api/profile` | Perfil completo del usuario |
| `POST` | `/api/profile/level` | Actualiza nivel CEFR |
| `POST` | `/transcribe` | Audio → transcript (multipart) |
| `POST` | `/generate` | Texto → respuesta tutor (JSON) |
| `POST` | `/synthesize` | Texto → audio MP3 |
| `POST` | `/ingest` | Pipeline completo: audio → STT → LLM → TTS |
| `POST` | `/session/start` | Crea sesión en SQLite |
| `POST` | `/session/end` | Cierra sesión |
| `GET` | `/session/{id}` | Datos de sesión + turnos |

### Orquestador (:3000)
| Método | Path | Descripción |
|--------|------|-------------|
| `WS` | `/ws` | WebSocket principal del frontend |
| `GET` | `/api/profile` | Proxy → Audio Engine |
| `POST` | `/api/profile/level` | Proxy → Audio Engine |
| `POST` | `/api/session/start` | Proxy → Audio Engine |
| `POST` | `/api/session/end` | Proxy → Audio Engine |
| `POST` | `/api/turn/text` | Orquesta turno de texto |
| `POST` | `/api/turn/audio` | Orquesta turno de audio |
| `GET` | `/api/health` | Estado consolidado |

---

## 🗄️ Base de Datos (SQLite)

| Tabla | Descripción |
|---|---|
| `users` | Perfil del usuario (nivel CEFR, idioma, persona) |
| `sessions` | Sesiones de práctica con timestamps y score |
| `turns` | Cada intercambio usuario↔tutor con latencias |
| `weaknesses` | Debilidades gramaticales con frecuencia |
| `vocabulary` | Banco de palabras con nivel de dominio |
| `user_stats` | Vista con estadísticas agregadas |

---

## 🎙️ Flujo de una conversación por voz

```
Usuario habla → MediaRecorder captura WebM
    → audio_b64 enviado por WebSocket al Orquestador
        → Orquestador → POST /ingest (audio_engine :8000)
            → Whisper STT → transcript
            → Ollama / Gemini → respuesta tutor
            → edge-tts → MP3 bytes
            → Todo guardado en SQLite (turns table)
        ← audio_b64 (MP3) + conversation + feedback
    ← tutor_response enviado por WebSocket al Frontend
        → AudioContext.decodeAudioData() → playback MP3
        → Burbuja de conversación + panel de feedback
```

---

## 📋 Variables de Entorno (`.env`)

```env
GEMINI_API_KEY=...          # Requerida si Ollama no está disponible
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=llama3
WHISPER_MODEL=base          # tiny | base | small | medium | large
WHISPER_DEVICE=cpu          # cpu | cuda
TTS_VOICE=en-US-AriaNeural
AUDIO_ENGINE_PORT=8000
ORCHESTRATOR_PORT=3000
DB_PATH=./db/lingvovibe.db
```

---

## 🔙 Compatibilidad con v1

Los archivos originales de LingoVibe v1 están preservados en `legacy/`.
La v1 sigue funcionable de forma independiente:
```powershell
uvicorn backend_service:app --reload --port 8001
```
