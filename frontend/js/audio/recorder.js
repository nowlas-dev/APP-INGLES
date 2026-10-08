/**
 * LingoBeats — frontend/js/audio/recorder.js
 * Grabador de Audio de Alta Eficiencia con Transmisión Binaria Directa (ArrayBuffer).
 *
 * Elimina la conversión a Base64 y garantiza la liberación estricta de pistas de MediaStream
 * y contextos de audio para prevenir fugas de memoria en el navegador.
 */

"use strict";

class AudioRecorder {
  constructor() {
    this.audioContext = null;
    this.analyserNode = null;
    this.mediaStream = null;
    this.mediaRecorder = null;
    this.recordedChunks = [];
    this.animationId = null;
    this.isCapturing = false;

    this.onChunkBinaryCallback = null;
    this.onLevelCallback = null;
  }

  /**
   * Determina el mejor formato MIME soportado por el navegador.
   */
  getSupportedMime() {
    const priorities = [
      "audio/webm;codecs=opus",
      "audio/webm",
      "audio/ogg;codecs=opus",
      "audio/mp4",
    ];
    for (const m of priorities) {
      if (MediaRecorder.isTypeSupported(m)) return m;
    }
    return "audio/webm";
  }

  /**
   * Inicializa el micrófono y el analizador de frecuencias Web Audio.
   */
  async init() {
    if (this.mediaStream && this.audioContext && this.audioContext.state === "running") {
      return;
    }

    const AudioCtx = window.AudioContext || window.webkitAudioContext;
    if (!this.audioContext || this.audioContext.state === "closed") {
      this.audioContext = new AudioCtx();
    }
    if (this.audioContext.state === "suspended") {
      await this.audioContext.resume();
    }

    this.analyserNode = this.audioContext.createAnalyser();
    this.analyserNode.fftSize = 256;
    this.analyserNode.smoothingTimeConstant = 0.8;

    try {
      this.mediaStream = await navigator.mediaDevices.getUserMedia({
        audio: {
          echoCancellation: true,
          noiseSuppression: true,
          autoGainControl: true,
          sampleRate: 16000,
        },
      });

      const sourceNode = this.audioContext.createMediaStreamSource(this.mediaStream);
      sourceNode.connect(this.analyserNode);
      console.log("[RECORDER] ✅ Micrófono y AudioContext inicializados.");
    } catch (err) {
      throw new Error(`Permiso de micrófono no otorgado: ${err.message}`);
    }
  }

  /**
   * Inicia la grabación continua transmitiendo el resultado como ArrayBuffer binario.
   * @param {function(ArrayBuffer, string): void} onBinaryReady Callback con buffer binario y tipo MIME
   * @param {function(number): void} [onLevel] Callback de nivel de audio normalizado (0-1)
   */
  startRecording(onBinaryReady, onLevel) {
    if (!this.mediaStream) {
      throw new Error("El grabador no está inicializado. Llame a init() primero.");
    }

    if (this.mediaRecorder && this.mediaRecorder.state === "recording") {
      return;
    }

    this.onChunkBinaryCallback = onBinaryReady;
    this.onLevelCallback = onLevel || null;
    this.recordedChunks = [];

    const mime = this.getSupportedMime();
    this.mediaRecorder = new MediaRecorder(this.mediaStream, { mimeType: mime });

    this.mediaRecorder.ondataavailable = (event) => {
      if (event.data && event.data.size > 0) {
        this.recordedChunks.push(event.data);
      }
    };

    this.mediaRecorder.onstop = async () => {
      const blob = new Blob(this.recordedChunks, { type: mime });
      this.recordedChunks = [];

      // Extracción directa de ArrayBuffer (cero Base64 overhead, Item 9)
      if (this.onChunkBinaryCallback) {
        try {
          const arrayBuffer = await blob.arrayBuffer();
          this.onChunkBinaryCallback(arrayBuffer, mime);
        } catch (err) {
          console.error("[RECORDER] Error extrayendo ArrayBuffer binario del blob:", err);
        }
      }

      // Liberar pistas de MediaStream inmediatamente para ahorrar batería y memoria (Item 14)
      this.stopMediaStreamTracks();
    };

    this.mediaRecorder.start(100);
    this.isCapturing = true;
    this._startLevelMonitor();
    console.log(`[RECORDER] 🔴 Grabando con formato '${mime}'...`);
  }

  /**
   * Detiene la captura de audio y detiene el monitor visual.
   */
  stopRecording() {
    this.isCapturing = false;
    this._stopLevelMonitor();

    if (this.mediaRecorder && this.mediaRecorder.state === "recording") {
      this.mediaRecorder.stop();
      console.log("[RECORDER] ⏹️ Grabación detenida.");
    }
  }

  isRecording() {
    return this.isCapturing;
  }

  /**
   * Monitor de volumen reactivo desacoplado.
   */
  _startLevelMonitor() {
    if (!this.analyserNode || !this.onLevelCallback) return;

    const dataArray = new Uint8Array(this.analyserNode.frequencyBinCount);
    const tick = () => {
      if (!this.isCapturing) return;
      this.analyserNode.getByteFrequencyData(dataArray);
      const avg = dataArray.reduce((acc, val) => acc + val, 0) / dataArray.length;
      this.onLevelCallback(avg / 255);
      this.animationId = requestAnimationFrame(tick);
    };
    this.animationId = requestAnimationFrame(tick);
  }

  _stopLevelMonitor() {
    if (this.animationId) {
      cancelAnimationFrame(this.animationId);
      this.animationId = null;
    }
    if (this.onLevelCallback) {
      this.onLevelCallback(0);
    }
  }

  /**
   * Libera todas las pistas activas del micrófono para que el hardware se apague.
   */
  stopMediaStreamTracks() {
    if (this.mediaStream) {
      this.mediaStream.getTracks().forEach((track) => {
        try {
          track.stop();
        } catch (e) {}
      });
      this.mediaStream = null;
      console.log("[RECORDER] 🔒 Pistas de MediaStream liberadas (track.stop).");
    }
  }

  /**
   * Destruye la instancia cerrando el AudioContext y limpiando buffers.
   */
  destroy() {
    this.stopRecording();
    this.stopMediaStreamTracks();
    if (this.audioContext && this.audioContext.state !== "closed") {
      this.audioContext.close();
      this.audioContext = null;
    }
    this.analyserNode = null;
    this.recordedChunks = [];
    console.log("[RECORDER] 🗑️ Grabador destruido y memoria liberada.");
  }
}

// Exportación universal
if (typeof module !== "undefined" && module.exports) {
  module.exports = AudioRecorder;
} else {
  window.AudioRecorder = AudioRecorder;
}
