/**
 * LingoBeats — frontend/js/audio/player.js
 * Reproductor Sincronizado de Alta Precisión con Compensación de Deriva (SyncPlayer).
 *
 * Mantiene la pista de audio alineada con marcas de tiempo en memoria,
 * compensa diferencias entre el reloj de Web Audio API y el elemento HTML5,
 * y pausa instantáneamente al finalizar cada estrofa para dar paso a la grabación del usuario.
 */

"use strict";

class SyncPlayer {
  /**
   * @param {object} options
   * @param {number} [options.driftThresholdMs=40] Tolerancia de deriva antes de resincronizar
   * @param {function} [options.onStanzaChange] Callback al cambiar de estrofa activa
   * @param {function} [options.onStanzaComplete] Callback al alcanzar el final de la estrofa
   * @param {function} [options.onTimeUpdate] Callback de progreso de tiempo de alta resolución
   */
  constructor(options = {}) {
    this.driftThresholdSec = (options.driftThresholdMs || 40) / 1000;
    this.onStanzaChange = options.onStanzaChange || (() => {});
    this.onStanzaComplete = options.onStanzaComplete || (() => {});
    this.onTimeUpdate = options.onTimeUpdate || (() => {});

    // Elemento HTML5 de audio (reproducción continua de stream/pista)
    this.audioElement = new Audio();
    this.audioElement.preload = "auto";

    // Web Audio API Context (reloj maestro determinista)
    const AudioCtx = window.AudioContext || window.webkitAudioContext;
    this.audioContext = new AudioCtx();
    this.audioContextStartTime = 0;
    this.mediaSourceNode = null;

    // Array plano de estrofas en memoria (desacoplado del DOM)
    this.stanzas = [];
    this.currentStanzaIndex = -1;
    this.isPlaying = false;
    this.rafId = null;

    // Bucle binded
    this._tick = this._tick.bind(this);
    this._setupAudioListeners();
  }

  _setupAudioListeners() {
    this.audioElement.addEventListener("ended", () => {
      this.pause();
      if (this.currentStanzaIndex >= 0 && this.stanzas[this.currentStanzaIndex]) {
        this.onStanzaComplete(this.stanzas[this.currentStanzaIndex]);
      }
    });

    this.audioElement.addEventListener("play", () => {
      if (this.audioContext.state === "suspended") {
        this.audioContext.resume();
      }
    });
  }

  /**
   * Carga una pista de audio y la lista de estrofas sincronizadas.
   * @param {string} audioUrl URL del stream o archivo de audio
   * @param {Array<object>} stanzas Array plano con { stanza_id, start_time, end_time, lines, text }
   */
  loadTrack(audioUrl, stanzas = []) {
    this.pause();
    this.audioElement.src = audioUrl;
    this.stanzas = Array.isArray(stanzas) ? [...stanzas] : [];
    this.currentStanzaIndex = -1;
    console.log(`[SYNC PLAYER] 🎵 Pista cargada con ${this.stanzas.length} estrofas.`);
  }

  /**
   * Inicia la reproducción y el bucle de sincronización por rAF.
   */
  async play() {
    if (this.audioContext.state === "suspended") {
      await this.audioContext.resume();
    }

    try {
      await this.audioElement.play();
      this.isPlaying = true;
      this.audioContextStartTime = this.audioContext.currentTime - this.audioElement.currentTime;

      this._cancelLoop();
      this.rafId = requestAnimationFrame(this._tick);
      console.log("[SYNC PLAYER] ▶️ Reproducción iniciada.");
    } catch (err) {
      console.error("[SYNC PLAYER] Error al reproducir audio:", err);
    }
  }

  /**
   * Pausa la reproducción y detiene el bucle rAF.
   */
  pause() {
    this.isPlaying = false;
    this.audioElement.pause();
    this._cancelLoop();
    console.log("[SYNC PLAYER] ⏸️ Reproducción pausada.");
  }

