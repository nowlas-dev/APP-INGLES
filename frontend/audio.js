/**
 * LingoBeats / LingoVibe — frontend/audio.js
 * Módulo unificado de captura de audio y reproducción sincronizada.
 * Utiliza AudioRecorder y SyncPlayer garantizando liberación de memoria y cero fugas.
 */

"use strict";

const AudioModule = (() => {
  let recorder = null;
  let player = null;
  let audioContext = null;
  let activeSourceNode = null;

  function _getAudioContext() {
    if (!audioContext || audioContext.state === "closed") {
      const AudioCtx = window.AudioContext || window.webkitAudioContext;
      audioContext = new AudioCtx();
    }
    return audioContext;
  }

  function stopPlayback() {
    if (activeSourceNode) {
      try {
        activeSourceNode.stop();
        activeSourceNode.disconnect();
      } catch (e) {}
      activeSourceNode = null;
    }
  }

  async function init() {
    if (!recorder) {
      recorder = new AudioRecorder();
    }
    await recorder.init();
    if (!player) {
      player = new SyncPlayer();
    }
  }

  /**
   * Inicia la grabación entregando un ArrayBuffer binario (sin Base64 overhead)
   * o un Blob para retrocompatibilidad.
   */
  function startRecording(onBinaryChunk, onLevel) {
    stopPlayback();
    if (!recorder) {
      recorder = new AudioRecorder();
    }
    recorder.startRecording(onBinaryChunk, onLevel);
  }

  function stopRecording() {
    if (recorder) {
      recorder.stopRecording();
    }
  }

  function isRecording() {
    return recorder ? recorder.isRecording() : false;
  }

  /**
   * Reproduce audio desde una URL decodificando con Web Audio API (decodeAudioData).
   */
  async function playAudioUrl(url) {
    if (!url) return;
    stopPlayback();
    const ctx = _getAudioContext();
    if (ctx.state === "suspended") {
      await ctx.resume();
    }

    const response = await fetch(url);
    if (!response.ok) {
      throw new Error(`Error al descargar audio (${response.status})`);
    }
    const arrayBuffer = await response.arrayBuffer();
    const decodedBuffer = await ctx.decodeAudioData(arrayBuffer);
    const sourceNode = ctx.createBufferSource();
    sourceNode.buffer = decodedBuffer;
    sourceNode.connect(ctx.destination);
    activeSourceNode = sourceNode;
    sourceNode.start();

    return new Promise((resolve) => {
      sourceNode.onended = () => {
        if (activeSourceNode === sourceNode) {
          activeSourceNode = null;
        }
        resolve();
      };
    });
  }

  /**
   * Reproduce audio desde Base64 de forma eficiente con AudioContext.
   */
  async function playAudioB64(audioB64, mimeType = "audio/mpeg") {
    if (!audioB64) return;
    stopPlayback();
    const ctx = _getAudioContext();
    if (ctx.state === "suspended") {
      await ctx.resume();
    }

    // Decodificación directa y eficiente
    const binaryString = atob(audioB64);
    const len = binaryString.length;
    const bytes = new Uint8Array(len);
    for (let i = 0; i < len; i++) {
      bytes[i] = binaryString.charCodeAt(i);
    }

    const decodedBuffer = await ctx.decodeAudioData(bytes.buffer.slice(0));
    const sourceNode = ctx.createBufferSource();
    sourceNode.buffer = decodedBuffer;
    sourceNode.connect(ctx.destination);
    activeSourceNode = sourceNode;
    sourceNode.start();

    return new Promise((resolve) => {
      sourceNode.onended = () => {
        if (activeSourceNode === sourceNode) {
          activeSourceNode = null;
        }
        resolve();
      };
    });
  }

  /**
   * Reproduce audio directamente desde un ArrayBuffer binario recibido por WebSocket.
   */
  async function playAudioBinary(arrayBuffer) {
    if (!arrayBuffer) return;
    stopPlayback();
    const ctx = _getAudioContext();
    if (ctx.state === "suspended") {
      await ctx.resume();
    }
    const decodedBuffer = await ctx.decodeAudioData(arrayBuffer.slice(0));
    const sourceNode = ctx.createBufferSource();
    sourceNode.buffer = decodedBuffer;
    sourceNode.connect(ctx.destination);
    activeSourceNode = sourceNode;
    sourceNode.start();

    return new Promise((resolve) => {
      sourceNode.onended = () => {
        if (activeSourceNode === sourceNode) {
          activeSourceNode = null;
        }
        resolve();
      };
    });
  }

  /**
   * Acceso al reproductor de karaoke sincronizado.
   */
  function getPlayer() {
    if (!player) {
      player = new SyncPlayer();
    }
    return player;
  }

  function destroy() {
    stopPlayback();
    if (recorder) {
      recorder.destroy();
      recorder = null;
    }
    if (player) {
      player.destroy();
      player = null;
    }
    if (audioContext && audioContext.state !== "closed") {
      audioContext.close();
      audioContext = null;
    }
  }

  return {
    init,
    startRecording,
    stopRecording,
    isRecording,
    playAudioUrl,
    playAudioB64,
    playAudioBinary,
    stopPlayback,
    getPlayer,
    destroy,
  };
})();
