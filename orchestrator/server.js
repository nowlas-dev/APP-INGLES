/**
 * LingoBeats / LingoVibe — orchestrator/server.js
 *
 * API Gateway + WebSocket Hub (Puerto 3000)
 * Soporta transporte binario directo (cero Base64 overhead), validación estricta de Magic Bytes,
 * integración de lyricsService (LRCLIB), proxies de AI y manejo global de errores seguro.
 */

"use strict";

require("dotenv").config({ path: require("path").join(__dirname, "../.env") });

const express    = require("express");
const http       = require("http");
const { WebSocketServer } = require("ws");
const { randomUUID }      = require("crypto");
const cors       = require("cors");
const axios      = require("axios");
const multer     = require("multer");
const path       = require("path");
const FormData   = require("form-data");
const fs         = require("fs");

const sessionStore   = require("./state/sessionStore");
const profileRoutes  = require("./routes/profile");
const sessionsRoutes = require("./routes/sessions");
const chatRoutes     = require("./routes/chat");
const lyricsService  = require("./services/lyricsService");

const PORT             = parseInt(process.env.ORCHESTRATOR_PORT || "3000", 10);
const rawAudioUrl      = process.env.AUDIO_ENGINE_URL || "http://127.0.0.1:8000";
const AUDIO_ENGINE_URL = rawAudioUrl.replace("localhost", "127.0.0.1");

// ─────────────────────────────────────────────────────────────
//  Validación de Cabeceras Magic Bytes (Item 11)
// ─────────────────────────────────────────────────────────────

function validateMagicBytes(buf) {
  if (!buf || buf.length < 4) return false;
  // WebM / EBML: 1A 45 DF A3
  if (buf[0] === 0x1A && buf[1] === 0x45 && buf[2] === 0xDF && buf[3] === 0xA3) return true;
  // WAV: 52 49 46 46 (RIFF)
  if (buf[0] === 0x52 && buf[1] === 0x49 && buf[2] === 0x46 && buf[3] === 0x46) return true;
  // MP3: 49 44 33 (ID3)
  if (buf[0] === 0x49 && buf[1] === 0x44 && buf[2] === 0x33) return true;
  // MP3 sync frame
  if (buf[0] === 0xFF && (buf[1] & 0xE0) === 0xE0) return true;
  // OGG: 4F 67 67 53 (OggS)
  if (buf[0] === 0x4F && buf[1] === 0x67 && buf[2] === 0x67 && buf[3] === 0x53) return true;
  return false;
}

// ─────────────────────────────────────────────────────────────
//  Express App & Middlewares
// ─────────────────────────────────────────────────────────────

const app = express();
const server = http.createServer(app);

// Multer con límite de 10 MB y filtro de tipo
const upload = multer({
  storage: multer.memoryStorage(),
  limits: { fileSize: 10 * 1024 * 1024 },
  fileFilter: (req, file, cb) => {
    const allowed = ["audio/webm", "audio/wav", "audio/mpeg", "audio/ogg", "audio/mp4", "audio/x-wav"];
    if (!allowed.includes(file.mimetype.toLowerCase())) {
      return cb(new Error("Formato de audio no permitido"));
    }
    cb(null, true);
  },
});

app.use(cors({ origin: true, credentials: true }));
app.use(express.json({ limit: "10mb" }));
app.use(express.urlencoded({ extended: true, limit: "10mb" }));

// Servir frontend estático
app.use(express.static(path.join(__dirname, "../frontend")));

// ── Rutas REST Existentes ────────────────────────────────────
app.use("/api/profile",  profileRoutes);
app.use("/api/session",  sessionsRoutes);
app.use("/api",          chatRoutes);

// Ruta multipart de audio con validación de magic bytes
app.post("/api/turn/audio", upload.single("audio"), (req, res, next) => {
  if (req.file && !validateMagicBytes(req.file.buffer)) {
    return res.status(400).json({ error: "Firma binaria de audio inválida (Magic bytes check falló)." });
  }
  next();
}, chatRoutes);

// ── Rutas Nuevas de LingoBeats (LRCLIB, Scoring, Stems) ─────

app.get("/api/lyrics", async (req, res) => {
  const { track, artist, album, duration } = req.query;
  if (!track) {
    return res.status(400).json({ error: "Parámetro 'track' requerido." });
  }
  try {
    const data = await lyricsService.getLyrics(
      track,
      artist || "",
      album || "",
      duration ? parseFloat(duration) : null
    );
    res.json(data);
  } catch (err) {
    res.status(500).json({ error: "Error consultando LRCLIB", detail: err.message });
  }
});

