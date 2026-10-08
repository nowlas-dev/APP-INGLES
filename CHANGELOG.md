# Changelog

Todos los cambios notables en este proyecto serán documentados en este archivo.

El formato está basado en [Keep a Changelog](https://keepachangelog.com/es-ES/1.1.0/),
y este proyecto se adhiere a [Semantic Versioning](https://semver.org/lang/es/).

---

## [Unreleased]

### Planned
- Separación de stems en tiempo real con Demucs (`htdemucs`) para aislamiento de pista instrumental.
- Sistema de repaso espaciado (SRS) de fonemas con mayor tasa de error por usuario.
- Modo sin conexión completo integrando `piper-tts` / `kokoro-onnx` sin depender de internet.

---

## [v2.1.0] - 2026-10-08

### Added
- **Selector de Actitud del Tutor en Frontend:** Dropdown estilizado Glassmorphism en la barra superior junto al selector de voces, con soporte para 3 actitudes pedagógicas (`friendly`, `funny`, `strict`) y persistencia en `localStorage.getItem('lingobeats_tutor_attitude')`.
- **Flujo de Bienvenida con AudioContext y Disparo Automático:** Botón "Comenzar Canción", estado reactivo `INTRO_GREETING` ("El tutor te está dando la bienvenida..."), decodificación Web Audio API y transición fluida a `playStanza(0)`.
- **Proxy Gateway de Streaming de Bienvenida en Node.js:** Endpoint `GET /api/session/welcome` en `backend-core` y `orchestrator` con proxy HTTP streaming binario (`audio/mpeg`) hacia FastAPI y fallback de contingencia.
- **Expansión de Máquina de Estados de Sesión:** Nuevos estados `INTRO_GREETING` y `PLAYING_STANZA` en `sessionStore.js` con persistencia dinámica de `attitude` y `voice` para el flujo conversacional.
- **Saludo Contextual de Bienvenida con Personalidad:** Endpoint `GET /api/ai/session/welcome` que genera saludos personalizados según canción y artista con catálogo dinámico de 3 actitudes (`friendly`, `funny`, `strict`) y modulación prosódica en tiempo real en `edge-tts`.
- **Síntesis Neuronal en Generación Textual:** Síntesis en memoria en `/generate` retornando `audio_b64` a 24kHz/48kHz estéreo para eliminar cualquier caída en modo solo-texto.
- **Reproducción Web Audio API Pura:** Implementación de `AudioModule.playAudioUrl()` utilizando `AudioContext.decodeAudioData()` y control estricto de buffers activos.
- **Suite de Pruebas Automatizadas de Voz:** Scripts `tests/test_tts_voices.py` y `tests/test_fastapi_endpoints.py` validando los endpoints y las 5 personalidades de voz.

### Changed
- **Eradicación Total de Web Speech API:** Eliminación completa de llamadas a `window.speechSynthesis` y `SpeechSynthesisUtterance` en el frontend (`app.js`, `ui.js`), sustituidas por streaming neural vía backend.
- **Normalización de Voces en edge-tts:** Corregida asignación de `elena` a `es-ES-ElviraNeural` (con soporte transparente de alias) para prevenir fallos y rechazos de parámetros en Microsoft Edge TTS.
- **Persistencia y Selección de Voz:** Unificación de claves de almacenamiento `selected_tutor_voice` con retrocompatibilidad hacia `lingobeats_tutor_voice`.

---

## [v2.0.0] - 2026-10-07

### Added
- **Selector de Tutores Vocales:** Menú desplegable en la barra superior con persistencia en `localStorage` y soporte para 5 personalidades neuronales (`dalia`, `jorge`, `paloma`, `alvaro`, `elena`).
- **Endpoint de Previsualización de Voz:** `GET /api/ai/tts/preview` para probar el timbre y prosodia antes de iniciar la sesión.
- **Pipeline de Audio Binario Puro:** Transmisión de buffers crudos `audio/webm` sobre WebSocket directo, reduciendo la sobrecarga de memoria un 33%.
- **Fallback Automático de LLM:** Conmutación por timeout (4.0s) de Ollama local (`llama3:8b`) hacia Gemini API (`gemini-1.5-flash`).
- **Control de Ingestión de Letras:** Cliente de integración hacia API de LRCLIB con parser de marcas temporales `[mm:ss.xx]`.

### Changed
- **Motor TTS Reestructurado:** Sustituido el sintetizador robótico estándar por voces neuronales de alta fidelidad vía `edge-tts` con modulación de velocidad y tono adaptada al aprendizaje de idiomas.
- **Centralización de Base de Datos:** Persistencia migrada de Python (`aiosqlite`) a Node.js (`node:sqlite`) con modo `WAL` activo y aislamiento transaccional.
- **Rediseño de Interfaz (SPA):** Nueva interfaz con estética oscura y Glassmorphism, contenedor con visualización tipo karaoke didáctico y barra de control inferior adaptativa.

### Fixed
- **Deadlock de Máquina de Estados:** Desbloqueadas las transiciones bloqueantes `IDLE -> PROCESSING` en `sessionStore.js` y `server.js`.
- **Fuga de Archivos Temporales en STT:** Eliminado `NamedTemporaryFile(delete=False)` en `whisper_stt.py`, procesando el audio en memoria mediante buffers virtuales.
- **Persistencia de Turnos:** Corregido el valor nulo (`None`) del campo `audio_path` en los registros de la tabla `turns`.
- **Fugas de Memoria en Micrófono:** Detención explícita de pistas en `MediaStream` al pausar o finalizar turnos de grabación.

---

## [v1.0.0] - 2026-09-15

### Added
- **Arquitectura Base Híbrida:** Estructura modular dividida en `frontend/` (Vanilla JS SPA), `backend-core/` (Node.js/Express) y `backend-ai/` (FastAPI).
- **Esquema Relacional SQLite:** Tablas iniciales para gestión de canciones, estrofas, progreso de usuario y registro de errores fonéticos.
- **Motor de Transcripción Local:** Integración de `faster-whisper` (`base.en` / `small.en`) con cuantización `int8` y filtro VAD de silencios.
- **Auditoría Fonética Básica:** Algoritmo de comparación textual mediante distancia Levenshtein y Word Error Rate (WER).
- **Agente Pedagógico Local:** Integración con Ollama para corrección física de pronunciación y preguntas de comprensión contextual por estrofa.
- **Reproductor Sincronizado Inicial:** Pausa automática por marcas de tiempo en el elemento de audio HTML5.
