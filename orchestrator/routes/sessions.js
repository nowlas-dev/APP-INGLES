/**
 * LingoVibe v2 — orchestrator/routes/sessions.js
 * Gestión de sesiones de práctica.
 * Delega la persistencia al audio_engine via HTTP (sin acceso directo a SQLite).
 */

"use strict";

const express = require("express");
const axios   = require("axios");
const router  = express.Router();

const rawAudioUrl      = process.env.AUDIO_ENGINE_URL || "http://127.0.0.1:8000";
const AUDIO_ENGINE_URL = rawAudioUrl.replace("localhost", "127.0.0.1");

/**
 * POST /api/session/start
 * Body: { user_key?, cefr_level? }
 * Crea una nueva sesión en el audio_engine y devuelve session_id.
 */
router.post("/start", async (req, res) => {
  const userKey   = req.body.user_key   || "usr_001";
  const cefrLevel = (req.body.cefr_level || "B2").toUpperCase();

  try {
    const r = await axios.post(
      `${AUDIO_ENGINE_URL}/session/start`,
      { user_key: userKey, cefr_level: cefrLevel },
      { timeout: 8000 }
    );
    console.log(`[SESSION] 🟢 Sesión creada: id=${r.data.session_id}`);
    res.json(r.data);
  } catch (err) {
    const status = err.response?.status || 502;
    console.error("[SESSION] Error al crear sesión:", err.message);
    res.status(status).json({ error: err.response?.data || err.message });
  }
});

/**
 * POST /api/session/end
 * Body: { session_id, score? }
 */
router.post("/end", async (req, res) => {
  const { session_id, score } = req.body;
  if (!session_id) return res.status(400).json({ error: "'session_id' requerido." });

  try {
    const r = await axios.post(
      `${AUDIO_ENGINE_URL}/session/end`,
      { session_id, score: score ?? null },
      { timeout: 8000 }
    );
    console.log(`[SESSION] 🔴 Sesión cerrada: id=${session_id}`);
    res.json(r.data);
  } catch (err) {
    const status = err.response?.status || 502;
    res.status(status).json({ error: err.response?.data || err.message });
  }
});

/**
 * GET /api/session/welcome
 * Query params: song, artist, attitude, voice
 * Reenvía la solicitud por HTTP streaming hacia FastAPI (/api/ai/session/welcome).
 */
router.get("/welcome", async (req, res) => {
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
      timeout: 12000,
    });

    const greetingText = upstreamResponse.headers["x-greeting-text"]
      ? decodeURIComponent(upstreamResponse.headers["x-greeting-text"])
      : "";

    res.set({
      "Content-Type": "audio/mpeg",
      "Transfer-Encoding": "chunked",
      ...(greetingText ? { "X-Greeting-Text": greetingText } : {}),
      ...(upstreamResponse.headers["x-tutor-attitude"]
        ? { "X-Tutor-Attitude": upstreamResponse.headers["x-tutor-attitude"] }
        : {}),
      ...(upstreamResponse.headers["x-tutor-voice"]
        ? { "X-Tutor-Voice": upstreamResponse.headers["x-tutor-voice"] }
        : {}),
    });

    upstreamResponse.data.pipe(res);
  } catch (err) {
    console.error(`[SESSION GATEWAY] Error en saludo de bienvenida (${err.message}). Activando fallback...`);
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
});

/**
 * GET /api/session/:id
 */
router.get("/:id", async (req, res) => {
  const sessionId = parseInt(req.params.id, 10);
  if (isNaN(sessionId)) return res.status(400).json({ error: "session_id debe ser número." });

  try {
    const r = await axios.get(`${AUDIO_ENGINE_URL}/session/${sessionId}`, { timeout: 5000 });
    res.json(r.data);
  } catch (err) {
    const status = err.response?.status || 502;
    res.status(status).json({ error: err.response?.data || err.message });
  }
});

module.exports = router;