// Proxy a endpoints de IA en audio_engine
app.post("/api/score", async (req, res) => {
  try {
    const r = await axios.post(`${AUDIO_ENGINE_URL}/api/score`, req.body, { timeout: 10000 });
    res.json(r.data);
  } catch (err) {
    res.status(err.response?.status || 500).json({ error: err.response?.data || err.message });
  }
});

app.post("/api/download", async (req, res) => {
  try {
    const r = await axios.post(`${AUDIO_ENGINE_URL}/api/download`, req.body, { timeout: 60000 });
    res.json(r.data);
  } catch (err) {
    res.status(err.response?.status || 500).json({ error: err.response?.data || err.message });
  }
});

// Previsualización de voz de tutor interactivo
app.get(["/api/ai/tts/preview", "/api/tts/preview"], async (req, res) => {
  const { voice_id, voice, text } = req.query;
  const chosenVoice = (voice || voice_id || "dalia").toLowerCase().trim();
  try {
    const r = await axios.get(`${AUDIO_ENGINE_URL}/api/ai/tts/preview`, {
      params: { voice: chosenVoice, voice_id: chosenVoice, text },
      responseType: "arraybuffer",
      timeout: 15000,
    });
    res.set("Content-Type", "audio/mpeg");
    res.send(r.data);
  } catch (err) {
    res.status(err.response?.status || 500).json({ error: "Error en síntesis de previsualización", detail: err.message });
  }
});

app.get("/api/health", async (req, res) => {
  let engineStatus = { status: "unreachable" };
  try {
    const r = await axios.get(`${AUDIO_ENGINE_URL}/health`, { timeout: 4000 });
    engineStatus = r.data;
  } catch {}
  res.json({
    orchestrator:    "ok",
    port:            PORT,
    audio_engine:    engineStatus,
    active_sessions: sessionStore.size || 0,
  });
});

// Manejador Global de Errores Sanitizado (Item 13)
app.use((err, req, res, next) => {
  console.error(`[ORCHESTRATOR ERROR] ${req.method} ${req.url}: ${err.message}`);
  res.status(err.status || 500).json({
    success: false,
    error: "INTERNAL_PROCESSING_ERROR",
    message: err.message || "Error interno del servidor.",
  });
});

// SPA fallback
app.get("*", (_, res) =>
  res.sendFile(path.join(__dirname, "../frontend/index.html"))
);


// ─────────────────────────────────────────────────────────────
//  WebSocket Hub (Soporte Binario Directo + JSON)
// ─────────────────────────────────────────────────────────────

const wss = new WebSocketServer({ server, path: "/ws", maxPayload: 15 * 1024 * 1024 });

