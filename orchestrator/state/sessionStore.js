/**
 * LingoBeats / LingoVibe — orchestrator/state/sessionStore.js
 *
 * State Machine determinista y resiliente para sesiones activas.
 * Grafo de estados:
 *   IDLE -> RECORDING / PROCESSING / LISTENING
 *   RECORDING -> PROCESSING / IDLE
 *   PROCESSING -> FEEDBACK / COMPREHENSION / SPEAKING / IDLE / ERROR
 *   FEEDBACK -> IDLE / COMPREHENSION / PROCESSING
 *   COMPREHENSION -> IDLE / PROCESSING / RECORDING
 *   SPEAKING -> IDLE / FEEDBACK / COMPREHENSION
 *   ERROR -> IDLE
 *
 * Incluye método defensivo forceTransition() para recuperación de desincronizaciones.
 */

"use strict";

/** @type {Map<string, object>} clave = clientId */
const sessions = new Map();

// ─────────────────────────────────────────────────────────────
//  Estados válidos
// ─────────────────────────────────────────────────────────────
const STATES = Object.freeze({
  IDLE:           "IDLE",
  INTRO_GREETING: "INTRO_GREETING",
  PLAYING_STANZA: "PLAYING_STANZA",
  LISTENING:      "LISTENING",
  RECORDING:      "RECORDING",
  PROCESSING:     "PROCESSING",
  SPEAKING:       "SPEAKING",
  FEEDBACK:       "FEEDBACK",
  COMPREHENSION:  "COMPREHENSION",
  ERROR:          "ERROR",
});

const VALID_TRANSITIONS = {
  [STATES.IDLE]:           [STATES.INTRO_GREETING, STATES.PLAYING_STANZA, STATES.RECORDING, STATES.LISTENING, STATES.PROCESSING],
  [STATES.INTRO_GREETING]: [STATES.PLAYING_STANZA, STATES.IDLE, STATES.ERROR],
  [STATES.PLAYING_STANZA]: [STATES.IDLE, STATES.RECORDING, STATES.LISTENING, STATES.PROCESSING, STATES.INTRO_GREETING],
  [STATES.LISTENING]:      [STATES.RECORDING, STATES.PROCESSING, STATES.IDLE],
  [STATES.RECORDING]:      [STATES.PROCESSING, STATES.IDLE],
  [STATES.PROCESSING]:     [STATES.FEEDBACK, STATES.COMPREHENSION, STATES.SPEAKING, STATES.IDLE, STATES.ERROR],
  [STATES.SPEAKING]:       [STATES.IDLE, STATES.FEEDBACK, STATES.COMPREHENSION, STATES.PLAYING_STANZA],
  [STATES.FEEDBACK]:       [STATES.IDLE, STATES.COMPREHENSION, STATES.PROCESSING],
  [STATES.COMPREHENSION]:  [STATES.IDLE, STATES.PROCESSING, STATES.RECORDING],
  [STATES.ERROR]:          [STATES.IDLE],
};


// ─────────────────────────────────────────────────────────────
//  CRUD de sesiones
// ─────────────────────────────────────────────────────────────

/**
 * Crea una entrada de sesión en memoria.
 * @param {string} clientId   Identificador único del cliente WS.
 * @param {object} opts
 * @param {number} opts.sessionId    ID en SQLite.
 * @param {string} opts.userId
 * @param {string} opts.cefrLevel
 * @param {import('ws').WebSocket} opts.ws
 * @param {string} [opts.voiceId]
 * @param {string} [opts.voice]
 * @param {string} [opts.attitude]
 */
function create(clientId, { sessionId, userId, cefrLevel, ws, voiceId = "dalia", voice = "dalia", attitude = "funny" }) {
  const chosenVoice = (voice || voiceId || "dalia").toLowerCase().trim();
  const chosenAttitude = (attitude || "funny").toLowerCase().trim();
  sessions.set(clientId, {
    clientId,
    sessionId,
    userId,
    cefrLevel,
    voiceId: chosenVoice,
    voice: chosenVoice,
    attitude: chosenAttitude,
    turnSeq: 0,
    state: STATES.IDLE,
    audioChunks: [], // Almacén binario en memoria para evitar sobrecarga Base64
    ws,
    createdAt: new Date(),
  });
  console.log(`[SESSION] ✅ Creada: ${clientId} | DB session=${sessionId} | lvl=${cefrLevel} | voice=${chosenVoice} | attitude=${chosenAttitude}`);
}

