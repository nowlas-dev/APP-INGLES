/**
 * LingoVibe v2 — orchestrator/routes/chat.js
 * Orquestación de turnos de conversación (proxy inteligente hacia audio_engine).
 */

"use strict";

const express  = require("express");
const axios    = require("axios");
const FormData = require("form-data");
const router   = express.Router();

const AUDIO_ENGINE_URL = process.env.AUDIO_ENGINE_URL || "http://localhost:8000";

/**
 * POST /api/turn
 * Orquesta un turno de texto:
 * Body JSON: { text, session_id, turn_seq, user_key, cefr_level, target_lang }
 */
router.post("/turn/text", async (req, res) => {
  const {
    text,
    session_id,
    turn_seq    = 1,
    user_key    = "usr_001",
    cefr_level,
    target_lang = "en-US",
  } = req.body;

  if (!text || !text.trim()) {
    return res.status(400).json({ error: "Campo 'text' requerido y no vacío." });
  }

  try {
    const r = await axios.post(
      `${AUDIO_ENGINE_URL}/generate`,
      { user_message: text, session_id, turn_seq, user_key, cefr_level },
      { timeout: 60000 }
    );
    res.json(r.data);
  } catch (err) {
    console.error("[CHAT/TEXT] Error en generate:", err.message);
    const status = err.response?.status || 502;
    res.status(status).json({ error: err.response?.data || err.message });
  }
});

/**
 * POST /api/turn/audio
 * Orquesta un turno de audio (multipart/form-data).
 * Campos: audio (file), session_id, turn_seq, user_key, cefr_level, target_lang, language
 */
router.post("/turn/audio", async (req, res) => {
  // req.body viene de multer/express-fileupload — usamos raw buffer vía express
  // El frontend envía FormData directo; lo retransmitimos al audio_engine.
  if (!req.rawBody && !req.body) {
    return res.status(400).json({ error: "Se requiere audio (multipart/form-data)." });
  }

  try {
    // Redirigir el FormData directamente al audio_engine /ingest
    const incomingForm = req;
    const outForm = new FormData();

    // Extraer campos del body parseado por express (si hay middleware)
    const fields = ["session_id", "turn_seq", "user_key", "cefr_level", "target_lang", "language"];
    for (const field of fields) {
      if (req.body[field] !== undefined) {
        outForm.append(field, String(req.body[field]));
      }
    }
    outForm.append("synthesize_audio", "true");

    // Nota: el audio file viene parseado por el middleware de upload
    if (req.file) {
      outForm.append("audio", req.file.buffer, {
        filename:    req.file.originalname || "audio.webm",
        contentType: req.file.mimetype || "audio/webm",
      });
    }

    const r = await axios.post(`${AUDIO_ENGINE_URL}/ingest`, outForm, {
      headers: outForm.getHeaders(),
      timeout: 90000,
      maxBodyLength: Infinity,
      maxContentLength: Infinity,
    });

    res.json(r.data);
  } catch (err) {
    console.error("[CHAT/AUDIO] Error en ingest:", err.message);
    const status = err.response?.status || 502;
    res.status(status).json({ error: err.response?.data || err.message });
  }
});

module.exports = router;
