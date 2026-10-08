/**
 * LingoVibe v2 — orchestrator/routes/profile.js
 * Rutas Express para el perfil de usuario (proxy a SQLite via audio_engine).
 */

"use strict";

const express = require("express");
const axios   = require("axios");
const router  = express.Router();

const AUDIO_ENGINE_URL = process.env.AUDIO_ENGINE_URL || "http://localhost:8000";

/**
 * GET /api/profile
 * Devuelve el perfil completo del usuario (nivel, stats, debilidades, vocab).
 */
router.get("/", async (req, res) => {
  try {
    const r = await axios.get(`${AUDIO_ENGINE_URL}/api/profile`, { timeout: 5000 });
    res.json(r.data);
  } catch (err) {
    console.error("[PROFILE] Error al obtener perfil:", err.message);
    res.status(502).json({ error: "No se pudo conectar al Audio Engine", detail: err.message });
  }
});

/**
 * POST /api/profile/level
 * Body: { level: "B2" }
 * Actualiza el nivel CEFR del usuario.
 */
router.post("/level", async (req, res) => {
  const { level } = req.body;
  if (!level) return res.status(400).json({ error: "Campo 'level' requerido." });

  const validLevels = ["A1", "A2", "B1", "B2", "C1", "C2"];
  if (!validLevels.includes(level.toUpperCase())) {
    return res.status(400).json({ error: `Nivel inválido. Use: ${validLevels.join(", ")}` });
  }

  try {
    const r = await axios.post(
      `${AUDIO_ENGINE_URL}/api/profile/level`,
      { level: level.toUpperCase() },
      { timeout: 5000 }
    );
    res.json(r.data);
  } catch (err) {
    console.error("[PROFILE] Error al actualizar nivel:", err.message);
    res.status(502).json({ error: "No se pudo actualizar el nivel", detail: err.message });
  }
});

module.exports = router;
