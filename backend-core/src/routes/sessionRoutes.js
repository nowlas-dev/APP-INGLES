/**
 * LingoBeats — backend-core/src/routes/sessionRoutes.js
 * Ruta Proxy / Gateway para flujo de bienvenida contextual y gestión de sesiones.
 * Transmite audio en HTTP streaming puro hacia FastAPI y gestiona fallbacks ante latencia.
 */

"use strict";

const express = require("express");
const axios   = require("axios");
const router  = express.Router();

const rawAudioUrl      = process.env.AUDIO_ENGINE_URL || "http://127.0.0.1:8000";
const AUDIO_ENGINE_URL = rawAudioUrl.replace("localhost", "127.0.0.1");

/**
 * GET /welcome y /api/session/welcome
 * Query params: song, artist, attitude, voice
 * Reenvía la solicitud por HTTP streaming hacia FastAPI (/api/ai/session/welcome).
 * Retorna audio/mpeg binario con fallback en caso de timeout.
 */
async function handleWelcomeGreeting(req, res) {
  const {
    song     = "Yesterday",
    artist   = "",
    attitude = "funny",
    voice    = "dalia",
  } = req.query;

  const upstreamUrl = `${AUDIO_ENGINE_URL}/api/ai/session/welcome`;

  try {
    const upstreamResponse = await axios.get(upstreamUrl, {
      params: { song, artist, attitude, voice },
      responseType: "stream",
      timeout: 12000, // Timeout de 12 segundos para prevenir bloqueos de pipeline
    });

    res.set({
      "Content-Type": "audio/mpeg",
      "Transfer-Encoding": "chunked",
      ...(upstreamResponse.headers["x-greeting-text"]
        ? { "X-Greeting-Text": upstreamResponse.headers["x-greeting-text"] }
        : {}),
      ...(upstreamResponse.headers["x-tutor-attitude"]
        ? { "X-Tutor-Attitude": upstreamResponse.headers["x-tutor-attitude"] }
        : {}),
      ...(upstreamResponse.headers["x-tutor-voice"]
        ? { "X-Tutor-Voice": upstreamResponse.headers["x-tutor-voice"] }
        : {}),
    });

    upstreamResponse.data.pipe(res);
  } catch (err) {
    console.error(`[SESSION GATEWAY] Error en saludo de bienvenida (${err.message}). Evaluando fallback...`);

    // Fallback de resiliencia: Si /api/ai/session/welcome falla o agota el tiempo,
    // se consulta el endpoint de preview general de TTS como respaldo rápido
    try {
      const fallbackText = `Hello! Welcome to LingoBeats. Let's practice ${song} together!`;
      const fallbackResp = await axios.get(`${AUDIO_ENGINE_URL}/api/ai/tts/preview`, {
        params: { voice, text: fallbackText },
        responseType: "stream",
        timeout: 5000,
      });

      res.set({
        "Content-Type": "audio/mpeg",
        "Transfer-Encoding": "chunked",
        "X-Fallback-Used": "true",
      });

      return fallbackResp.data.pipe(res);
    } catch (fbErr) {
      console.error(`[SESSION GATEWAY] Fallback también falló: ${fbErr.message}`);
      return res.status(504).json({
        success: false,
        error: "GATEWAY_TIMEOUT",
        message: "El motor de síntesis de voz no respondió a tiempo para el saludo de bienvenida.",
        detail: err.message,
      });
    }
  }
}

// Registro de endpoints (soporta montaje con prefijo /api/session o directo)
router.get("/welcome", handleWelcomeGreeting);
router.get("/api/session/welcome", handleWelcomeGreeting);

module.exports = router;
