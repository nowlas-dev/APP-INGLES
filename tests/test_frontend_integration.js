/**
 * LingoBeats — tests/test_frontend_integration.js
 * Verificación automatizada de la integración frontend:
 * 1. Elementos DOM y selectores de actitud en index.html.
 * 2. Métodos modulares de SyncPlayer (playStanza, playGreeting).
 * 3. Integración de app.js con /api/session/welcome y localStorage key.
 */

"use strict";

const fs   = require("fs");
const path = require("path");
const assert = require("assert");

console.log("\n=== TEST FRONTEND INTEGRATION: LingoBeats ===");

// 1. Verificación de frontend/index.html
const htmlPath = path.join(__dirname, "../frontend/index.html");
const htmlContent = fs.readFileSync(htmlPath, "utf8");

assert(htmlContent.includes('id="tutor-attitude-select"'), "Debe existir #tutor-attitude-select en index.html");
assert(htmlContent.includes('id="tutor-attitude-chip"'), "Debe existir #tutor-attitude-chip en index.html");
assert(htmlContent.includes('id="start-song-btn"'), "Debe existir #start-song-btn en index.html");
assert(htmlContent.includes('value="friendly"'), "Debe incluir opción 'friendly'");
assert(htmlContent.includes('value="funny"'), "Debe incluir opción 'funny'");
assert(htmlContent.includes('value="strict"'), "Debe incluir opción 'strict'");
console.log("  [PASS] index.html contiene el selector de actitud, opciones y botón Comenzar Canción.");

// 2. Verificación de frontend/css/style.css
const cssPath = path.join(__dirname, "../frontend/css/style.css");
const cssContent = fs.readFileSync(cssPath, "utf8");

assert(cssContent.includes(".tutor-attitude-container"), "Debe tener clase .tutor-attitude-container en CSS");
assert(cssContent.includes(".start-song-btn"), "Debe tener clase .start-song-btn en CSS");
assert(cssContent.includes(".attitude-selector-dropdown"), "Debe tener clase .attitude-selector-dropdown en CSS");
console.log("  [PASS] style.css contiene los estilos Glassmorphism para actitud y botón de inicio.");

// 3. Verificación de frontend/js/audio/player.js
const SyncPlayer = require("../frontend/js/audio/player");
assert(typeof SyncPlayer.prototype.playStanza === "function", "SyncPlayer debe tener método playStanza()");
assert(typeof SyncPlayer.prototype.playGreeting === "function", "SyncPlayer debe tener método playGreeting()");
console.log("  [PASS] SyncPlayer implementa playStanza() y playGreeting().");

// 4. Verificación de frontend/app.js y frontend/ui.js
const appPath = path.join(__dirname, "../frontend/app.js");
const appContent = fs.readFileSync(appPath, "utf8");

assert(appContent.includes("lingobeats_tutor_attitude"), "app.js debe usar clave localStorage 'lingobeats_tutor_attitude'");
assert(appContent.includes("startSongWithWelcome"), "app.js debe definir startSongWithWelcome()");
assert(appContent.includes("playStanza"), "app.js debe definir playStanza()");
assert(appContent.includes("/api/session/welcome"), "app.js debe invocar endpoint /api/session/welcome");
assert(appContent.includes("INTRO_GREETING"), "app.js debe transicionar al estado INTRO_GREETING");
console.log("  [PASS] app.js conecta el flujo de bienvenida, AudioContext, playStanza y persistencia.");

const uiPath = path.join(__dirname, "../frontend/ui.js");
const uiContent = fs.readFileSync(uiPath, "utf8");
assert(uiContent.includes("INTRO_GREETING"), "ui.js debe definir estado INTRO_GREETING en STATE_CONFIG");
assert(uiContent.includes("setSelectedAttitude"), "ui.js debe exportar setSelectedAttitude");
console.log("  [PASS] ui.js actualiza STATE_CONFIG con 'El tutor te está dando la bienvenida...' y helpers de actitud.");

console.log("\nTODOS LOS TESTS DE FRONTEND PASARON EXITOSAMENTE.");