/**
 * Obtiene la entrada de sesión del cliente.
 * @param {string} clientId
 * @returns {object|undefined}
 */
function get(clientId) {
  return sessions.get(clientId);
}

/**
 * Elimina la sesión cuando el cliente desconecta.
 * @param {string} clientId
 */
function remove(clientId) {
  const session = sessions.get(clientId);
  if (session) {
    session.audioChunks = [];
  }
  sessions.delete(clientId);
  console.log(`[SESSION] 🗑️  Eliminada: ${clientId}`);
}

/**
 * Transiciona el estado de la sesión si la transición es permitida.
 * @param {string} clientId
 * @param {string} newState  Uno de los valores de STATES.
 * @returns {boolean}        true si la transición fue válida.
 */
function transition(clientId, newState) {
  const session = sessions.get(clientId);
  if (!session) return false;

  const allowed = VALID_TRANSITIONS[session.state] || [];
  if (!allowed.includes(newState)) {
    console.warn(
      `[SESSION] ⚠️ Transición irregular solicitada: ${session.state} → ${newState} (cliente: ${clientId}). Aplicando forceTransition defensiva.`
    );
    return forceTransition(clientId, newState);
  }

  session.state = newState;
  console.log(`[SESSION] 🔄 ${clientId}: ${session.state}`);

  // Notificar al cliente via WS
  safeSend(session.ws, { type: "state_change", state: newState });
  return true;
}

/**
 * Fuerza defensivamente el estado de la sesión para evitar bloqueos por desincronización de red.
 * @param {string} clientId
 * @param {string} targetState Uno de los valores de STATES.
 * @returns {boolean}
 */
function forceTransition(clientId, targetState) {
  const session = sessions.get(clientId);
  if (!session) return false;

  const previous = session.state;
  session.state = targetState;
  console.log(`[SESSION] 🛡️ forceTransition ${clientId}: ${previous} ➔ ${targetState}`);

  safeSend(session.ws, { type: "state_change", state: targetState, forced: true, previousState: previous });
  return true;
}

/**
 * Incrementa el contador de turno y devuelve el nuevo seq.
 * @param {string} clientId
 * @returns {number}
 */
function nextTurn(clientId) {
  const session = sessions.get(clientId);
  if (!session) return 1;
  session.turnSeq += 1;
  return session.turnSeq;
}

/**
 * Actualiza el nivel CEFR de la sesión en memoria.
 */
function updateLevel(clientId, cefrLevel) {
  const session = sessions.get(clientId);
  if (session) session.cefrLevel = cefrLevel;
}

/**
 * Actualiza la personalidad/voz del tutor en la sesión en memoria.
 */
function updateVoice(clientId, voiceId) {
  const session = sessions.get(clientId);
  if (session && voiceId) {
    const v = voiceId.toLowerCase().trim();
    session.voiceId = v;
    session.voice = v;
    console.log(`[SESSION] 🎙️ ${clientId}: tutor voice = ${v}`);
  }
}

/**
 * Actualiza la actitud pedagógica del tutor en la sesión en memoria.
 */
function updateAttitude(clientId, attitude) {
  const session = sessions.get(clientId);
  if (session && attitude) {
    const a = attitude.toLowerCase().trim();
    session.attitude = a;
    console.log(`[SESSION] 🎭 ${clientId}: tutor attitude = ${a}`);
  }
}

/**
 * Envía un mensaje JSON por WebSocket de forma segura.
 * @param {import('ws').WebSocket} ws
 * @param {object} payload
 */
function safeSend(ws, payload) {
  if (ws && ws.readyState === 1 /* OPEN */) {
    ws.send(JSON.stringify(payload));
  }
}

module.exports = {
  STATES,
  VALID_TRANSITIONS,
  create,
  get,
  remove,
  transition,
  forceTransition,
  nextTurn,
  updateLevel,
  updateVoice,
  updateAttitude,
  safeSend,
};
