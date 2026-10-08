const path = require("path");
const WebSocket = require(path.join(__dirname, "../orchestrator/node_modules/ws"));

const ws = new WebSocket("ws://127.0.0.1:3000/ws");

ws.on("open", () => {
  console.log("[TEST WS] Conectado. Enviando set_voice con jorge...");
  ws.send(JSON.stringify({ type: "set_voice", voice_id: "jorge" }));
});

ws.on("message", (data) => {
  const msg = JSON.parse(data.toString());
  console.log("[TEST WS] Mensaje recibido:", msg.type, msg.voice_id || msg.state || "");
  if (msg.type === "voice_updated") {
    console.log("[TEST WS] OK! Voz actualizada exitosamente a:", msg.voice_id);
    ws.close();
    process.exit(0);
  }
});

setTimeout(() => {
  console.error("[TEST WS] Timeout");
  ws.close();
  process.exit(1);
}, 5000);
