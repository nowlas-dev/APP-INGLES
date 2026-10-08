/**
 * Automated test suite for LingoBeats Node.js core backend.
 */
"use strict";

const sessionStore = require("../orchestrator/state/sessionStore");
const lyricsService = require("../orchestrator/services/lyricsService");
const { randomUUID } = require("crypto");

function testStateMachine() {
  const clientId = randomUUID();
  sessionStore.create(clientId, {
    sessionId: 101,
    userId: "usr_001",
    cefrLevel: "B2",
    ws: { readyState: 1, send: () => {} },
  });

  const s = sessionStore.get(clientId);
  if (s.state !== sessionStore.STATES.IDLE) throw new Error("Should be IDLE");

  // IDLE -> PROCESSING
  if (!sessionStore.transition(clientId, sessionStore.STATES.PROCESSING)) {
    throw new Error("IDLE -> PROCESSING must be allowed");
  }

  // PROCESSING -> SPEAKING
  if (!sessionStore.transition(clientId, sessionStore.STATES.SPEAKING)) {
    throw new Error("PROCESSING -> SPEAKING must be allowed");
  }

  // forceTransition
  if (!sessionStore.forceTransition(clientId, sessionStore.STATES.IDLE)) {
    throw new Error("forceTransition failed");
  }
}

function testLyricsParser() {
  const sampleLrc = `[00:10.00] Line 1\n[00:12.00] Line 2\n[00:18.00] Line 3`;
  const lines = lyricsService.parseLRC(sampleLrc);
  if (lines.length !== 3) throw new Error("Expected 3 lines");

  const stanzas = lyricsService.groupIntoStanzas(lines);
  if (stanzas.length < 2) throw new Error("Expected pause grouping");
}

testStateMachine();
testLyricsParser();
console.log("✅ All Node.js core tests passed.");
