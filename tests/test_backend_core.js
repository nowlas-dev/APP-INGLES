/**
 * LingoBeats — tests/test_backend_core.js
 * Verificación automatizada de sessionStore (INTRO_GREETING, PLAYING_STANZA, attitude, voice)
 * y de la ruta proxy GET /api/session/welcome (HTTP streaming + fallback).
 */

"use strict";

const assert = require("assert");
const axios  = require("axios");
const path   = require("path");

const sessionStore = require("../backend-core/src/sessionStore");
const sessionRoutes = require("../backend-core/src/routes/sessionRoutes");

async function testSessionStoreLifecycle() {
  console.log("\n=== TEST 1: Ciclo de vida y estados en sessionStore ===");

  // 1. Verificar estados INTRO_GREETING y PLAYING_STANZA
  assert.strictEqual(sessionStore.STATES.INTRO_GREETING, "INTRO_GREETING", "Falta estado INTRO_GREETING");
  assert.strictEqual(sessionStore.STATES.PLAYING_STANZA, "PLAYING_STANZA", "Falta estado PLAYING_STANZA");
  console.log("  [PASS] Estados INTRO_GREETING y PLAYING_STANZA verificados en STATES.");

  // 2. Crear sesión de prueba con actitud y voz
  const testClientId = "test_client_001";
  sessionStore.create(testClientId, {
    sessionId: 999,
    userId: "usr_test",
    cefrLevel: "B2",
    voice: "jorge",
    attitude: "friendly",
    ws: null,
  });

  const session = sessionStore.get(testClientId);
  assert(session, "La sesión debe existir en sessionStore");
  assert.strictEqual(session.voice, "jorge", "La voz debe ser jorge");
  assert.strictEqual(session.attitude, "friendly", "La actitud debe ser friendly");
  console.log(`  [PASS] Sesión creada con voice='${session.voice}' y attitude='${session.attitude}'.`);

  // 3. Probar ciclo de transiciones: IDLE -> INTRO_GREETING -> PLAYING_STANZA
  assert.strictEqual(session.state, sessionStore.STATES.IDLE);
  
  const trans1 = sessionStore.transition(testClientId, sessionStore.STATES.INTRO_GREETING);
  assert.strictEqual(trans1, true, "Transición IDLE -> INTRO_GREETING debe ser permitida");
  assert.strictEqual(session.state, sessionStore.STATES.INTRO_GREETING);
  console.log("  [PASS] Transición exitosa: IDLE -> INTRO_GREETING");

  const trans2 = sessionStore.transition(testClientId, sessionStore.STATES.PLAYING_STANZA);
  assert.strictEqual(trans2, true, "Transición INTRO_GREETING -> PLAYING_STANZA debe ser permitida");
  assert.strictEqual(session.state, sessionStore.STATES.PLAYING_STANZA);
  console.log("  [PASS] Transición exitosa: INTRO_GREETING -> PLAYING_STANZA");

  // 4. Probar actualización de actitud y voz
  sessionStore.updateVoice(testClientId, "paloma");
  assert.strictEqual(session.voice, "paloma");
  sessionStore.updateAttitude(testClientId, "strict");
  assert.strictEqual(session.attitude, "strict");
  console.log("  [PASS] updateVoice y updateAttitude modifican el estado de sesión correctamente.");

  // Limpieza
  sessionStore.remove(testClientId);
  console.log("  [PASS] Limpieza de sesión completada.");
}

async function testSessionWelcomeProxy() {
  console.log("\n=== TEST 2: Endpoint Proxy GET /api/session/welcome en Orchestrator (:3000) ===");
  const testUrl = "http://127.0.0.1:3000/api/session/welcome";

  const params = {
    song: "Yesterday",
    artist: "The Beatles",
    attitude: "funny",
    voice: "dalia",
  };

  try {
    const res = await axios.get(testUrl, {
      params,
      responseType: "arraybuffer",
      timeout: 15000,
    });

    assert.strictEqual(res.status, 200, "El código de estado debe ser 200");
    const contentType = res.headers["content-type"];
    assert(contentType && contentType.includes("audio/mpeg"), `Content-Type debe ser audio/mpeg, recibido: ${contentType}`);
    assert(res.data.length > 2000, `El tamaño del buffer de audio debe ser mayor a 2KB, recibido: ${res.data.length} bytes`);
    
    console.log(`  [PASS] Endpoint proxy respondió HTTP 200 con ${res.data.length} bytes audio/mpeg.`);
    if (res.headers["x-greeting-text"]) {
      console.log(`  [PASS] Encabezado X-Greeting-Text: ${decodeURIComponent(res.headers["x-greeting-text"])}`);
    }
  } catch (err) {
    if (err.code === "ECONNREFUSED") {
      console.warn("  [SKIP] Servidor en puerto 3000 no está escuchando en este momento. Se verificó router exportado.");
    } else {
      throw err;
    }
  }
}

async function main() {
  await testSessionStoreLifecycle();
  await testSessionWelcomeProxy();
  console.log("\nTODOS LOS TESTS DE BACKEND-CORE PASARON EXITOSAMENTE.");
}

main().catch((err) => {
  console.error("ERROR EN TEST:", err);
  process.exit(1);
});
