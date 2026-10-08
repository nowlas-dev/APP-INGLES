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

  function _getAudioContext() {
    if (!audioContext || audioContext.state === "closed") {
      const AudioCtx = window.AudioContext || window.webkitAudioContext;
      audioContext = new AudioCtx();
    }
    return audioContext;
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
   * Reproduce audio desde Base64 de forma eficiente (sin Array.from excesivo).
   */
  async function playAudioB64(audioB64, mimeType = "audio/mpeg") {
    if (!audioB64) return;
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
    sourceNode.start();

    return new Promise((resolve) => {
      sourceNode.onended = resolve;
    });
  }

  /**
   * Reproduce audio directamente desde un ArrayBuffer binario recibido por WebSocket.
   */
  async function playAudioBinary(arrayBuffer) {
    if (!arrayBuffer) return;
    const ctx = _getAudioContext();
    if (ctx.state === "suspended") {
      await ctx.resume();
    }
    const decodedBuffer = await ctx.decodeAudioData(arrayBuffer.slice(0));
    const sourceNode = ctx.createBufferSource();
    sourceNode.buffer = decodedBuffer;
    sourceNode.connect(ctx.destination);
    sourceNode.start();

    return new Promise((resolve) => {
      sourceNode.onended = resolve;
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
    playAudioB64,
    playAudioBinary,
    getPlayer,
    destroy,
  };
})();
