const http = require('http');
const express = require('express');
const { WebSocketServer, WebSocket } = require('ws');
const fs = require('fs');
const path = require('path');
const axios = require('axios');

async function testFull() {
  process.chdir(path.join(__dirname, '..', 'orchestrator'));
  // Cargar el servidor
  const serverModule = require(path.join(__dirname, '..', 'orchestrator', 'server.js'));

  // Esperar a que el servidor esté escuchando
  await new Promise(r => setTimeout(r, 1000));

  const audioPath = path.resolve(__dirname, '..', 'data', 'storage', 'turns', '1', 'turn_2_1791419446.webm');
  const audioBuffer = fs.readFileSync(audioPath);

  const ws = new WebSocket('ws://127.0.0.1:3000/ws');

  ws.on('open', () => {
    console.log('[TEST] Conectado a ws://127.0.0.1:3000/ws');
  });

  ws.on('message', (rawData, isBinary) => {
    if (isBinary) {
      console.log('[TEST] Frame binario recibido:', rawData.length);
      return;
    }
    const msg = JSON.parse(rawData.toString('utf8'));
    console.log('[TEST] Evento WS recibido:', msg.type);

    if (msg.type === 'connected') {
      console.log('[TEST] Sesión lista:', msg.sessionId, 'Enviando audio...');
      ws.send(audioBuffer);
    } else if (msg.type === 'tutor_response') {
      console.log('[TEST] ✅ EXITO TOTAL - TUTOR RESPONDIÓ:');
      console.log('       Transcripción:', msg.transcript);
      console.log('       Conversación:', msg.conversation);
      console.log('       Feedback:', msg.feedback);
      console.log('       Audio sintetizado:', !!msg.audio_b64);
      ws.close();
      process.exit(0);
    } else if (msg.type === 'error') {
      console.error('[TEST] ❌ Error:', msg.message);
      ws.close();
      process.exit(1);
    }
  });

  ws.on('error', (err) => {
    console.error('[TEST] WS error:', err.message);
    process.exit(1);
  });
}

testFull().catch(err => {
  console.error('[TEST] Error global:', err);
  process.exit(1);
});