wss.on("connection", (ws) => {
  const clientId = randomUUID();
  console.log(`[WS] 🔌 Cliente conectado: ${clientId}`);

  let sessionId = null;
  let cefrLevel = "B2";
  const userId  = "usr_001";

  // Registro inmediato de sesión en memoria
  sessionStore.create(clientId, { sessionId, userId, cefrLevel, ws, voiceId: "dalia" });

  // Inicialización asíncrona de backend
  (async () => {
    try {
      const r = await axios.post(
        `${AUDIO_ENGINE_URL}/session/start`,
        { user_key: userId, cefr_level: cefrLevel },
        { timeout: 5000 }
      );
      sessionId = r.data.session_id;
      cefrLevel = r.data.cefr_level || cefrLevel;
      const session = sessionStore.get(clientId);
      if (session) {
        session.sessionId = sessionId;
        session.cefrLevel = cefrLevel;
      }
    } catch (err) {
      console.error("[WS] No se pudo crear sesión en audio_engine:", err.message);
    }

    let profile = {};
    try {
      const r = await axios.get(`${AUDIO_ENGINE_URL}/api/profile`, { timeout: 4000 });
      profile = r.data;
    } catch {}

    const curVoice = sessionStore.get(clientId)?.voiceId || "dalia";
    sessionStore.safeSend(ws, {
      type: "connected",
      clientId,
      sessionId,
      profile,
      voice_id: curVoice,
      state:   sessionStore.STATES.IDLE,
      message: "Conectado a LingoBeats / LingoVibe Orchestrator",
    });
  })();

  // ── Dispatcher de Mensajes (Sincrónico para no perder paquetes de inicio) ──
  ws.on("message", async (rawData, isBinary) => {
    const session = sessionStore.get(clientId);
    if (!session) return;

    // Caso A: Mensaje Binario Directo (ArrayBuffer / Buffer sin Base64 overhead)
    if (isBinary || (Buffer.isBuffer(rawData) && validateMagicBytes(rawData))) {
      const audioBuffer = Buffer.isBuffer(rawData) ? rawData : Buffer.from(rawData);
      console.log(`[WS] 📦 Recibido frame de audio binario: ${audioBuffer.length} bytes | Tutor: ${session.voiceId || "dalia"}`);

      sessionStore.transition(clientId, sessionStore.STATES.PROCESSING);
      const turnSeq = sessionStore.nextTurn(clientId);

      try {
        const form = new FormData();
        form.append("audio", audioBuffer, { filename: "audio.webm", contentType: "audio/webm" });
        form.append("session_id", String(session.sessionId || ""));
        form.append("turn_seq", String(turnSeq));
        form.append("user_key", session.userId);
        form.append("cefr_level", session.cefrLevel);
        form.append("target_lang", "en-US");
        form.append("synthesize_audio", "true");
        form.append("voice_id", session.voiceId || "dalia");
        form.append("voice", session.voiceId || "dalia");

        const r = await axios.post(`${AUDIO_ENGINE_URL}/ingest`, form, {
          headers: form.getHeaders(),
          timeout: 90000,
          maxBodyLength: Infinity,
          maxContentLength: Infinity,
        });

        sessionStore.transition(clientId, sessionStore.STATES.SPEAKING);
        sessionStore.safeSend(ws, {
          type: "tutor_response",
          transcript: r.data.transcript,
          conversation: r.data.conversation,
          feedback: r.data.feedback,
          target_corrections: r.data.target_corrections,
          audio_b64: r.data.audio_b64,
          audio_mime: r.data.audio_mime,
          llm_provider: r.data.llm_provider,
          stt_latency_ms: r.data.stt_latency_ms,
          llm_latency_ms: r.data.llm_latency_ms,
          total_latency_ms: r.data.total_latency_ms,
          turn_seq: turnSeq,
        });
        sessionStore.transition(clientId, sessionStore.STATES.IDLE);
      } catch (err) {
        console.error(`[WS] Error ingest binario: ${err.message}`);
        sessionStore.transition(clientId, sessionStore.STATES.ERROR);
        sessionStore.safeSend(ws, { type: "error", message: `Pipeline error: ${err.message}` });
        sessionStore.forceTransition(clientId, sessionStore.STATES.IDLE);
      }
      return;
    }

    // Caso B: Mensaje JSON estructurado
    let data;
    try {
      data = JSON.parse(rawData.toString());
    } catch {
      return sessionStore.safeSend(ws, { type: "error", message: "JSON inválido" });
    }

    const { type = "message" } = data;

    // Control de estado explícito
    if (type === "set_state") {
      const targetState = (data.state || "IDLE").toUpperCase();
      sessionStore.transition(clientId, targetState);
      return;
    }

    if (type === "set_level") {
      const level = (data.level || "B2").toUpperCase();
      try {
        await axios.post(
          `${AUDIO_ENGINE_URL}/api/profile/level`,
          { level },
          { timeout: 5000 }
        );
        sessionStore.updateLevel(clientId, level);
        sessionStore.safeSend(ws, { type: "level_updated", cefr_level: level });
      } catch (err) {
        sessionStore.safeSend(ws, { type: "error", message: `Error actualizando nivel: ${err.message}` });
      }
      return;
    }

    if (type === "message") {
      const text = (data.text || "").trim();
      if (!text) return;

      sessionStore.transition(clientId, sessionStore.STATES.PROCESSING);
      const turnSeq = sessionStore.nextTurn(clientId);

      try {
        const chosenVoice = (data.voice || data.voice_id || session.voiceId || "dalia").toLowerCase().trim();
        session.voiceId = chosenVoice;

        const r = await axios.post(`${AUDIO_ENGINE_URL}/generate`, {
          user_message: text,
          session_id:   session.sessionId,
          turn_seq:     turnSeq,
          user_key:     session.userId,
          cefr_level:   session.cefrLevel,
          voice:        chosenVoice,
          voice_id:     chosenVoice,
          synthesize_audio: true,
        }, { timeout: 60000 });

        sessionStore.transition(clientId, sessionStore.STATES.SPEAKING);
        sessionStore.safeSend(ws, {
          type: "tutor_response",
          transcript: text,
          conversation: r.data.conversation,
          feedback: r.data.feedback,
          target_corrections: r.data.target_corrections,
          audio_b64: r.data.audio_b64,
          audio_mime: r.data.audio_mime || "audio/mpeg",
          llm_provider: r.data.llm_provider,
          latency_ms: r.data.latency_ms,
          turn_seq: turnSeq,
        });
        sessionStore.transition(clientId, sessionStore.STATES.IDLE);
      } catch (err) {
        console.error(`[WS] Error generate: ${err.message}`);
        sessionStore.transition(clientId, sessionStore.STATES.ERROR);
        sessionStore.safeSend(ws, { type: "error", message: `LLM error: ${err.message}` });
        sessionStore.forceTransition(clientId, sessionStore.STATES.IDLE);
      }
      return;
    }

    // Actualización de tutor/voz explícita
    if (type === "set_voice") {
      const voiceId = (data.voice_id || data.voice || "dalia").toLowerCase().trim();
      sessionStore.updateVoice(clientId, voiceId);
      sessionStore.safeSend(ws, { type: "voice_updated", voice_id: voiceId, voice: voiceId });
      return;
    }

    if (data.voice_id || data.voice) {
      sessionStore.updateVoice(clientId, (data.voice_id || data.voice).toLowerCase().trim());
    }

    // Audio legado en base64
    if (type === "audio") {
      const { audio_b64, mime_type = "audio/webm", target_lang = "en-US" } = data;
      if (!audio_b64) return;

      sessionStore.transition(clientId, sessionStore.STATES.PROCESSING);
      const turnSeq = sessionStore.nextTurn(clientId);

      try {
        const audioBuffer = Buffer.from(audio_b64, "base64");
        const form = new FormData();
        form.append("audio", audioBuffer, { filename: "audio.webm", contentType: mime_type });
        form.append("session_id", String(session.sessionId || ""));
        form.append("turn_seq", String(turnSeq));
        form.append("user_key", session.userId);
        form.append("cefr_level", session.cefrLevel);
        form.append("target_lang", target_lang);
        form.append("synthesize_audio", "true");
        form.append("voice_id", session.voiceId || "dalia");
        form.append("voice", session.voiceId || "dalia");

        const r = await axios.post(`${AUDIO_ENGINE_URL}/ingest`, form, {
          headers: form.getHeaders(),
          timeout: 90000,
          maxBodyLength: Infinity,
          maxContentLength: Infinity,
        });

        sessionStore.transition(clientId, sessionStore.STATES.SPEAKING);
        sessionStore.safeSend(ws, {
          type: "tutor_response",
          transcript: r.data.transcript,
          conversation: r.data.conversation,
          feedback: r.data.feedback,
          target_corrections: r.data.target_corrections,
          audio_b64: r.data.audio_b64,
          audio_mime: r.data.audio_mime,
          llm_provider: r.data.llm_provider,
          stt_latency_ms: r.data.stt_latency_ms,
          llm_latency_ms: r.data.llm_latency_ms,
          total_latency_ms: r.data.total_latency_ms,
          turn_seq: turnSeq,
        });
        sessionStore.transition(clientId, sessionStore.STATES.IDLE);
      } catch (err) {
        console.error(`[WS] Error ingest base64: ${err.message}`);
        sessionStore.transition(clientId, sessionStore.STATES.ERROR);
        sessionStore.safeSend(ws, { type: "error", message: `Pipeline error: ${err.message}` });
        sessionStore.forceTransition(clientId, sessionStore.STATES.IDLE);
      }
      return;
    }
  });

  ws.on("close", () => {
    const session = sessionStore.get(clientId);
    if (session?.sessionId) {
      axios.post(`${AUDIO_ENGINE_URL}/session/end`, { session_id: session.sessionId }, { timeout: 3000 })
        .catch(() => {});
    }
    sessionStore.remove(clientId);
    console.log(`[WS] 🔌 Cliente desconectado: ${clientId}`);
  });

  ws.on("error", (err) => console.error(`[WS] Error socket ${clientId}:`, err.message));
});

// ─────────────────────────────────────────────────────────────
//  Arranque del Servidor
// ─────────────────────────────────────────────────────────────

server.listen(PORT, "127.0.0.1", () => {
  console.log("=".repeat(60));
  console.log(`  🎙️  LingoBeats / LingoVibe — Orquestador iniciado`);
  console.log(`  🌐  URL: http://127.0.0.1:${PORT}`);
  console.log(`  🔌  WebSocket: ws://127.0.0.1:${PORT}/ws`);
  console.log(`  ⚙️   Audio Engine: ${AUDIO_ENGINE_URL}`);
  console.log("=".repeat(60));
});
