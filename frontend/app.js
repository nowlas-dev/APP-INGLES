/**
 * LingoBeats / LingoVibe — frontend/app.js
 * Bootstrap, WebSocket con soporte binario y enrutamiento reactivo de eventos.
 * Conecta UIModule + AudioModule con el Orquestador Node.js y la API de Letras LRCLIB.
 */

"use strict";

const AppModule = (() => {
  const WS_URL          = `ws://${location.host}/ws`;
  const RECONNECT_DELAY = 3000;

  let ws           = null;
  let sessionId    = null;
  let isConnected  = false;
  let reconnecting = false;

  // Estado de la voz y actitud del tutor
  const STORAGE_KEY_VOICE = "selected_tutor_voice";
  const LEGACY_STORAGE_KEY_VOICE = "lingobeats_tutor_voice";
  const STORAGE_KEY_ATTITUDE = "lingobeats_tutor_attitude";

  let currentVoiceId      = localStorage.getItem(STORAGE_KEY_VOICE) || localStorage.getItem(LEGACY_STORAGE_KEY_VOICE) || "dalia";
  let currentAttitude     = localStorage.getItem(STORAGE_KEY_ATTITUDE) || "funny";
  let previewAudioObj     = null;

  // Estado de la canción y karaoke sincronizado
  let currentTrackName  = "Yesterday";
  let currentArtistName = "The Beatles";
  let currentStanzas    = [];
  let currentStanzaIdx  = 0;
  let playbackRate      = 1.0;
  let isSpeakingStanza  = false;

  // ── Bootstrap ────────────────────────────────────────────
  async function init() {
    UIModule.init();
    currentVoiceId = localStorage.getItem(STORAGE_KEY_VOICE) || localStorage.getItem(LEGACY_STORAGE_KEY_VOICE) || "dalia";
    currentAttitude = localStorage.getItem(STORAGE_KEY_ATTITUDE) || "funny";
    UIModule.setSelectedVoice(currentVoiceId);
    UIModule.setSelectedAttitude(currentAttitude);
    _setupEventListeners();
    _connect();
    // Cargar automáticamente canción inicial (Yesterday)
    await _loadSongLyrics(currentTrackName, currentArtistName);
  }

  // ── WebSocket ────────────────────────────────────────────
  function _connect() {
    if (ws && ws.readyState === WebSocket.OPEN) return;

    UIModule.addSystemMessage("Conectando al servidor…", "info");
    ws = new WebSocket(WS_URL);
    ws.binaryType = "arraybuffer"; // Habilitar soporte de transporte binario nativo

    ws.onopen = () => {
      isConnected  = true;
      reconnecting = false;
      console.log("[APP] 🔌 WebSocket conectado con soporte ArrayBuffer.");
      _sendMessage("set_voice", { voice_id: currentVoiceId, voice: currentVoiceId });
      _sendMessage("set_attitude", { attitude: currentAttitude });
    };

    ws.onmessage = async (event) => {
      // Si el mensaje recibido es binario directo (ej. audio TTS streaming)
      if (event.data instanceof ArrayBuffer) {
        console.log(`[APP] 🔊 Audio binario recibido: ${event.data.byteLength} bytes.`);
        await AudioModule.playAudioBinary(event.data);
        UIModule.setState("IDLE");
        return;
      }

      let msg;
      try {
        msg = JSON.parse(event.data);
      } catch {
        console.warn("[APP] Mensaje WS no estructurado:", event.data);
        return;
      }
      _handleMessage(msg);
    };

    ws.onclose = () => {
      isConnected = false;
      UIModule.setState("IDLE");
      UIModule.addSystemMessage("Desconectado. Reconectando…", "warning");
      if (!reconnecting) {
        reconnecting = true;
        setTimeout(_connect, RECONNECT_DELAY);
      }
    };

    ws.onerror = (err) => {
      console.error("[APP] WS error:", err);
    };
  }

  // ── Handlers de Mensajes Entrantes ───────────────────────
  function _handleMessage(msg) {
    const { type } = msg;

    switch (type) {
      case "connected": {
        sessionId = msg.sessionId;
        UIModule.setState("IDLE");
        UIModule.addSystemMessage(
          `✅ Conectado — Sesión #${sessionId || "activa"} | Nivel: ${msg.profile?.current_level || "B2"}`,
          "success"
        );
        if (msg.profile) {
          UIModule.setSelectedLevel(msg.profile.current_level || "B2");
          UIModule.updateStats(msg.profile.stats);
        }
        break;
      }

      case "state_change": {
        UIModule.setState(msg.state);
        break;
      }

      case "tutor_response": {
        if (msg.transcript && msg.transcript !== msg.conversation) {
          UIModule.addSystemMessage(`🎙️ Transcrito: "${msg.transcript}"`, "transcript");
        }

        UIModule.addTutorBubble(msg.conversation || "");
        UIModule.showFeedback(msg.feedback || null, msg.discrepancies || []);

        // Reproducir audio con decodificación Web Audio API
        if (msg.audio_b64) {
          AudioModule.playAudioB64(msg.audio_b64, msg.audio_mime || "audio/mpeg")
            .then(() => UIModule.setState("IDLE"))
            .catch((err) => {
              console.warn("[APP] TTS playback error:", err);
              UIModule.setState("IDLE");
            });
        } else if (msg.conversation) {
          const url = `/api/ai/tts/preview?voice=${encodeURIComponent(currentVoiceId)}&voice_id=${encodeURIComponent(currentVoiceId)}&text=${encodeURIComponent(msg.conversation)}`;
          AudioModule.playAudioUrl(url)
            .then(() => UIModule.setState("IDLE"))
            .catch((err) => {
              console.warn("[APP] TTS fallback error:", err);
              UIModule.setState("IDLE");
            });
        } else {
          UIModule.setState("IDLE");
        }

        if (msg.total_latency_ms) {
          console.log(`[APP] ⏱️ Latencia: Total=${msg.total_latency_ms}ms | STT=${msg.stt_latency_ms || 0}ms | LLM=${msg.llm_latency_ms || 0}ms`);
        }
        break;
      }

      case "scoring_result": {
        UIModule.showFeedback(
          `Precisión Fonética: ${msg.accuracy_score}% (WER: ${msg.wer})`,
          msg.discrepancies || []
        );
        break;
      }

      case "level_updated": {
        UIModule.showToast(`Nivel actualizado a ${msg.cefr_level}`, "success");
        break;
      }

      case "error": {
        UIModule.addSystemMessage(`❌ ${msg.message}`, "error");
        UIModule.showToast(msg.message, "error");
        UIModule.setState("IDLE");
        break;
      }

      default:
        console.log("[APP] Evento WS no mapeado:", msg);
    }
  }

  // ── Gestión de Letras Sincronizadas (LRCLIB) ──────────────
  async function _loadSongLyrics(track, artist = "") {
    try {
      const url = `/api/lyrics?track=${encodeURIComponent(track)}&artist=${encodeURIComponent(artist)}`;
      const res = await fetch(url);
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = await res.json();

      if (data && data.stanzas && data.stanzas.length > 0) {
        currentStanzas   = data.stanzas;
        currentStanzaIdx = 0;
        currentTrackName = data.track_name || track;
        currentArtistName = data.artist_name || artist || "Artista";

        UIModule.setTrackInfo(currentTrackName, currentArtistName, "B2 Intermediate");
        _updateKaraokeView();
        UIModule.showToast(`Cargada: "${currentTrackName}" (${data.stanzas.length} estrofas)`, "success");
      } else {
        UIModule.showToast(`No se encontraron letras sincronizadas para "${track}"`, "warning");
      }
    } catch (err) {
      console.warn("[APP] No se pudieron cargar letras de LRCLIB:", err.message);
    }
  }

  function _updateKaraokeView() {
    if (!currentStanzas || currentStanzas.length === 0) return;

    const curr = currentStanzas[currentStanzaIdx];
    const prev = currentStanzaIdx > 0 ? currentStanzas[currentStanzaIdx - 1] : null;
    const next = currentStanzaIdx < currentStanzas.length - 1 ? currentStanzas[currentStanzaIdx + 1] : null;

    UIModule.renderKaraokeStanza(curr, prev, next, currentStanzas.length);
  }

  function _nextStanza() {
    if (currentStanzaIdx < currentStanzas.length - 1) {
      currentStanzaIdx++;
      _updateKaraokeView();
      if (isSpeakingStanza) _playCurrentStanzaSpeech();
    }
  }

  function _prevStanza() {
    if (currentStanzaIdx > 0) {
      currentStanzaIdx--;
      _updateKaraokeView();
      if (isSpeakingStanza) _playCurrentStanzaSpeech();
    }
  }

  function _togglePlayStanza() {
    if (isSpeakingStanza) {
      AudioModule.stopPlayback();
      isSpeakingStanza = false;
      UIModule.setPlayButtonState(false);
    } else {
      _playCurrentStanzaSpeech();
    }
  }

  function _playCurrentStanzaSpeech() {
    if (!currentStanzas || !currentStanzas[currentStanzaIdx]) return;
    const textToSpeak = (currentStanzas[currentStanzaIdx].text || "").trim();
    if (!textToSpeak) return;

    AudioModule.stopPlayback();
    isSpeakingStanza = true;
    UIModule.setPlayButtonState(true);

    const url = `/api/ai/tts/preview?voice=${encodeURIComponent(currentVoiceId)}&voice_id=${encodeURIComponent(currentVoiceId)}&text=${encodeURIComponent(textToSpeak)}`;
    AudioModule.playAudioUrl(url)
      .then(() => {
        isSpeakingStanza = false;
        UIModule.setPlayButtonState(false);
        UIModule.showToast("🎧 Estrofa completada. ¡Ahora presiona el micrófono para practicar!", "info");
      })
      .catch((err) => {
        console.warn("[APP] Error al reproducir estrofa con TTS neuronal:", err);
        isSpeakingStanza = false;
        UIModule.setPlayButtonState(false);
      });
  }

  function _cycleSpeed() {
    const speeds = [0.8, 1.0, 1.2];
    const idx = speeds.indexOf(playbackRate);
    playbackRate = speeds[(idx + 1) % speeds.length];

    const speedBtn = document.getElementById("player-speed-btn");
    if (speedBtn) speedBtn.textContent = `${playbackRate.toFixed(1)}x`;
    UIModule.showToast(`Velocidad: ${playbackRate.toFixed(1)}x`, "info");

    if (isSpeakingStanza) {
      _playCurrentStanzaSpeech();
    }
  }

  // ── Envío de Mensajes ────────────────────────────────────
  function _sendMessage(type, payload) {
    if (!ws || ws.readyState !== WebSocket.OPEN) {
      UIModule.showToast("Sin conexión al servidor", "error");
      return;
    }
    ws.send(JSON.stringify({
      type,
      voice_id: currentVoiceId,
      voice: currentVoiceId,
      attitude: currentAttitude,
      ...payload
    }));
  }

  function _sendBinary(arrayBuffer) {
    if (!ws || ws.readyState !== WebSocket.OPEN) {
      UIModule.showToast("Sin conexión al servidor", "error");
      return;
    }
    // Envío directo en memoria sin Base64
    ws.send(arrayBuffer);
  }

  // ── Interacción por Texto ────────────────────────────────
  function _sendText() {
    const text = UIModule.getInputText();
    if (!text) return;
    UIModule.addUserBubble(text);
    UIModule.clearInput();
    UIModule.showFeedback(null);
    UIModule.setState("PROCESSING");
    _sendMessage("message", { text });
  }

  // ── Interacción por Voz (ArrayBuffer Directo) ────────────
  async function _toggleRecording() {
    if (AudioModule.isRecording()) {
      AudioModule.stopRecording();
      UIModule.setRecordingActive(false);
      UIModule.setAudioLevel(0);
      return;
    }

    try {
      await AudioModule.init();
    } catch (err) {
      UIModule.showToast(`Micrófono: ${err.message}`, "error");
      return;
    }

    UIModule.setRecordingActive(true);
    UIModule.setState("RECORDING");
    _sendMessage("set_state", { state: "RECORDING" });

    AudioModule.startRecording(
      // onBinaryChunk: ArrayBuffer directo al finalizar grabación (Item 9)
      (arrayBuffer, mimeType) => {
        UIModule.setState("PROCESSING");
        UIModule.addUserBubble("🎙️ [audio enviado]");
        UIModule.showFeedback(null);

        // Transmisión binaria instantánea
        _sendBinary(arrayBuffer);
      },
      // onLevel: visualizador y ondas concéntricas
      (level) => UIModule.setAudioLevel(level)
    );
  }

  function _onLevelChange(level) {
    _sendMessage("set_level", { level });
  }

  // ── Gestión del Selector de Tutores y Voces ─────────────
  function _onVoiceChange(newVoiceId) {
    if (!newVoiceId) return;
    currentVoiceId = newVoiceId.toLowerCase().trim();
    localStorage.setItem(STORAGE_KEY_VOICE, currentVoiceId);
    localStorage.setItem(LEGACY_STORAGE_KEY_VOICE, currentVoiceId);
    UIModule.updateTutorChip(currentVoiceId);
    _sendMessage("set_voice", { voice_id: currentVoiceId, voice: currentVoiceId });
    UIModule.showToast(`Tutor: ${currentVoiceId.toUpperCase()} activado`, "info");
  }

  // ── Gestión del Selector de Actitud Pedagógica ───────────
  function _onAttitudeChange(newAttitude) {
    if (!newAttitude) return;
    currentAttitude = newAttitude.toLowerCase().trim();
    localStorage.setItem(STORAGE_KEY_ATTITUDE, currentAttitude);
    UIModule.updateAttitudeChip(currentAttitude);
    _sendMessage("set_attitude", { attitude: currentAttitude });
    const labels = { friendly: "Amable", funny: "Bromista", strict: "Exigente" };
    UIModule.showToast(`Actitud del tutor: ${labels[currentAttitude] || currentAttitude}`, "info");
  }

  async function _playVoicePreview() {
    try {
      UIModule.setPreviewPlaying(true);
      AudioModule.stopPlayback();
      const url = `/api/ai/tts/preview?voice=${encodeURIComponent(currentVoiceId)}&voice_id=${encodeURIComponent(currentVoiceId)}&t=${Date.now()}`;
      await AudioModule.playAudioUrl(url);
    } catch (err) {
      console.warn("[APP] Error en reproducción de vista previa:", err);
      UIModule.showToast("No se pudo reproducir la muestra de voz.", "warning");
    } finally {
      UIModule.setPreviewPlaying(false);
    }
  }

  /**
   * Salta y reproduce la estrofa indicada por índice (0-based).
   * @param {number} [index=0]
   */
  async function playStanza(index = 0) {
    if (!currentStanzas || currentStanzas.length === 0) return;
    currentStanzaIdx = Math.max(0, Math.min(index, currentStanzas.length - 1));
    _updateKaraokeView();
    UIModule.setState("PLAYING_STANZA");
    _sendMessage("set_state", { state: "PLAYING_STANZA", stanza_idx: currentStanzaIdx });

    // Sincronizar con SyncPlayer o reproducir síntesis fonética de la estrofa
    const syncPlayer = AudioModule.getPlayer();
    if (syncPlayer && syncPlayer.stanzas && syncPlayer.stanzas.length > 0) {
      syncPlayer.playStanza(currentStanzaIdx);
    } else {
      _playCurrentStanzaSpeech();
    }
  }

  /**
   * Flujo de inicio de canción con saludo contextual del tutor.
   * 1. Coloca la UI en estado "El tutor te está dando la bienvenida...".
   * 2. Petición fetch a /api/session/welcome?song=...&attitude=...&voice=...
   * 3. Decodifica el audio MP3 mediante AudioContext (Web Audio API).
   * 4. Espera a que termine la locución del tutor (onended).
   * 5. Inicia automáticamente la reproducción de la primera estrofa (playStanza(0)).
   */
  async function startSongWithWelcome() {
    UIModule.setStartSongLoading(true);

    try {
      // 1. Coloca la UI en estado "El tutor te está dando la bienvenida..."
      UIModule.setState("INTRO_GREETING");
      UIModule.showToast("El tutor te está dando la bienvenida…", "info");
      _sendMessage("set_state", { state: "INTRO_GREETING" });

      // 2. Hace una petición fetch a /api/session/welcome
      const songTitle = currentTrackName || "Yesterday";
      const artist = currentArtistName || "The Beatles";
      const welcomeUrl = `/api/session/welcome?song=${encodeURIComponent(songTitle)}&artist=${encodeURIComponent(artist)}&attitude=${encodeURIComponent(currentAttitude)}&voice=${encodeURIComponent(currentVoiceId)}`;

      const response = await fetch(welcomeUrl);
      if (!response.ok) {
        throw new Error(`Error en servidor (${response.status})`);
      }

      // Si el servidor envía el texto del saludo en los encabezados, reflejarlo en el chat
      const greetingText = response.headers.get("x-greeting-text");
      if (greetingText) {
        UIModule.addTutorBubble(greetingText);
      }

      // 3 y 4. Decodifica el audio MP3 mediante AudioContext y espera a que termine (onended)
      const arrayBuffer = await response.arrayBuffer();
      await AudioModule.playAudioBinary(arrayBuffer);

      // 5. Inicia automáticamente la reproducción de la primera estrofa
      await playStanza(0);
    } catch (err) {
      console.warn("[APP] Error en saludo de bienvenida inicial:", err);
      UIModule.showToast("Iniciando primera estrofa directamente…", "warning");
      UIModule.setState("IDLE");
      await playStanza(0);
    } finally {
      UIModule.setStartSongLoading(false);
    }
  }

  // ── Event Listeners ──────────────────────────────────────
  function _setupEventListeners() {
    document.getElementById("send-btn")?.addEventListener("click", _sendText);

    document.getElementById("text-input")?.addEventListener("keydown", (e) => {
      if (e.key === "Enter" && !e.shiftKey) {
        e.preventDefault();
        _sendText();
      }
    });

    document.getElementById("record-btn")?.addEventListener("click", _toggleRecording);

    document.getElementById("level-select")?.addEventListener("change", (e) => {
      _onLevelChange(e.target.value);
    });

    // Selector de tutor y voz neuronal
    const voiceDropdown = document.getElementById("tutor-voice-select") || document.getElementById("voice-selector-dropdown");
    if (voiceDropdown) {
      voiceDropdown.addEventListener("change", (e) => {
        _onVoiceChange(e.target.value);
      });
    }

    // Selector de actitud pedagógica del tutor
    const attitudeDropdown = document.getElementById("tutor-attitude-select");
    if (attitudeDropdown) {
      attitudeDropdown.addEventListener("change", (e) => {
        _onAttitudeChange(e.target.value);
      });
    }

    // Botón de previsualización de voz
    const previewBtn = document.getElementById("voice-preview-btn");
    if (previewBtn) {
      previewBtn.addEventListener("click", _playVoicePreview);
    }

    // Botón Comenzar Canción
    const startSongBtn = document.getElementById("start-song-btn");
    if (startSongBtn) {
      startSongBtn.addEventListener("click", startSongWithWelcome);
    }

    document.getElementById("clear-btn")?.addEventListener("click", () => {
      const container = document.getElementById("chat-container");
      if (container) container.textContent = "";
      UIModule.showFeedback(null);
    });

    // Controles del reproductor
    document.getElementById("player-play-btn")?.addEventListener("click", _togglePlayStanza);
    document.getElementById("player-next-btn")?.addEventListener("click", _nextStanza);
    document.getElementById("player-prev-btn")?.addEventListener("click", _prevStanza);
    document.getElementById("player-speed-btn")?.addEventListener("click", _cycleSpeed);

    // Clic en estrofas adyacentes para saltar
    document.getElementById("stanza-prev")?.addEventListener("click", _prevStanza);
    document.getElementById("stanza-next")?.addEventListener("click", _nextStanza);

    // Búsqueda de canciones en LRCLIB
    const searchInput = document.getElementById("song-search-input");
    if (searchInput) {
      searchInput.addEventListener("keydown", (e) => {
        if (e.key === "Enter") {
          e.preventDefault();
          const query = searchInput.value.trim();
          if (query) {
            let parts = query.split("-");
            let track = parts[0].trim();
            let artist = parts[1] ? parts[1].trim() : "";
            _loadSongLyrics(track, artist);
          }
        }
      });
    }
  }

  return {
    init,
    playStanza,
    startSongWithWelcome,
  };
})();

// Exportar globalmente para pruebas y acceso modular en el navegador
window.AppModule = AppModule;
window.playStanza = (idx = 0) => AppModule.playStanza(idx);

document.addEventListener("DOMContentLoaded", () => AppModule.init());
