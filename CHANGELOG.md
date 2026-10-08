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