  /**
   * Salta a una posición temporal específica en segundos.
   * @param {number} seconds
   */
  seek(seconds) {
    const clamped = Math.max(0, Math.min(seconds, this.audioElement.duration || seconds));
    this.audioElement.currentTime = clamped;
    this.audioContextStartTime = this.audioContext.currentTime - clamped;
    this._evaluateCurrentStanza(clamped);
  }

  /**
   * Salta a una estrofa específica e inicia reproducción.
   * @param {number} stanzaId
   */
  jumpToStanza(stanzaId) {
    const index = this.stanzas.findIndex((s) => s.stanza_id === stanzaId);
    if (index !== -1) {
      this.currentStanzaIndex = index;
      const targetStanza = this.stanzas[index];
      this.seek(targetStanza.start_time);
      this.onStanzaChange(targetStanza);
    }
  }

  /**
   * Bucle de alta frecuencia (rAF) con compensación de deriva entre clocks.
   */
  _tick() {
    if (!this.isPlaying) return;

    const mediaTime = this.audioElement.currentTime;
    const acTime = this.audioContext.currentTime - this.audioContextStartTime;
    const drift = Math.abs(acTime - mediaTime);

    // Mecanismo de compensación de desviación (Drift Compensation)
    let synchronizedTime = mediaTime;
    if (drift > this.driftThresholdSec) {
      // Re-alinear el reloj maestro Web Audio si la deriva supera el umbral
      this.audioContextStartTime = this.audioContext.currentTime - mediaTime;
      synchronizedTime = mediaTime;
    } else {
      // Uso de tiempo ponderado de alta precisión
      synchronizedTime = acTime * 0.7 + mediaTime * 0.3;
    }

    this.onTimeUpdate(synchronizedTime);
    this._evaluateCurrentStanza(synchronizedTime);

    this.rafId = requestAnimationFrame(this._tick);
  }

  /**
   * Evalúa la estrofa actual y detecta el corte automático al final de la estrofa.
   * @param {number} currentTime
   */
  _evaluateCurrentStanza(currentTime) {
    if (this.stanzas.length === 0) return;

    // 1. Detectar si la estrofa activa ha alcanzado su fin estricto
    if (this.currentStanzaIndex >= 0) {
      const active = this.stanzas[this.currentStanzaIndex];
      if (currentTime >= active.end_time) {
        console.log(`[SYNC PLAYER] ⏹️ Estrofa #${active.stanza_id} finalizada en ${currentTime.toFixed(2)}s.`);
        this.pause();
        this.onStanzaComplete(active);
        return;
      }
    }

    // 2. Localizar estrofa activa en el array en memoria
    const foundIndex = this.stanzas.findIndex(
      (s) => currentTime >= s.start_time && currentTime < s.end_time
    );

    if (foundIndex !== -1 && foundIndex !== this.currentStanzaIndex) {
      this.currentStanzaIndex = foundIndex;
      const stanza = this.stanzas[foundIndex];
      console.log(`[SYNC PLAYER] 🎶 Estrofa activa #${stanza.stanza_id} (${stanza.start_time}s - ${stanza.end_time}s)`);
      this.onStanzaChange(stanza);
    }
  }

  _cancelLoop() {
    if (this.rafId) {
      cancelAnimationFrame(this.rafId);
      this.rafId = null;
    }
  }

  /**
   * Destruye el reproductor liberando contexto y recursos de audio.
   */
  destroy() {
    this.pause();
    this.audioElement.src = "";
    this.audioElement.load();
    if (this.audioContext && this.audioContext.state !== "closed") {
      this.audioContext.close();
    }
    this.stanzas = [];
    console.log("[SYNC PLAYER] 🗑️ Recursos liberados.");
  }
}

// Exportación compatible en navegador y módulos
if (typeof module !== "undefined" && module.exports) {
  module.exports = SyncPlayer;
} else {
  window.SyncPlayer = SyncPlayer;
}
