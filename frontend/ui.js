/**
 * LingoBeats / LingoVibe — frontend/ui.js
 * Módulo de manipulación del DOM y renderizado reactivo 100% sanitizado (Cero XSS).
 * Estética Spotify Lyrics + Duolingo Max, interactividad de palabras y feedback fonético.
 */

"use strict";

const UIModule = (() => {
  let chatContainer, inputField, sendBtn, recordBtn,
      stateIndicator, stateLabel, levelSelect,
      feedbackPanel, visualizerBar, statsEl,
      trackTitleEl, trackArtistEl,
      stanzaPrevEl, stanzaActiveEl, stanzaNextEl,
      stanzaProgressTextEl, songSearchInput, difficultyBadgeEl,
      playerPlayBtn, playerSpeedBtn;

  const STATE_CONFIG = {
    IDLE:          { label: "Listo",            class: "state-idle"          },
    LISTENING:     { label: "Escuchando…",      class: "state-listening"     },
    RECORDING:     { label: "Grabando voz…",    class: "state-listening"     },
    PROCESSING:    { label: "Procesando IA…",   class: "state-processing"    },
    SPEAKING:      { label: "Tutor hablando…",  class: "state-speaking"      },
    FEEDBACK:      { label: "Evaluando…",       class: "state-processing"    },
    COMPREHENSION: { label: "Comprensión",      class: "state-speaking"      },
    ERROR:         { label: "Error",            class: "state-error"         },
  };

  function init() {
    chatContainer        = document.getElementById("chat-container");
    inputField           = document.getElementById("text-input");
    sendBtn              = document.getElementById("send-btn");
    recordBtn            = document.getElementById("record-btn");
    stateIndicator       = document.getElementById("state-indicator");
    stateLabel           = document.getElementById("state-label");
    levelSelect          = document.getElementById("level-select");
    feedbackPanel        = document.getElementById("feedback-panel");
    visualizerBar        = document.getElementById("visualizer-bar");
    statsEl              = document.getElementById("stats");

    trackTitleEl         = document.getElementById("track-title");
    trackArtistEl        = document.getElementById("track-artist");
    stanzaPrevEl         = document.getElementById("stanza-prev");
    stanzaActiveEl       = document.getElementById("karaoke-active-display");
    stanzaNextEl         = document.getElementById("stanza-next");
    stanzaProgressTextEl = document.getElementById("stanza-progress-text");
    songSearchInput      = document.getElementById("song-search-input");
    difficultyBadgeEl    = document.getElementById("song-difficulty-badge");
    playerPlayBtn        = document.getElementById("player-play-btn");
    playerSpeedBtn       = document.getElementById("player-speed-btn");
  }

  function setState(stateName) {
    const cfg = STATE_CONFIG[stateName] || STATE_CONFIG.IDLE;
    if (stateIndicator) {
      stateIndicator.className = `state-dot ${cfg.class}`;
    }
    if (stateLabel) {
      stateLabel.textContent = cfg.label;
    }

    const busy = ["PROCESSING"].includes(stateName);
    if (sendBtn) sendBtn.disabled = busy;
    if (recordBtn) recordBtn.disabled = busy && stateName !== "LISTENING" && stateName !== "RECORDING";
  }

  function addUserBubble(text) {
    _appendBubble("user", text);
  }

  function addTutorBubble(text) {
    _appendBubble("tutor", text);
  }

  function addSystemMessage(text, type = "info") {
    const el = document.createElement("div");
    el.className = `system-msg system-${type}`;
    el.textContent = text;
    _append(el);
  }

  function _appendBubble(role, text) {
    const wrapper = document.createElement("div");
    wrapper.className = `bubble-wrapper ${role}`;

    const bubble = document.createElement("div");
    bubble.className = `bubble bubble-${role}`;
    bubble.textContent = text; // Estricto textContent contra XSS

    const time = document.createElement("span");
    time.className = "bubble-time";
    time.textContent = new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });

    wrapper.appendChild(bubble);
    wrapper.appendChild(time);
    _append(wrapper);
  }

  function _append(el) {
    if (chatContainer) {
      chatContainer.appendChild(el);
      chatContainer.scrollTop = chatContainer.scrollHeight;
    }
  }

  /**
   * Muestra feedback pedagógico o de pronunciación con estética Duolingo Max
   * y resalta las palabras correspondientes en la estrofa activa.
   */
  function showFeedback(text, discrepancies = []) {
    if (!feedbackPanel) return;

    if (!text && (!discrepancies || discrepancies.length === 0)) {
      feedbackPanel.classList.add("hidden");
      feedbackPanel.textContent = "";
      return;
    }

    feedbackPanel.classList.remove("hidden");
    feedbackPanel.textContent = "";

    const titleEl = document.createElement("div");
    titleEl.style.fontWeight = "700";
    titleEl.style.marginBottom = "8px";
    titleEl.style.display = "flex";
    titleEl.style.alignItems = "center";
    titleEl.style.gap = "6px";
    titleEl.textContent = "💡 Consejo Fonético & Articulatorio (LingoMax)";
    feedbackPanel.appendChild(titleEl);

    if (text) {
      const p = document.createElement("div");
      p.style.lineHeight = "1.5";
      p.textContent = text;
      feedbackPanel.appendChild(p);
    }

    if (Array.isArray(discrepancies) && discrepancies.length > 0) {
      const listContainer = document.createElement("div");
      listContainer.style.marginTop = "10px";
      listContainer.style.display = "flex";
      listContainer.style.flexDirection = "column";
      listContainer.style.gap = "6px";

      for (const disc of discrepancies) {
        const item = document.createElement("div");
        item.style.display = "flex";
        item.style.alignItems = "center";
        item.style.gap = "8px";
        item.style.fontSize = "0.82rem";

        const badgeTarget = document.createElement("span");
        badgeTarget.style.padding = "2px 8px";
        badgeTarget.style.borderRadius = "4px";
        badgeTarget.style.background = "rgba(16, 185, 129, 0.2)";
        badgeTarget.style.color = "#6ee7b7";
        badgeTarget.style.fontWeight = "600";
        badgeTarget.textContent = disc.target_word || "Meta";

        const arrow = document.createElement("span");
        arrow.textContent = "➔";
        arrow.style.color = "var(--text-subtle)";

        const badgePronounced = document.createElement("span");
        badgePronounced.style.padding = "2px 8px";
        badgePronounced.style.borderRadius = "4px";
        badgePronounced.style.background = "rgba(239, 68, 68, 0.2)";
        badgePronounced.style.color = "#fca5a5";
        badgePronounced.style.fontWeight = "600";
        badgePronounced.textContent = disc.pronounced_word || "Omitido";

        const expSpan = document.createElement("span");
        expSpan.style.color = "var(--text-muted)";
        expSpan.textContent = disc.explanation ? `(${disc.explanation})` : "";

        item.appendChild(badgeTarget);
        item.appendChild(arrow);
        item.appendChild(badgePronounced);
        if (disc.explanation) item.appendChild(expSpan);

        listContainer.appendChild(item);
      }
      feedbackPanel.appendChild(listContainer);
    }

    // Botón de reintento rápido
    const retryBtn = document.createElement("button");
    retryBtn.type = "button";
    retryBtn.textContent = "🔁 Reintentar Estrofa";
    retryBtn.style.marginTop = "12px";
    retryBtn.style.padding = "6px 14px";
    retryBtn.style.borderRadius = "20px";
    retryBtn.style.border = "1px solid rgba(245, 158, 11, 0.4)";
    retryBtn.style.background = "rgba(245, 158, 11, 0.15)";
    retryBtn.style.color = "#fbbf24";
    retryBtn.style.fontSize = "0.8rem";
    retryBtn.style.fontWeight = "600";
    retryBtn.style.cursor = "pointer";
    retryBtn.addEventListener("click", () => {
      if (recordBtn) recordBtn.click();
    });
    feedbackPanel.appendChild(retryBtn);

    // Actualizar resaltado de tokens en la estrofa activa
    _highlightWords(discrepancies);
  }

  /**
   * Resalta interactivamente palabras en la estrofa activa:
   * Verde (éxito), Naranja punteado (fallo) con tooltip fonético.
   */
  function _highlightWords(discrepancies = []) {
    const activeDisplay = stanzaActiveEl || document.getElementById("karaoke-active-display");
    if (!activeDisplay) return;

    const tokens = activeDisplay.querySelectorAll(".word-token");
    const errorMap = new Map();
    for (const d of discrepancies) {
      if (d.target_word) {
        errorMap.set(d.target_word.toLowerCase().replace(/[^a-z0-9']/gi, ""), d);
      }
    }

    tokens.forEach((span) => {
      const cleanText = span.textContent.toLowerCase().replace(/[^a-z0-9']/gi, "");
      if (errorMap.has(cleanText)) {
        const disc = errorMap.get(cleanText);
        span.className = "word-token word-warning";
        span.setAttribute(
          "data-phonetic",
          disc.explanation || `Fallo: '${disc.pronounced_word || "—"}' ➔ Correcto: '${disc.target_word}'`
        );
      } else if (errorMap.size > 0) {
        span.className = "word-token word-success";
        span.removeAttribute("data-phonetic");
      }
    });
  }

  /**
   * Renderiza la estrofa activa y las adyacentes al estilo Spotify Lyrics.
   * Divide en tokens de palabras interactivos.
   */
  function renderKaraokeStanza(stanza, prevStanza = null, nextStanza = null, totalStanzas = null) {
    if (!stanza) return;

    // 1. Contador de progreso general
    if (stanzaProgressTextEl) {
      const total = totalStanzas || 16;
      stanzaProgressTextEl.textContent = `Estrofa ${stanza.stanza_id || 1} / ${total}`;
    }

    // 2. Estrofa anterior atenuada
    const prevEl = stanzaPrevEl || document.getElementById("stanza-prev");
    if (prevEl) {
      if (prevStanza && prevStanza.text) {
        prevEl.textContent = prevStanza.text;
        prevEl.style.display = "block";
      } else {
        prevEl.textContent = "";
        prevEl.style.display = "none";
      }
    }

    // 3. Estrofa siguiente atenuada
    const nextEl = stanzaNextEl || document.getElementById("stanza-next");
    if (nextEl) {
      if (nextStanza && nextStanza.text) {
        nextEl.textContent = nextStanza.text;
        nextEl.style.display = "block";
      } else {
        nextEl.textContent = "";
        nextEl.style.display = "none";
      }
    }

    // 4. Estrofa activa con tokens interactivos
    const activeDisplay = stanzaActiveEl || document.getElementById("karaoke-active-display");
    if (activeDisplay) {
      activeDisplay.textContent = "";
      const wordsContainer = document.createElement("div");
      wordsContainer.className = "stanza-words";

      const lines = (stanza.text || "").split("\n");
      lines.forEach((line, lineIdx) => {
        if (lineIdx > 0) {
          const br = document.createElement("div");
          br.style.width = "100%";
          wordsContainer.appendChild(br);
        }

        const words = line.trim().split(/\s+/);
        words.forEach((word) => {
          if (!word) return;
          const span = document.createElement("span");
          span.className = "word-token word-pending";
          span.textContent = word;

          // Clic para pronunciar palabra individual
          span.title = `Toca para escuchar: "${word}"`;
          span.addEventListener("click", () => {
            _speakWord(word);
            showToast(`Pronunciando: "${word}"`, "info");
          });

          wordsContainer.appendChild(span);
        });
      });

      activeDisplay.appendChild(wordsContainer);
    }
  }

  function setTrackInfo(title, artist, difficulty = "B2 Intermediate") {
    if (trackTitleEl) trackTitleEl.textContent = title || "Canción seleccionada";
    if (trackArtistEl) trackArtistEl.textContent = artist || "Artista";
    if (difficultyBadgeEl) difficultyBadgeEl.textContent = `⚡ ${difficulty}`;
  }

  function setAudioLevel(level) {
    if (!visualizerBar) return;
    const pct = Math.min(100, Math.round(level * 100));
    visualizerBar.style.width = `${pct}%`;
    visualizerBar.style.background = level > 0.65
      ? "var(--color-error)"
      : level > 0.25
        ? "var(--color-success)"
        : "var(--grad-primary)";
  }

  function updateStats(stats) {
    if (!statsEl || !stats) return;
    statsEl.textContent = "";

    const span = document.createElement("span");
    span.textContent = `Sesiones: ${stats.sessions_completed ?? 0}  |  Turnos: ${stats.total_turns ?? 0}  |  Puntaje Medio: ${stats.avg_score ?? "—"}%`;
    statsEl.appendChild(span);
  }

  function getInputText() {
    return inputField?.value?.trim() || "";
  }

  function clearInput() {
    if (inputField) inputField.value = "";
  }

  function getSelectedLevel() {
    return levelSelect?.value || "B2";
  }

  function setSelectedLevel(level) {
    if (levelSelect) levelSelect.value = level;
  }

  function setRecordingActive(active) {
    if (!recordBtn) return;
    recordBtn.classList.toggle("recording", active);
    recordBtn.setAttribute("aria-pressed", active.toString());
    recordBtn.title = active ? "Detener grabación" : "Iniciar grabación de voz";
  }

  function setPlayButtonState(isPlaying) {
    const btn = playerPlayBtn || document.getElementById("player-play-btn");
    if (!btn) return;
    btn.textContent = isPlaying ? "⏸" : "▶";
    btn.title = isPlaying ? "Pausar estrofa" : "Reproducir estrofa";
  }

  function showToast(msg, type = "info") {
    const toast = document.createElement("div");
    toast.className = `toast toast-${type}`;
    toast.textContent = msg;
    document.body.appendChild(toast);
    setTimeout(() => toast.classList.add("visible"), 10);
    setTimeout(() => {
      toast.classList.remove("visible");
      setTimeout(() => toast.remove(), 300);
    }, 3200);
  }

  function _speakWord(word) {
    if (!("speechSynthesis" in window)) return;
    window.speechSynthesis.cancel();
    const clean = word.replace(/[^a-z0-9']/gi, "");
    const utter = new SpeechSynthesisUtterance(clean);
    utter.lang = "en-US";
    utter.rate = 0.85;
    window.speechSynthesis.speak(utter);
  }

  return {
    init,
    setState,
    addUserBubble,
    addTutorBubble,
    addSystemMessage,
    showFeedback,
    renderKaraokeStanza,
    setTrackInfo,
    setAudioLevel,
    setPlayButtonState,
    updateStats,
    getInputText,
    clearInput,
    getSelectedLevel,
    setSelectedLevel,
    setRecordingActive,
    showToast,
  };
})();
